SET client_encoding = 'UTF8';
-- =============================================================================
-- 046_bitacora_de_servicios.sql
-- La bitácora deja de pasar por la web (D36).
--
-- - Un servicio que responde 403 anota PERMISSION_DENIED (RF-A05; antes lo hacía
--   la web). Los diez roles que no escribían en audit_log reciben INSERT, igual
--   que los demás: audit_log es de todos, pero solo para insertar.
-- - La consulta de la bitácora es del servicio roles (D37, E7): su rol lee
--   audit_log (svc_usuarios ya la leía, desde la 026, para las dependencias de
--   una cuenta).
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

GRANT INSERT ON audit_log TO svc_comparacion, svc_estado_servicios, svc_indicadores,
    svc_pareto, svc_regiones, svc_resultados, svc_series, svc_tipos_intervencion,
    svc_validacion, svc_zonas;
GRANT USAGE ON SEQUENCE audit_log_id_seq TO svc_comparacion, svc_estado_servicios,
    svc_indicadores, svc_pareto, svc_regiones, svc_resultados, svc_series,
    svc_tipos_intervencion, svc_validacion, svc_zonas;

GRANT SELECT ON audit_log TO svc_roles;

INSERT INTO schema_migrations (version, description)
VALUES ('046', 'Bitacora: INSERT en audit_log para los diez roles que no lo tenian y lectura para svc_roles (D36, D37)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
