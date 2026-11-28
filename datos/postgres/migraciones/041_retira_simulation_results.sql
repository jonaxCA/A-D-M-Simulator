SET client_encoding = 'UTF8';
-- =============================================================================
-- 041_retira_simulation_results.sql
-- Retira simulation_results (D28).
--
-- - D28: la serie diaria de cada corrida esta en MongoDB (series_corridas) y su
--   resumen, huella y trazabilidad, en simulation_runs (038). Nadie la escribe
--   ni la lee: ni el simulador, ni resultados, ni pareto, ni la web.
-- - La 038 ya copio a simulation_runs el resumen de las corridas que hubiera.
--   La serie de esas corridas se pierde con la tabla; se recupera volviendo a
--   correrlas con la misma semilla.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS simulation_results;

INSERT INTO schema_migrations (version, description)
VALUES ('041', 'Simulacion: retira simulation_results; la serie esta en MongoDB y el resumen en simulation_runs (D28)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
