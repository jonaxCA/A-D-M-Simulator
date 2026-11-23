SET client_encoding = 'UTF8';
-- =============================================================================
-- 064_proyectos_archivado_y_firma.sql
-- Dominio: escenarios. Proyectos de investigación, archivado de escenarios,
-- devolución y firma de versiones (D54, D55, D7 del checklist).
--
-- - research_projects: un proyecto de investigación del escritorio agrupa
--   escenarios de una enfermedad y una región, con su objetivo, su periodo de
--   estudio y los motores que contempla. Lo escribe escenarios; no se borra, se
--   archiva.
-- - scenarios.project_id: el proyecto de un escenario, opcional. El trigger
--   fn_escenario_en_proyecto exige la misma enfermedad y región que el proyecto.
-- - scenarios.status = 'archivado' ya existía en el CHECK de la 006; aquí
--   svc_escenarios recibe el UPDATE para escribirlo (y para quitar is_public, que
--   ck_scenarios_publico solo admite en uno publicado), y fn_version_aprobada
--   (014) rechaza también las corridas de un escenario archivado.
-- - scenario_versions.approval_sha256: la firma de una versión aprobada, la
--   SHA-256 de la entrada canónica del motor (la misma huella_escenario que cada
--   corrida guarda en simulation_runs.scenario_checksum). Las aprobadas antes de
--   esta migración quedan sin firma.
-- - SCENARIO_RETURNED entra al CHECK de notifications: una versión devuelta para
--   cambios vuelve a borrador con el comentario del revisor.
-- - Es la 064 y no la 042 de D porque rehace ck_notifications_type: en una
--   instalación limpia por número, la 057 y la 060 la volverían a dejar sin el
--   tipo nuevo.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS research_projects (
    id           BIGSERIAL     PRIMARY KEY,
    name         VARCHAR(160)  NOT NULL,
    objective    TEXT,
    disease_id   SMALLINT      NOT NULL,
    region_id    INTEGER       NOT NULL,
    period_start DATE          NOT NULL,
    period_end   DATE          NOT NULL,
    engines      TEXT[]        NOT NULL,
    owner_id     BIGINT        NOT NULL,
    status       VARCHAR(20)   NOT NULL DEFAULT 'activo',
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT fk_research_projects_disease
        FOREIGN KEY (disease_id) REFERENCES diseases (id) ON DELETE RESTRICT,
    CONSTRAINT fk_research_projects_region
        FOREIGN KEY (region_id)  REFERENCES regions (id)  ON DELETE RESTRICT,
    CONSTRAINT fk_research_projects_owner
        FOREIGN KEY (owner_id)   REFERENCES users (id)    ON DELETE RESTRICT,
    CONSTRAINT uq_research_projects_owner_name UNIQUE (owner_id, name),
    CONSTRAINT ck_research_projects_name CHECK (char_length(btrim(name)) BETWEEN 3 AND 160),
    CONSTRAINT ck_research_projects_periodo CHECK (period_end >= period_start),
    CONSTRAINT ck_research_projects_motores CHECK (
        cardinality(engines) >= 1
        AND engines <@ ARRAY['seir-ref', 'abm-ref', 'abm-gpu']::TEXT[]),
    CONSTRAINT ck_research_projects_status CHECK (status IN ('activo', 'archivado'))
);

CREATE INDEX IF NOT EXISTS ix_research_projects_region ON research_projects (region_id);

COMMENT ON TABLE research_projects IS
    'Proyectos de investigación del escritorio (D54): agrupan escenarios de una enfermedad y una región. Los escribe escenarios; no se borran, se archivan.';
COMMENT ON COLUMN research_projects.id IS 'Identificador del proyecto.';
COMMENT ON COLUMN research_projects.name IS 'Nombre del proyecto, único para cada dueño.';
COMMENT ON COLUMN research_projects.objective IS 'Pregunta u objetivo de la investigación.';
COMMENT ON COLUMN research_projects.disease_id IS 'Enfermedad que estudia. Referencia a diseases.id. [llave foranea]';
COMMENT ON COLUMN research_projects.region_id IS 'Región que estudia; da el alcance de D43. Referencia a regions.id. [llave foranea]';
COMMENT ON COLUMN research_projects.period_start IS 'Inicio del periodo de estudio.';
COMMENT ON COLUMN research_projects.period_end IS 'Fin del periodo de estudio (no antes del inicio).';
COMMENT ON COLUMN research_projects.engines IS 'Motores que contempla el proyecto: seir-ref, abm-ref o abm-gpu (al menos uno).';
COMMENT ON COLUMN research_projects.owner_id IS 'Quien creó el proyecto. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN research_projects.status IS 'activo o archivado. Un proyecto archivado no recibe escenarios nuevos.';
COMMENT ON COLUMN research_projects.created_at IS 'Alta del proyecto.';
COMMENT ON COLUMN research_projects.updated_at IS 'Último cambio.';

