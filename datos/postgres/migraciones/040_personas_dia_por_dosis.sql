SET client_encoding = 'UTF8';
-- =============================================================================
-- 040_personas_dia_por_dosis.sql
-- Lugar para el factor de personas-día por dosis de la frontera de Pareto (D3).
--
-- - D3: la frontera usa personas-día y los pesos van aparte. Las capas y el
--   testeo cuentan sus personas-día por definición (habitante-día); la
--   vacunación necesita un factor por dosis, que es un supuesto.
-- - Mismas reglas que unit_cost (014): sin valor por omisión (regla 8) y, si se
--   captura, con fuente o marcado como supuesto. Ninguna fila trae valor.
-- - Lo fija el servicio intervenciones (PUT .../person-days), así que su rol
--   puede actualizar estas tres columnas.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

ALTER TABLE intervention_types
    ADD COLUMN IF NOT EXISTS person_days_per_unit      NUMERIC(12,4),
    ADD COLUMN IF NOT EXISTS person_days_source        TEXT,
    ADD COLUMN IF NOT EXISTS person_days_is_assumption BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE intervention_types
    DROP CONSTRAINT IF EXISTS ck_intervention_types_person_days,
    ADD  CONSTRAINT ck_intervention_types_person_days CHECK (
        person_days_per_unit IS NULL
        OR (person_days_per_unit >= 0
            AND (person_days_is_assumption OR person_days_source IS NOT NULL))
    );

COMMENT ON COLUMN intervention_types.person_days_per_unit IS
    'Personas-dia que cuenta cada unidad en la frontera de Pareto (D3). Solo la usan los tipos por_dosis (vacunacion). NULL = sin capturar: una comparacion con ese tipo no se calcula.';
COMMENT ON COLUMN intervention_types.person_days_source IS
    'De donde salio el factor. Obligatoria si no esta marcado como supuesto.';
COMMENT ON COLUMN intervention_types.person_days_is_assumption IS
    'TRUE si el factor es un supuesto del equipo y no un dato con respaldo.';

GRANT UPDATE (person_days_per_unit, person_days_source, person_days_is_assumption)
    ON intervention_types TO svc_intervenciones;

INSERT INTO schema_migrations (version, description)
VALUES ('040', 'Pareto: personas-dia por dosis en intervention_types (D3)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
