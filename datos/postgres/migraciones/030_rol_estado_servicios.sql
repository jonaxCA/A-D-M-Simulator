-- =============================================================================
-- 030_rol_estado_servicios.sql
-- Un rol de PostgreSQL para el microservicio estado-servicios (bloque L).
-- Sigue el patrón de la 026 a la 029.
--
-- No lee ni escribe ninguna tabla: sondea el /health de los demás servicios y guarda lo
-- que ve en Redis. Solo se conecta para su propio /health, que hace SELECT 1, y para eso
-- basta el CONNECT que PUBLIC tiene sobre la base. Por eso no recibe ningún GRANT.
-- - El rol nace con LOGIN y sin contraseña. En el compose la fija
--   infra/postgres/10-inicializa.sh; fuera de él: ALTER ROLE svc_estado_servicios PASSWORD '...';
--   y el servicio la recibe en su DATABASE_URL (ver infra/.env.example).
-- - No toca a epidemia_app ni a los roles app_* de la 009: el monolito sigue igual.
-- - Idempotente: cada corrida le revoca lo que alguien le hubiera dado a mano.
-- =============================================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'svc_estado_servicios') THEN
        CREATE ROLE svc_estado_servicios LOGIN;
    END IF;
END;
$$;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM svc_estado_servicios;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM svc_estado_servicios;

COMMENT ON ROLE svc_estado_servicios IS 'Microservicio estado-servicios (5262): solo se conecta; no lee ni escribe tablas.';

INSERT INTO schema_migrations (version, description)
VALUES ('030', 'Seguridad: rol de PostgreSQL de estado-servicios')
ON CONFLICT (version) DO NOTHING;

COMMIT;
