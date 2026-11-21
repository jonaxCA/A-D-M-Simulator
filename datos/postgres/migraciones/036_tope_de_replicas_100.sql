SET client_encoding = 'UTF8';
-- =============================================================================
-- 036_tope_de_replicas_100.sql
-- El tope de réplicas de un lote baja de 200 a 100 (D8, RF-E03).
--
-- - D8: el escritorio ya topa en 100 y la base aceptaba 200; se documenta 100.
-- - Cambia el CHECK de simulation_batches.replicas (esquema, 014) y el valor de
--   max_replicas_por_lote en system_settings (dato, 010).
-- - Los lotes que existen tienen 1 réplica, así que el CHECK nuevo los acepta.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

ALTER TABLE simulation_batches
    DROP CONSTRAINT IF EXISTS ck_simulation_batches_replicas,
    ADD  CONSTRAINT ck_simulation_batches_replicas
        CHECK (replicas BETWEEN 1 AND 100);

UPDATE system_settings
   SET value = '100'::jsonb
 WHERE key = 'max_replicas_por_lote'
   AND value <> '100'::jsonb;

INSERT INTO schema_migrations (version, description)
VALUES ('036', 'Simulacion: el tope de replicas por lote baja de 200 a 100 (D8)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
