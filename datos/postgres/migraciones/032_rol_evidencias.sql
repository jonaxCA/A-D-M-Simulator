SET client_encoding = 'UTF8';
-- =============================================================================
-- 032_rol_evidencias.sql
-- Un rol de PostgreSQL para el microservicio evidencias (5224), dueño de
-- case_attachments. Sigue el patrón de la 026 a la 031.
--
-- - El rol nace con LOGIN y sin contraseña. En el compose la fija
--   infra/postgres/10-inicializa.sh; fuera de él: ALTER ROLE svc_evidencias PASSWORD '...';
--   y el servicio la recibe en su DATABASE_URL (ver infra/.env.example).
-- - El archivo vive en el volumen del servicio, no en la base: case_attachments guarda su
--   ruta, tipo, tamaño y huella. Una evidencia no se edita: se sube o, solo ADMINISTRADOR,
--   se borra. Por eso no recibe UPDATE.
-- - De cases solo lee id y reported_by: si el caso existe y quién lo reportó, que es quien
--   puede adjuntarle fotos (además de ADMINISTRADOR).
-- - No toca a epidemia_app ni a los roles app_* de la 009: el monolito sigue igual.
-- - Idempotente: cada corrida revoca y vuelve a otorgar exactamente lo de abajo.
-- =============================================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'svc_evidencias') THEN
        CREATE ROLE svc_evidencias LOGIN;
    END IF;
END;
$$;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM svc_evidencias;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM svc_evidencias;
GRANT USAGE ON SCHEMA public TO svc_evidencias;

GRANT SELECT, INSERT, DELETE ON case_attachments TO svc_evidencias;
GRANT SELECT (id, reported_by) ON cases TO svc_evidencias;
GRANT INSERT ON audit_log TO svc_evidencias;

DO $$
DECLARE
    tabla TEXT;
    secuencia TEXT;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['case_attachments', 'audit_log']
    LOOP
        secuencia := pg_get_serial_sequence('public.' || tabla, 'id');
        IF secuencia IS NOT NULL THEN
            EXECUTE format('GRANT USAGE ON SEQUENCE %s TO svc_evidencias', secuencia);
        END IF;
    END LOOP;
END;
$$;

COMMENT ON ROLE svc_evidencias IS 'Microservicio evidencias (5224): duenio de case_attachments.';

INSERT INTO schema_migrations (version, description)
VALUES ('032', 'Seguridad: rol de PostgreSQL de evidencias')
ON CONFLICT (version) DO NOTHING;

COMMIT;
