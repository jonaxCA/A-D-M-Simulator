SET client_encoding = 'UTF8';
-- =============================================================================
-- 044_ajustes_de_parametros_por_version.sql
-- Dominio: escenarios y parámetros. Ajustes de los parámetros de la enfermedad
-- en una versión de escenario (D59, A4 «Configuración del modelo»).
--
-- - scenario_versions.param_overrides: los parámetros que esa versión cambia
--   respecto del catálogo, cada uno con su fuente o la marca de supuesto. Solo
--   se edita en borrador (lo exige el servicio parametros). Al enviar la versión
--   a revisión, disease_params (024) congela el catálogo con estos ajustes
--   encima: los parámetros efectivos de una versión son
--   coalesce(disease_params, default_params || param_overrides).
-- - svc_parametros recibe lo mínimo para leer la versión y su escenario y para
--   escribir los ajustes; las demás lecturas de scenario_versions ya son de
--   tabla completa (027, 028, 029) y ven la columna nueva.
-- - Es la 044, de la reserva de D. Idempotente (D7).
-- =============================================================================

BEGIN;

ALTER TABLE scenario_versions
    ADD COLUMN IF NOT EXISTS param_overrides JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE scenario_versions
    DROP CONSTRAINT IF EXISTS ck_scenario_versions_ajustes,
    ADD  CONSTRAINT ck_scenario_versions_ajustes CHECK (jsonb_typeof(param_overrides) = 'object');

COMMENT ON COLUMN scenario_versions.param_overrides IS
    'Parámetros de la enfermedad que esta versión ajusta respecto del catálogo (D59): {clave: {valor, fuente, supuesto, intervalo?}}. Solo se editan en borrador; al enviarla, disease_params congela el catálogo con estos ajustes encima. Vacío si la versión usa el catálogo tal cual.';

GRANT SELECT (id, scenario_id, version_number, status, is_current, disease_params, param_overrides)
    ON scenario_versions TO svc_parametros;
GRANT SELECT (id, owner_id, disease_id, region_id, status) ON scenarios TO svc_parametros;
GRANT UPDATE (param_overrides) ON scenario_versions TO svc_parametros;

INSERT INTO schema_migrations (version, description)
VALUES ('044', 'Ajustes de los parámetros de la enfermedad por versión de escenario (D59)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
