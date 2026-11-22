SET client_encoding = 'UTF8';
-- =============================================================================
-- 060_campanas_y_preferencias.sql
-- Dominio: vigilancia y plataforma. Campañas, avisos de datos incompletos y
-- preferencias de avisos por persona (D49, F7).
--
-- - campaigns: una campaña de salud de una enfermedad, en un municipio o en
--   todo Nuevo León (region_id nulo), con sus fechas, la población objetivo y
--   la descripción. La administra vacunas; su estado (programada, activa,
--   terminada o cancelada) sale de las fechas y de cancelled_at. Sin coberturas:
--   eso es el servicio opcional de vacunación.
-- - notification_preferences: los tipos de aviso que una persona apagó (o
--   volvió a prender). Sin fila, el tipo está prendido. SYSTEM no se apaga.
-- - CAMPAIGN (a los CAPTURISTA, al crear una campaña) y DATA_INCOMPLETE (a quien
--   capturó casos a los que les faltan datos) entran al CHECK de notifications.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS campaigns (
    id                BIGSERIAL     PRIMARY KEY,
    name              VARCHAR(160)  NOT NULL,
    disease_id        SMALLINT      NOT NULL,
    region_id         INTEGER,
    starts_on         DATE          NOT NULL,
    ends_on           DATE          NOT NULL,
    target_population INTEGER,
    description       TEXT,
    created_by        BIGINT        NOT NULL,
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ,
    cancelled_at      TIMESTAMPTZ,
    cancelled_by      BIGINT,
    cancel_reason     VARCHAR(500),

    CONSTRAINT fk_campaigns_disease
        FOREIGN KEY (disease_id)   REFERENCES diseases (id) ON DELETE RESTRICT,
    CONSTRAINT fk_campaigns_region
        FOREIGN KEY (region_id)    REFERENCES regions (id)  ON DELETE RESTRICT,
    CONSTRAINT fk_campaigns_creador
        FOREIGN KEY (created_by)   REFERENCES users (id)    ON DELETE RESTRICT,
    CONSTRAINT fk_campaigns_cancelo
        FOREIGN KEY (cancelled_by) REFERENCES users (id)    ON DELETE RESTRICT,
    CONSTRAINT ck_campaigns_fechas CHECK (ends_on >= starts_on),
    CONSTRAINT ck_campaigns_poblacion CHECK (target_population IS NULL OR target_population > 0),
    CONSTRAINT ck_campaigns_descripcion CHECK (description IS NULL OR length(description) <= 2000),
    CONSTRAINT ck_campaigns_cancelacion CHECK (
        (cancelled_at IS NULL) = (cancelled_by IS NULL)
        AND (cancelled_at IS NULL) = (cancel_reason IS NULL))
);

CREATE INDEX IF NOT EXISTS ix_campaigns_fechas ON campaigns (starts_on, ends_on);

COMMENT ON TABLE campaigns IS
    'Campaña de salud de una enfermedad, en un municipio o en todo Nuevo León (D49). La escribe svc_vacunas.';
COMMENT ON COLUMN campaigns.id IS 'Identificador de la campaña. [llave primaria]';
COMMENT ON COLUMN campaigns.name IS 'Nombre de la campaña.';
COMMENT ON COLUMN campaigns.disease_id IS 'Enfermedad. Referencia a diseases.id. [llave foranea]';
COMMENT ON COLUMN campaigns.region_id IS 'Municipio de Nuevo León; nulo si es todo el estado. Referencia a regions.id. [llave foranea]';
COMMENT ON COLUMN campaigns.starts_on IS 'Primer día de la campaña.';
COMMENT ON COLUMN campaigns.ends_on IS 'Último día de la campaña.';
COMMENT ON COLUMN campaigns.target_population IS 'Población objetivo (personas), si se conoce.';
COMMENT ON COLUMN campaigns.description IS 'A quién va dirigida y qué se hace (hasta 2000 caracteres).';
COMMENT ON COLUMN campaigns.created_by IS 'Quién la creó. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN campaigns.created_at IS 'Momento de alta.';
COMMENT ON COLUMN campaigns.updated_at IS 'Último cambio.';
COMMENT ON COLUMN campaigns.cancelled_at IS 'Momento de la cancelación; nulo si no se canceló.';
COMMENT ON COLUMN campaigns.cancelled_by IS 'Quién la canceló. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN campaigns.cancel_reason IS 'Motivo de la cancelación.';

CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id    BIGINT       NOT NULL,
    type       VARCHAR(40)  NOT NULL,
    enabled    BOOLEAN      NOT NULL,
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT pk_notification_preferences PRIMARY KEY (user_id, type),
    CONSTRAINT fk_notification_preferences_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_notification_preferences_system CHECK (type <> 'SYSTEM')
);

COMMENT ON TABLE notification_preferences IS
    'Los tipos de aviso que una persona apagó o volvió a prender (D49). Sin fila, el tipo está prendido.';
COMMENT ON COLUMN notification_preferences.user_id IS 'Persona. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN notification_preferences.type IS 'Tipo de aviso (como notifications.type); SYSTEM no se apaga.';
COMMENT ON COLUMN notification_preferences.enabled IS 'false: notificaciones no le crea avisos de ese tipo.';
COMMENT ON COLUMN notification_preferences.updated_at IS 'Último cambio.';

ALTER TABLE notifications DROP CONSTRAINT IF EXISTS ck_notifications_type;
ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type CHECK (type IN
    ('RUN_FINISHED', 'RUN_FAILED', 'THRESHOLD_EXCEEDED', 'ASSIGNMENT',
     'SCENARIO_PUBLISHED', 'SCENARIO_APPROVED', 'SCENARIO_SUBMITTED',
     'SCENARIO_REJECTED', 'NEW_CASES', 'SYSTEM', 'CASE_REJECTED', 'CAMPAIGN',
     'DATA_INCOMPLETE'));

COMMENT ON COLUMN notifications.type IS
    'Tipo: RUN_FINISHED, RUN_FAILED, THRESHOLD_EXCEEDED, ASSIGNMENT, SCENARIO_PUBLISHED, SCENARIO_APPROVED, SCENARIO_SUBMITTED, SCENARIO_REJECTED, NEW_CASES, SYSTEM, CASE_REJECTED, CAMPAIGN o DATA_INCOMPLETE.';

GRANT SELECT, INSERT, UPDATE ON campaigns TO svc_vacunas;
GRANT USAGE ON SEQUENCE campaigns_id_seq TO svc_vacunas;
GRANT SELECT (level, parent_region_id, code) ON regions TO svc_vacunas;
GRANT SELECT, INSERT, UPDATE ON notification_preferences TO svc_notificaciones;

INSERT INTO schema_migrations (version, description)
VALUES ('060', 'Campañas, preferencias de avisos y los tipos CAMPAIGN y DATA_INCOMPLETE (D49)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
