SET client_encoding = 'UTF8';
-- =============================================================================
-- 045_intentos_de_corridas.sql
-- Una corrida interrumpida se reencola en lugar de cerrarse como fallida (D38).
--
-- - attempts cuenta las veces que la corrida pasó a 'ejecutando'. Al arrancar,
--   el simulador regresa a 'encolado' las que se quedaron en 'ejecutando' con
--   menos de 3 intentos y la misma versión de motor; las demás se cierran como
--   'fallido'. Así una corrida que tumba al trabajador cada vez no se repite
--   para siempre.
-- - svc_simulador suma el intento al marcarla 'ejecutando'.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

ALTER TABLE simulation_runs
    ADD COLUMN IF NOT EXISTS attempts SMALLINT NOT NULL DEFAULT 0;

ALTER TABLE simulation_runs
    DROP CONSTRAINT IF EXISTS ck_simulation_runs_attempts,
    ADD  CONSTRAINT ck_simulation_runs_attempts CHECK (attempts BETWEEN 0 AND 3);

COMMENT ON COLUMN simulation_runs.attempts IS
    'Veces que la corrida paso a ejecutando. Una interrumpida se reencola mientras sea menor que 3 (D38).';

GRANT UPDATE (attempts) ON simulation_runs TO svc_simulador;

INSERT INTO schema_migrations (version, description)
VALUES ('045', 'Simulacion: intentos de una corrida interrumpida que se reencola (D38)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
