SET client_encoding = 'UTF8';
-- =============================================================================
-- 055_historial_con_alcance.sql
-- El historial de un escenario aplica el alcance por región (D43).
--
-- - svc_roles lee scenarios, scenario_versions y scenario_interventions solo para
--   saber la región de la entidad cuyo historial se consulta.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

GRANT SELECT ON scenarios, scenario_versions, scenario_interventions TO svc_roles;

INSERT INTO schema_migrations (version, description)
VALUES ('055', 'Identidad: svc_roles lee escenarios para aplicar el alcance regional al historial (D43)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
