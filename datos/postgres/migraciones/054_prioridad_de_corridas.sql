SET client_encoding = 'UTF8';
-- =============================================================================
-- 054_prioridad_de_corridas.sql
-- Prioridad en la cola de corridas y reintento manual de una fallida (RF-E07,
-- RF-E08, D44).
--
-- - priority: 'baja', 'normal' (por omisión) o 'alta'. El simulador toma antes las
--   altas y luego las normales; dentro de cada una, en orden de llegada.
-- - Reintentar una fallida la regresa a 'encolado' con la misma semilla, así que
--   svc_corridas necesita limpiar error_message, progress y attempts.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

ALTER TABLE simulation_runs
    ADD COLUMN IF NOT EXISTS priority VARCHAR(10) NOT NULL DEFAULT 'normal';

ALTER TABLE simulation_runs
    DROP CONSTRAINT IF EXISTS ck_simulation_runs_priority,
    ADD  CONSTRAINT ck_simulation_runs_priority CHECK (priority IN ('baja', 'normal', 'alta'));

COMMENT ON COLUMN simulation_runs.priority IS
    'Prioridad en la cola de su motor: baja, normal o alta. Solo el ADMINISTRADOR pide alta (D44).';

GRANT UPDATE (error_message, progress, attempts) ON simulation_runs TO svc_corridas;

INSERT INTO schema_migrations (version, description)
VALUES ('054', 'Simulacion: prioridad de la corrida en la cola y permisos para reintentar una fallida (D44)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
