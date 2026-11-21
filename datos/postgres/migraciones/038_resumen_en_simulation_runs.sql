SET client_encoding = 'UTF8';
-- =============================================================================
-- 038_resumen_en_simulation_runs.sql
-- El resumen de cada corrida pasa a simulation_runs (D28).
--
-- - D28: la serie diaria va a MongoDB (series_corridas) y el resumen, la huella
--   del escenario y la trazabilidad, a simulation_runs. simulation_results deja
--   de usarse; la retira la 041.
-- - Las columnas generadas son las mismas que tenia simulation_results (014):
--   la comparacion las ordena y grafica sin abrir el JSON. Leen los nombres de
--   la salida del motor (procesamiento/contrato.py).
-- - Las llena el simulador al cerrar la corrida como completada; en las demas
--   quedan en NULL.
-- - Copia lo que hubiera en simulation_results, si la tabla sigue ahi.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

ALTER TABLE simulation_runs
    ADD COLUMN IF NOT EXISTS scenario_checksum CHAR(64),
    ADD COLUMN IF NOT EXISTS resumen           JSONB,
    ADD COLUMN IF NOT EXISTS trazabilidad      JSONB;

ALTER TABLE simulation_runs
    ADD COLUMN IF NOT EXISTS casos_acumulados   INTEGER      GENERATED ALWAYS AS ((resumen->>'casos_acumulados')::integer)   STORED,
    ADD COLUMN IF NOT EXISTS hospitalizaciones  INTEGER      GENERATED ALWAYS AS ((resumen->>'hospitalizaciones')::integer)  STORED,
    ADD COLUMN IF NOT EXISTS fallecimientos     INTEGER      GENERATED ALWAYS AS ((resumen->>'fallecimientos')::integer)     STORED,
    ADD COLUMN IF NOT EXISTS pico_casos_activos INTEGER      GENERATED ALWAYS AS ((resumen->>'pico_casos_activos')::integer) STORED,
    ADD COLUMN IF NOT EXISTS dia_pico           SMALLINT     GENERATED ALWAYS AS ((resumen->>'dia_pico')::smallint)          STORED,
    ADD COLUMN IF NOT EXISTS tasa_ataque        NUMERIC(8,6) GENERATED ALWAYS AS ((resumen->>'tasa_ataque')::numeric)        STORED;

ALTER TABLE simulation_runs
    DROP CONSTRAINT IF EXISTS ck_simulation_runs_resumen,
    ADD  CONSTRAINT ck_simulation_runs_resumen
        CHECK (resumen IS NULL OR jsonb_typeof(resumen) = 'object'),
    DROP CONSTRAINT IF EXISTS ck_simulation_runs_traza,
    ADD  CONSTRAINT ck_simulation_runs_traza
        CHECK (trazabilidad IS NULL OR jsonb_typeof(trazabilidad) = 'array'),
    DROP CONSTRAINT IF EXISTS ck_simulation_runs_checksum,
    ADD  CONSTRAINT ck_simulation_runs_checksum
        CHECK (scenario_checksum IS NULL OR scenario_checksum ~ '^[0-9a-f]{64}$');

DO $$
BEGIN
    IF to_regclass('public.simulation_results') IS NOT NULL THEN
        UPDATE simulation_runs r
        SET    resumen = res.resumen,
               scenario_checksum = res.scenario_checksum,
               trazabilidad = res.trazabilidad
        FROM   simulation_results res
        WHERE  res.run_id = r.id AND r.resumen IS NULL;
    END IF;
END;
$$;

COMMENT ON COLUMN simulation_runs.resumen IS
    'Indicadores de la corrida completada, tal como los da motor.simular(): casos_acumulados, pico, dia_pico, hospitalizaciones, fallecimientos, tasa_ataque y desglose por grupo de edad. La serie diaria esta en MongoDB (series_corridas, D28).';
COMMENT ON COLUMN simulation_runs.trazabilidad IS
    'Parametros usados, con su fuente o su marca de supuesto, tal como los reporto el motor.';
COMMENT ON COLUMN simulation_runs.scenario_checksum IS
    'SHA-256 de la entrada canonica del motor. Misma huella + misma semilla + mismo engine_version => mismo resultado.';

-- El simulador cierra la corrida y, en el mismo UPDATE, guarda su resumen y la
-- version del motor que la corrio (la que reporta motor.simular()).
GRANT UPDATE (engine_version, resumen, scenario_checksum, trazabilidad)
    ON simulation_runs TO svc_simulador;

INSERT INTO schema_migrations (version, description)
VALUES ('038', 'Simulacion: resumen, huella y trazabilidad de la corrida en simulation_runs (D28)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
