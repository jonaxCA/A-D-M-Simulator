SET client_encoding = 'UTF8';
-- =============================================================================
-- 037_avisos_de_casos_y_revision.sql
-- Tres tipos de aviso nuevos y el permiso para avisar a un rol (bloque E1).
--
--   NEW_CASES          sincronizacion: un lote trajo casos nuevos (D32, RF-C19)
--   SCENARIO_SUBMITTED aprobacion: una versión espera revisión (RF-D15)
--   SCENARIO_REJECTED  aprobacion: se rechazó la versión de su autor (RF-D16)
--
-- - notificaciones crea un aviso por cada persona activa con un rol (los
--   EPIDEMIOLOGO), así que su rol lee users, user_roles y roles, solo las
--   columnas que necesita.
-- - La 036 está reservada para otro cambio.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

ALTER TABLE notifications DROP CONSTRAINT IF EXISTS ck_notifications_type;
ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type CHECK (type IN
    ('RUN_FINISHED', 'RUN_FAILED', 'THRESHOLD_EXCEEDED', 'ASSIGNMENT',
     'SCENARIO_PUBLISHED', 'SCENARIO_APPROVED', 'SCENARIO_SUBMITTED',
     'SCENARIO_REJECTED', 'NEW_CASES', 'SYSTEM'));

COMMENT ON COLUMN notifications.type IS
    'Tipo: RUN_FINISHED, RUN_FAILED, THRESHOLD_EXCEEDED, ASSIGNMENT, SCENARIO_PUBLISHED, SCENARIO_APPROVED, SCENARIO_SUBMITTED, SCENARIO_REJECTED, NEW_CASES o SYSTEM.';

GRANT SELECT (id, is_active) ON users TO svc_notificaciones;
GRANT SELECT (user_id, role_id) ON user_roles TO svc_notificaciones;
GRANT SELECT (id, code) ON roles TO svc_notificaciones;

INSERT INTO schema_migrations (version, description)
VALUES ('037', 'Avisos: NEW_CASES, SCENARIO_SUBMITTED y SCENARIO_REJECTED; notificaciones lee los roles')
ON CONFLICT (version) DO NOTHING;

COMMIT;