ALTER TABLE scenarios ADD COLUMN IF NOT EXISTS project_id BIGINT;
ALTER TABLE scenarios
    DROP CONSTRAINT IF EXISTS fk_scenarios_project,
    ADD  CONSTRAINT fk_scenarios_project
        FOREIGN KEY (project_id) REFERENCES research_projects (id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS ix_scenarios_project ON scenarios (project_id) WHERE project_id IS NOT NULL;

COMMENT ON COLUMN scenarios.project_id IS
    'Proyecto de investigación al que pertenece, opcional (D54). Misma enfermedad y región que el proyecto (fn_escenario_en_proyecto). Referencia a research_projects.id. [llave foranea]';
COMMENT ON COLUMN scenarios.status IS
    'borrador, publicado (visible en el sitio público con is_public) o archivado. Un escenario archivado es de solo lectura: no recibe versiones, cambios de intervenciones, envíos a revisión ni corridas, y deja de ser público; al restaurarlo vuelve a borrador (D54).';

CREATE OR REPLACE FUNCTION fn_escenario_en_proyecto()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_disease SMALLINT;
    v_region  INTEGER;
BEGIN
    IF NEW.project_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT disease_id, region_id INTO v_disease, v_region
    FROM research_projects
    WHERE id = NEW.project_id;
    IF v_disease IS DISTINCT FROM NEW.disease_id OR v_region IS DISTINCT FROM NEW.region_id THEN
        RAISE EXCEPTION
            'El escenario % no es de la enfermedad y la región del proyecto %.',
            NEW.id, NEW.project_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION fn_escenario_en_proyecto() IS
    'Trigger BEFORE INSERT OR UPDATE en scenarios: un escenario solo entra a un proyecto de su misma enfermedad y región (D54).';

DROP TRIGGER IF EXISTS tg_scenarios_en_proyecto ON scenarios;
CREATE TRIGGER tg_scenarios_en_proyecto
    BEFORE INSERT OR UPDATE OF project_id, disease_id, region_id ON scenarios
    FOR EACH ROW EXECUTE FUNCTION fn_escenario_en_proyecto();

-- Lo mismo de la 014, más el escenario archivado.
CREATE OR REPLACE FUNCTION fn_version_aprobada()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_status    VARCHAR(20);
    v_escenario VARCHAR(20);
BEGIN
    SELECT v.status, s.status INTO v_status, v_escenario
    FROM scenario_versions v
    JOIN scenarios s ON s.id = v.scenario_id
    WHERE v.id = NEW.scenario_version_id;

    IF v_status IS DISTINCT FROM 'aprobado' THEN
        RAISE EXCEPTION
            'La version de escenario % no esta aprobada (estado: %); no se puede simular.',
            NEW.scenario_version_id, COALESCE(v_status, 'inexistente')
            USING ERRCODE = 'restrict_violation';
    END IF;

    IF v_escenario = 'archivado' THEN
        RAISE EXCEPTION
            'El escenario de la version % esta archivado; no se puede simular.',
            NEW.scenario_version_id
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION fn_version_aprobada() IS
    'Trigger BEFORE INSERT: rechaza corridas y lotes sobre versiones de escenario que no esten aprobadas o cuyo escenario este archivado (014, 064).';

ALTER TABLE scenario_versions ADD COLUMN IF NOT EXISTS approval_sha256 CHAR(64);
ALTER TABLE scenario_versions
    DROP CONSTRAINT IF EXISTS ck_scenario_versions_firma,
    ADD  CONSTRAINT ck_scenario_versions_firma CHECK (
        approval_sha256 IS NULL
        OR (approval_sha256 ~ '^[0-9a-f]{64}$' AND status = 'aprobado'));

COMMENT ON COLUMN scenario_versions.approval_sha256 IS
    'Firma de la versión aprobada (D55): SHA-256 de la entrada canónica del motor al aprobarla, la misma huella_escenario que guarda cada corrida en simulation_runs.scenario_checksum. NULL si se aprobó antes de la 064.';
COMMENT ON COLUMN scenario_versions.review_comment IS
    'Comentario del revisor. En un rechazo es el motivo (obligatorio); en un borrador, el motivo por el que se devolvió para cambios (D55).';

ALTER TABLE notifications DROP CONSTRAINT IF EXISTS ck_notifications_type;
ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type CHECK (type IN
    ('RUN_FINISHED', 'RUN_FAILED', 'THRESHOLD_EXCEEDED', 'ASSIGNMENT',
     'SCENARIO_PUBLISHED', 'SCENARIO_APPROVED', 'SCENARIO_SUBMITTED',
     'SCENARIO_REJECTED', 'NEW_CASES', 'SYSTEM', 'CASE_REJECTED', 'CAMPAIGN',
     'DATA_INCOMPLETE', 'SCENARIO_RETURNED'));

COMMENT ON COLUMN notifications.type IS
    'Tipo: RUN_FINISHED, RUN_FAILED, THRESHOLD_EXCEEDED, ASSIGNMENT, SCENARIO_PUBLISHED, SCENARIO_APPROVED, SCENARIO_SUBMITTED, SCENARIO_REJECTED, NEW_CASES, SYSTEM, CASE_REJECTED, CAMPAIGN, DATA_INCOMPLETE o SCENARIO_RETURNED.';

GRANT SELECT, INSERT, UPDATE ON research_projects TO svc_escenarios;
GRANT USAGE ON SEQUENCE research_projects_id_seq TO svc_escenarios;
GRANT UPDATE (status, project_id, is_public) ON scenarios TO svc_escenarios;
GRANT UPDATE (approval_sha256) ON scenario_versions TO svc_aprobacion;
GRANT SELECT (scenario_version_id, scenario_checksum, status) ON simulation_runs TO svc_aprobacion;

INSERT INTO schema_migrations (version, description)
VALUES ('064', 'Proyectos de investigación, archivado de escenarios y devolución y firma de versiones (D54, D55)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
