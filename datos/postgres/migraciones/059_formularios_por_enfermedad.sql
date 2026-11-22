SET client_encoding = 'UTF8';
-- =============================================================================
-- 059_formularios_por_enfermedad.sql
-- Dominio: vigilancia. Formularios por enfermedad, con versiones (D48, F7).
--
-- - Los campos fijos de un caso (enfermedad, municipio, fechas, edad, sexo,
--   ubicación, resultado y gravedad) se quedan como están. Cada enfermedad
--   puede sumar los suyos en un formulario: case_forms guarda cada versión,
--   con sus campos en orden (fields, una lista de objetos: clave, etiqueta,
--   tipo, obligatorio, mínimo, máximo, opciones...).
-- - Una versión nace 'borrador', se edita y se publica; publicada ya no
--   cambia. Al publicar otra, la anterior pasa a 'retirado', pero sigue
--   valiendo para los casos que se capturaron con ella sin conexión.
-- - A lo más un borrador y una versión publicada por enfermedad (índices
--   únicos parciales).
-- - required: con la versión vigente marcada, un caso de esa enfermedad tiene
--   que traer sus respuestas. Nace en false: la app todavía no manda
--   formularios (B4).
-- - cases.form_id y cases.form_answers: la versión con que se capturó el caso y
--   sus respuestas, ya validadas por casos. Van juntas o ninguna.
-- - svc_casos administra case_forms; en cases corrige form_id y form_answers.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS case_forms (
    id            BIGSERIAL     PRIMARY KEY,
    disease_id    SMALLINT      NOT NULL,
    version       INTEGER       NOT NULL,
    status        VARCHAR(20)   NOT NULL DEFAULT 'borrador',
    title         VARCHAR(160)  NOT NULL,
    fields        JSONB         NOT NULL DEFAULT '[]'::jsonb,
    required      BOOLEAN       NOT NULL DEFAULT false,
    created_by    BIGINT        NOT NULL,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ,
    published_by  BIGINT,
    published_at  TIMESTAMPTZ,

    CONSTRAINT uq_case_forms_version UNIQUE (disease_id, version),
    CONSTRAINT fk_case_forms_disease
        FOREIGN KEY (disease_id)   REFERENCES diseases (id) ON DELETE RESTRICT,
    CONSTRAINT fk_case_forms_creador
        FOREIGN KEY (created_by)   REFERENCES users (id)    ON DELETE RESTRICT,
    CONSTRAINT fk_case_forms_publicador
        FOREIGN KEY (published_by) REFERENCES users (id)    ON DELETE RESTRICT,
    CONSTRAINT ck_case_forms_status CHECK (status IN ('borrador', 'publicado', 'retirado')),
    CONSTRAINT ck_case_forms_version CHECK (version >= 1),
    CONSTRAINT ck_case_forms_fields CHECK (jsonb_typeof(fields) = 'array'),
    CONSTRAINT ck_case_forms_publicacion CHECK (
        (status = 'borrador') = (published_at IS NULL)
        AND (published_at IS NULL) = (published_by IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_case_forms_vigente
    ON case_forms (disease_id) WHERE status = 'publicado';
CREATE UNIQUE INDEX IF NOT EXISTS ux_case_forms_borrador
    ON case_forms (disease_id) WHERE status = 'borrador';

COMMENT ON TABLE case_forms IS
    'Formulario de captura de una enfermedad, por versión (D48): los campos que suma a los fijos del caso.';
COMMENT ON COLUMN case_forms.id IS 'Identificador de la versión del formulario. [llave primaria]';
COMMENT ON COLUMN case_forms.disease_id IS 'Enfermedad. Referencia a diseases.id. [llave foranea]';
COMMENT ON COLUMN case_forms.version IS 'Número de versión dentro de la enfermedad, desde 1.';
COMMENT ON COLUMN case_forms.status IS
    'borrador (se edita), publicado (la vigente; ya no cambia) o retirado (la reemplazó otra; sigue valiendo para los casos capturados con ella).';
COMMENT ON COLUMN case_forms.title IS 'Título que muestra la app.';
COMMENT ON COLUMN case_forms.fields IS
    'Campos en orden: [{clave, etiqueta, tipo (texto, entero, decimal, fecha, booleano, opcion, opciones), obligatorio, minimo, maximo, max_largo, opciones [{valor, etiqueta}], ayuda}]. Los valida casos.';
COMMENT ON COLUMN case_forms.required IS
    'Si es la vigente y está en true, un caso de la enfermedad tiene que traer sus respuestas.';
COMMENT ON COLUMN case_forms.created_by IS 'Quién creó el borrador. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN case_forms.created_at IS 'Momento en que se creó el borrador.';
COMMENT ON COLUMN case_forms.updated_at IS 'Último cambio del borrador.';
COMMENT ON COLUMN case_forms.published_by IS 'Quién lo publicó. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN case_forms.published_at IS 'Momento de la publicación; nulo en un borrador.';

ALTER TABLE cases
    ADD COLUMN IF NOT EXISTS form_id      BIGINT,
    ADD COLUMN IF NOT EXISTS form_answers JSONB;

ALTER TABLE cases
    DROP CONSTRAINT IF EXISTS fk_cases_form,
    ADD  CONSTRAINT fk_cases_form
        FOREIGN KEY (form_id) REFERENCES case_forms (id) ON DELETE RESTRICT,
    DROP CONSTRAINT IF EXISTS ck_cases_formulario,
    ADD  CONSTRAINT ck_cases_formulario CHECK (
        (form_id IS NULL) = (form_answers IS NULL)
        AND (form_answers IS NULL OR jsonb_typeof(form_answers) = 'object'));

COMMENT ON COLUMN cases.form_id IS
    'Versión del formulario de la enfermedad con que se capturó el caso; nulo si no trajo formulario. Referencia a case_forms.id. [llave foranea]';
COMMENT ON COLUMN cases.form_answers IS
    'Respuestas al formulario, {clave: valor}, ya validadas contra su versión. Va junto con form_id.';

GRANT SELECT, INSERT, UPDATE ON case_forms TO svc_casos;
GRANT USAGE ON SEQUENCE case_forms_id_seq TO svc_casos;
GRANT UPDATE (form_id, form_answers) ON cases TO svc_casos;

INSERT INTO schema_migrations (version, description)
VALUES ('059', 'Vigilancia: formularios por enfermedad con versiones y las respuestas de cada caso (D48)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
