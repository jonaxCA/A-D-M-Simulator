SET client_encoding = 'UTF8';
-- =============================================================================
-- 034_permisos_d1_y_reportes.sql
-- Permisos de D1 y D35 sobre la matriz de la 010 (que no se edita).
--
-- - scenarios.approve (nuevo): aprobar o rechazar una version. EPIDEMIOLOGO y
--   ADMINISTRADOR; ninguno revisa la suya (ck_scenario_versions_no_autoaprobacion).
-- - reports.upload (nuevo): subir el reporte de una comparacion. ANALISTA y
--   ADMINISTRADOR (D35).
-- - audit.read sale del EPIDEMIOLOGO: la bitacora es solo del ADMINISTRADOR (RF-L05).
-- - cases.create sale del ADMINISTRADOR: solo el CAPTURISTA captura (D1, 2026-11-17).
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

-- La 002 no tenia la accion 'upload'.
ALTER TABLE permissions DROP CONSTRAINT IF EXISTS ck_permissions_accion;
ALTER TABLE permissions ADD CONSTRAINT ck_permissions_accion CHECK (action IN
    ('read', 'create', 'update', 'delete', 'publish', 'run', 'export', 'approve', 'upload'));

INSERT INTO permissions (code, resource, action, description) VALUES
    ('scenarios.approve', 'scenarios', 'approve', 'Aprobar o rechazar una version de escenario.'),
    ('reports.upload',    'reports',   'upload',  'Subir el reporte de una comparacion.')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r JOIN permissions p ON p.code = 'scenarios.approve'
WHERE r.code IN ('EPIDEMIOLOGO', 'ADMINISTRADOR')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r JOIN permissions p ON p.code = 'reports.upload'
WHERE r.code IN ('ANALISTA', 'ADMINISTRADOR')
ON CONFLICT DO NOTHING;

DELETE FROM role_permissions rp
USING roles r, permissions p
WHERE rp.role_id = r.id AND rp.permission_id = p.id
  AND ((r.code = 'EPIDEMIOLOGO' AND p.code = 'audit.read')
    OR (r.code = 'ADMINISTRADOR' AND p.code = 'cases.create'));

INSERT INTO schema_migrations (version, description)
VALUES ('034', 'Permisos de D1 y D35: scenarios.approve y reports.upload; audit.read solo ADMINISTRADOR; cases.create sin ADMINISTRADOR')
ON CONFLICT (version) DO NOTHING;

COMMIT;
