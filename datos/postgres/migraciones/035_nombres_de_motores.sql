SET client_encoding = 'UTF8';
-- =============================================================================
-- 035_nombres_de_motores.sql
-- Los motores cambian de nombre (D2): el SEIR queda como control experimental
-- y los dos ABM se nombran por lo que son.
--
--   python-ref -> seir-ref    SEIR estocástico por edad (procesamiento/motor)
--   numba      -> abm-ref     ABM en Python, en CPU
--   cuda       -> abm-gpu     ABM en FLAME GPU 2
--
-- - La 034 queda reservada para D1 (permisos y auditoría).
-- - El CHECK de la 014 tiene los nombres fijos. El orden es el de D2: soltar el
--   CHECK, convertir los valores, poner el CHECK nuevo y cambiar el DEFAULT.
-- - engine_version de las corridas que ya existen (python-ref-0.1) no se toca:
--   registra qué versión del motor produjo cada resultado. seir-ref-0.1 es el
--   mismo código con otro nombre.
-- - motor_por_defecto (010) se traduce igual. Ningún código lo lee hoy.
-- - La cola de Redis también cambia de llave (queue:simulaciones:<motor>): una
--   corrida que esté esperando en la llave vieja al desplegar no la toma nadie.
--   Se despliega con la cola vacía.
-- - Idempotente (D7): correrla dos veces no cambia nada.
-- =============================================================================

BEGIN;

ALTER TABLE simulation_batches DROP CONSTRAINT IF EXISTS ck_simulation_batches_engine;

UPDATE simulation_batches
   SET engine = CASE engine
                    WHEN 'python-ref' THEN 'seir-ref'
                    WHEN 'numba'      THEN 'abm-ref'
                    WHEN 'cuda'       THEN 'abm-gpu'
                END
 WHERE engine IN ('python-ref', 'numba', 'cuda');

ALTER TABLE simulation_batches
    ADD CONSTRAINT ck_simulation_batches_engine
        CHECK (engine IN ('seir-ref', 'abm-ref', 'abm-gpu'));

ALTER TABLE simulation_batches ALTER COLUMN engine SET DEFAULT 'seir-ref';

COMMENT ON COLUMN simulation_batches.engine IS
    'Motor que corre el lote (D2): seir-ref, abm-ref o abm-gpu.';

UPDATE system_settings
   SET value = CASE value #>> '{}'
                   WHEN 'python-ref' THEN '"seir-ref"'::jsonb
                   WHEN 'numba'      THEN '"abm-ref"'::jsonb
                   WHEN 'cuda'       THEN '"abm-gpu"'::jsonb
               END
 WHERE key = 'motor_por_defecto'
   AND value #>> '{}' IN ('python-ref', 'numba', 'cuda');

INSERT INTO schema_migrations (version, description)
VALUES ('035', 'Simulacion: nombres de motores seir-ref, abm-ref y abm-gpu (D2)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
