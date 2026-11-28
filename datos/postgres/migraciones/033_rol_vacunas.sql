SET client_encoding = 'UTF8';
-- =============================================================================
-- 033_rol_vacunas.sql
-- Un rol de PostgreSQL para el microservicio vacunas (5225), dueño de vaccine_lots: los
-- lotes que la app móvil lee por QR o código de barras y las dosis que se les aplican.
-- Sigue el patrón de la 026 a la 032.
--
-- - El rol nace con LOGIN y sin contraseña. En el compose la fija
--   infra/postgres/10-inicializa.sh; fuera de él: ALTER ROLE svc_vacunas PASSWORD '...';
--   y el servicio la recibe en su DATABASE_URL (ver infra/.env.example).
-- - De un lote ya registrado solo cambia doses_used, al aplicar dosis; nunca lo borra. El
--   tope lo garantiza ck_vaccine_lots_usadas (005), además del UPDATE condicionado.
-- - Lee el nombre de la enfermedad y de la región para responder con ellos.
-- - No liga dosis a casos: cases.vaccine_lot_id es de casos.
-- - No toca a epidemia_app ni a los roles app_* de la 009: el monolito sigue igual.
-- - Idempotente: cada corrida revoca y vuelve a otorgar exactamente lo de abajo.
-- =============================================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'svc_vacunas') THEN
        CREATE ROLE svc_vacunas LOGIN;
    END IF;
END;
$$;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM svc_vacunas;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM svc_vacunas;
GRANT USAGE ON SCHEMA public TO svc_vacunas;

GRANT SELECT, INSERT ON vaccine_lots TO svc_vacunas;
GRANT UPDATE (doses_used) ON vaccine_lots TO svc_vacunas;
GRANT SELECT (id, name) ON diseases, regions TO svc_vacunas;
GRANT INSERT ON audit_log TO svc_vacunas;

DO $$
DECLARE
    tabla TEXT;
    secuencia TEXT;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['vaccine_lots', 'audit_log']
    LOOP
        secuencia := pg_get_serial_sequence('public.' || tabla, 'id');
        IF secuencia IS NOT NULL THEN
            EXECUTE format('GRANT USAGE ON SEQUENCE %s TO svc_vacunas', secuencia);
        END IF;
    END LOOP;
END;
$$;

COMMENT ON ROLE svc_vacunas IS 'Microservicio vacunas (5225): duenio de vaccine_lots.';

INSERT INTO schema_migrations (version, description)
VALUES ('033', 'Seguridad: rol de PostgreSQL de vacunas')
ON CONFLICT (version) DO NOTHING;

COMMIT;
