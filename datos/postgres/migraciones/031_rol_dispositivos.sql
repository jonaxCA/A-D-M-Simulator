SET client_encoding = 'UTF8';
-- =============================================================================
-- 031_rol_dispositivos.sql
-- Un rol de PostgreSQL para el microservicio dispositivos (5223), dueño de devices, y la
-- lectura de devices que necesita casos para no aceptar un caso de un dispositivo ajeno o
-- revocado. Sigue el patrón de la 026 a la 030.
--
-- - El rol nace con LOGIN y sin contraseña. En el compose la fija
--   infra/postgres/10-inicializa.sh; fuera de él: ALTER ROLE svc_dispositivos PASSWORD '...';
--   y el servicio la recibe en su DATABASE_URL (ver infra/.env.example).
-- - dispositivos registra, actualiza y revoca, pero nunca borra un dispositivo ni le cambia
--   el dueño, el identificador o la plataforma: no tiene DELETE ni UPDATE sobre esas columnas.
-- - casos solo lee id, user_id e is_revoked, lo que necesita para decidir si acepta un
--   device_id. La 027 le revoca todo a svc_casos: si se vuelve a correr sola, hay que correr
--   esta después (el dump las corre en orden).
-- - No toca a epidemia_app ni a los roles app_* de la 009: el monolito sigue igual.
-- - Idempotente: cada corrida revoca y vuelve a otorgar exactamente lo de abajo.
-- =============================================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'svc_dispositivos') THEN
        CREATE ROLE svc_dispositivos LOGIN;
    END IF;
END;
$$;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM svc_dispositivos;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM svc_dispositivos;
GRANT USAGE ON SCHEMA public TO svc_dispositivos;

-- dispositivos: dueño de devices.
GRANT SELECT, INSERT ON devices TO svc_dispositivos;
GRANT UPDATE (model, app_version, push_token, is_revoked, last_seen_at) ON devices TO svc_dispositivos;
GRANT INSERT ON audit_log TO svc_dispositivos;

DO $$
DECLARE
    tabla TEXT;
    secuencia TEXT;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['devices', 'audit_log']
    LOOP
        secuencia := pg_get_serial_sequence('public.' || tabla, 'id');
        IF secuencia IS NOT NULL THEN
            EXECUTE format('GRANT USAGE ON SEQUENCE %s TO svc_dispositivos', secuencia);
        END IF;
    END LOOP;
END;
$$;

-- casos: de quién es un dispositivo y si está revocado.
REVOKE ALL ON devices FROM svc_casos;
GRANT SELECT (id, user_id, is_revoked) ON devices TO svc_casos;

COMMENT ON ROLE svc_dispositivos IS 'Microservicio dispositivos (5223): duenio de devices.';

INSERT INTO schema_migrations (version, description)
VALUES ('031', 'Seguridad: rol de dispositivos y lectura de devices para casos')
ON CONFLICT (version) DO NOTHING;

COMMIT;
