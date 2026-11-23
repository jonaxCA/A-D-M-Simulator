SET client_encoding = 'UTF8';
-- =============================================================================
-- 057_seguimiento_de_casos.sql
-- Dominio: vigilancia. Corregir un caso y cambiar su estado, con control de
-- versión e historial (D47, F7; RF-C11 y RF-C15).
--
-- - cases.version: cada cambio la sube en 1. Quien corrige o cambia el estado
--   manda la versión que leyó (If-Match); si alguien lo cambió antes, el cambio
--   se rechaza en vez de sobrescribir en silencio lo que hizo otra persona.
-- - updated_at y updated_by: el último cambio. status_reason: el motivo del
--   estado (obligatorio al descartar, marcar duplicado o reabrir).
--   duplicate_of: el caso original de uno marcado como duplicado.
-- - case_history: una fila por cambio, con la versión que dejó, quién y cuándo,
--   el estado antes y después, los campos que cambiaron ({campo: {antes,
--   despues}}), el motivo y el dispositivo, si vino de la app móvil.
-- - CASE_REJECTED: el aviso al capturista cuando su caso se descarta o se
--   marca como duplicado.
-- - svc_casos actualiza solo las columnas que se corrigen y las del
--   seguimiento; nunca local_uuid, reported_by ni device_id.
-- - Los casos que ya existen quedan en la versión 1, sin historial. Uno que ya
--   estaba 'duplicado' se queda sin duplicate_of: el CHECK solo exige que un
--   duplicate_of venga con el estado 'duplicado', no al revés.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

ALTER TABLE cases
    ADD COLUMN IF NOT EXISTS version       INTEGER      NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS updated_at    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_by    BIGINT,
    ADD COLUMN IF NOT EXISTS status_reason VARCHAR(500),
    ADD COLUMN IF NOT EXISTS duplicate_of  BIGINT;

ALTER TABLE cases
    DROP CONSTRAINT IF EXISTS fk_cases_updated_by,
    ADD  CONSTRAINT fk_cases_updated_by
        FOREIGN KEY (updated_by) REFERENCES users (id) ON DELETE RESTRICT,
    DROP CONSTRAINT IF EXISTS fk_cases_duplicate_of,
    ADD  CONSTRAINT fk_cases_duplicate_of
        FOREIGN KEY (duplicate_of) REFERENCES cases (id) ON DELETE RESTRICT,
    DROP CONSTRAINT IF EXISTS ck_cases_version,
    ADD  CONSTRAINT ck_cases_version CHECK (version >= 1),
    DROP CONSTRAINT IF EXISTS ck_cases_duplicate_of,
    ADD  CONSTRAINT ck_cases_duplicate_of CHECK (
        duplicate_of IS NULL OR (status = 'duplicado' AND duplicate_of <> id));

COMMENT ON COLUMN cases.version IS
    'Versión del caso: empieza en 1 y cada corrección o cambio de estado la sube en 1. Quien cambia el caso manda la que leyó (If-Match, D47).';
COMMENT ON COLUMN cases.updated_at IS 'Momento del último cambio; nulo si nunca se cambió.';
COMMENT ON COLUMN cases.updated_by IS 'Quién hizo el último cambio. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN cases.status_reason IS
    'Motivo del estado actual: obligatorio al descartar, marcar duplicado o reabrir (D47).';
COMMENT ON COLUMN cases.duplicate_of IS
    'Caso original de uno marcado como duplicado. Referencia a cases.id. [llave foranea]';

CREATE TABLE IF NOT EXISTS case_history (
    id            BIGSERIAL     PRIMARY KEY,
    case_id       BIGINT        NOT NULL,
    version       INTEGER       NOT NULL,
    action        VARCHAR(20)   NOT NULL,
    changed_by    BIGINT        NOT NULL,
    changed_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    status_before VARCHAR(20),
    status_after  VARCHAR(20),
    changes       JSONB         NOT NULL DEFAULT '{}'::jsonb,
    reason        VARCHAR(500),
    device_id     BIGINT,

    CONSTRAINT uq_case_history_version UNIQUE (case_id, version),
    CONSTRAINT fk_case_history_case
        FOREIGN KEY (case_id)    REFERENCES cases (id)   ON DELETE RESTRICT,
    CONSTRAINT fk_case_history_user
        FOREIGN KEY (changed_by) REFERENCES users (id)   ON DELETE RESTRICT,
    CONSTRAINT fk_case_history_device
        FOREIGN KEY (device_id)  REFERENCES devices (id) ON DELETE SET NULL,
    CONSTRAINT ck_case_history_action CHECK (action IN ('correccion', 'estado')),
    CONSTRAINT ck_case_history_version CHECK (version >= 2)
);

COMMENT ON TABLE case_history IS
    'Historial de un caso: una fila por corrección o cambio de estado (D47). Solo la escribe svc_casos.';
COMMENT ON COLUMN case_history.id IS 'Identificador del cambio. [llave primaria]';
COMMENT ON COLUMN case_history.case_id IS 'Caso que cambió. Referencia a cases.id. [llave foranea]';
COMMENT ON COLUMN case_history.version IS 'Versión del caso que dejó este cambio (la primera es la 2).';
COMMENT ON COLUMN case_history.action IS 'correccion (datos del caso) o estado (validar, descartar, duplicado, reabrir).';
COMMENT ON COLUMN case_history.changed_by IS 'Quién hizo el cambio. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN case_history.changed_at IS 'Momento del cambio.';
COMMENT ON COLUMN case_history.status_before IS 'Estado del caso antes del cambio.';
COMMENT ON COLUMN case_history.status_after IS 'Estado del caso después del cambio.';
COMMENT ON COLUMN case_history.changes IS 'Campos que cambiaron: {campo: {antes, despues}}.';
COMMENT ON COLUMN case_history.reason IS 'Motivo que dio quien hizo el cambio.';
COMMENT ON COLUMN case_history.device_id IS 'Dispositivo desde el que llegó, si vino de la app móvil. Referencia a devices.id. [llave foranea]';

ALTER TABLE notifications DROP CONSTRAINT IF EXISTS ck_notifications_type;
ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type CHECK (type IN
    ('RUN_FINISHED', 'RUN_FAILED', 'THRESHOLD_EXCEEDED', 'ASSIGNMENT',
     'SCENARIO_PUBLISHED', 'SCENARIO_APPROVED', 'SCENARIO_SUBMITTED',
     'SCENARIO_REJECTED', 'NEW_CASES', 'SYSTEM', 'CASE_REJECTED'));

COMMENT ON COLUMN notifications.type IS
    'Tipo: RUN_FINISHED, RUN_FAILED, THRESHOLD_EXCEEDED, ASSIGNMENT, SCENARIO_PUBLISHED, SCENARIO_APPROVED, SCENARIO_SUBMITTED, SCENARIO_REJECTED, NEW_CASES, SYSTEM o CASE_REJECTED.';

GRANT UPDATE (disease_id, region_id, age, sex, onset_date, report_date, latitude, longitude,
              test_result, severity, status, version, updated_at, updated_by, status_reason,
              duplicate_of) ON cases TO svc_casos;
GRANT SELECT, INSERT ON case_history TO svc_casos;
GRANT USAGE ON SEQUENCE case_history_id_seq TO svc_casos;

INSERT INTO schema_migrations (version, description)
VALUES ('057', 'Vigilancia: version, motivo e historial de cada caso, y el aviso CASE_REJECTED (D47)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
