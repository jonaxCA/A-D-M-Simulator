-- =============================================================================
-- 026_roles_por_servicio.sql
-- Un rol de PostgreSQL por microservicio del grupo de las 14:00 (bloque L).
--
-- Cada servicio se conecta con su propio rol y solo puede escribir lo que el
-- catálogo (docs/arquitectura/microservicios.md) dice que escribe. Lee únicamente
-- las tablas que consultan sus funciones de backend_web.
--
-- - Los roles nacen con LOGIN y sin contraseña. La contraseña se fija fuera del
--   repositorio: ALTER ROLE svc_regiones PASSWORD '...'; y el servicio la recibe
--   en su DATABASE_URL (ver .env.example).
-- - No toca a epidemia_app ni a los roles app_* de la 009: el monolito sigue igual.
-- - Idempotente: cada corrida revoca y vuelve a otorgar exactamente lo de abajo.
-- - SELECT ... FOR UPDATE exige UPDATE en alguna columna; por eso quien bloquea
--   filas tiene UPDATE de las columnas que escribe y nada más.
-- =============================================================================

BEGIN;

DO $$
DECLARE
    r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY[
        'svc_auth', 'svc_sesiones', 'svc_usuarios', 'svc_roles',
        'svc_enfermedades', 'svc_parametros', 'svc_regiones', 'svc_poblacion',
        'svc_tipos_intervencion', 'svc_indicadores', 'svc_series', 'svc_zonas'
    ]
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('CREATE ROLE %I LOGIN', r);
        END IF;
        EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', r);
        EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', r);
        EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', r);
    END LOOP;
END;
$$;

-- -----------------------------------------------------------------------------
-- Identidad
-- -----------------------------------------------------------------------------
-- auth: attempt_login lee la cuenta y sus roles, y actualiza intentos fallidos,
-- bloqueo y último acceso en users. Audita LOGIN y LOGIN_FAILED.
GRANT SELECT ON users, roles, user_roles TO svc_auth;
GRANT UPDATE (failed_attempts, last_login_at) ON users TO svc_auth
GRANT INSERT ON audit_log TO svc_auth;

-- sesiones: vive en Redis; solo audita LOGOUT.
GRANT INSERT ON audit_log TO svc_sesiones;

-- usuarios: dueño de users. Lee los roles para la ficha y, para revisar
-- dependencias antes de borrar, cada tabla con llave foránea hacia users
-- (bloque DO de abajo).
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO svc_usuarios;
GRANT SELECT ON roles, user_roles TO svc_usuarios;
GRANT INSERT ON audit_log TO svc_usuarios;

DO $$
DECLARE
    t REGCLASS;
BEGIN
    FOR t IN
        SELECT DISTINCT c.conrelid::regclass
        FROM pg_constraint c
        WHERE c.contype = 'f' AND c.confrelid = 'public.users'::regclass
    LOOP
        EXECUTE format('GRANT SELECT ON %s TO svc_usuarios', t);
    END LOOP;
END;
$$;

-- roles: dueño de user_roles (un rol por cuenta: DELETE + INSERT).
GRANT SELECT ON users, roles, permissions, role_permissions TO svc_roles;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_roles TO svc_roles;
GRANT INSERT ON audit_log TO svc_roles;

-- -----------------------------------------------------------------------------
-- Catálogos
-- -----------------------------------------------------------------------------
-- enfermedades: todo diseases menos default_params. El alta inserta
-- default_params = '{}' explícitamente, así que el INSERT lo incluye; editarlo
-- después es solo de parametros.
GRANT SELECT ON diseases, cases, regions TO svc_enfermedades;
GRANT INSERT (code, name, description, default_params) ON diseases TO svc_enfermedades;
GRANT UPDATE (name, description, is_active) ON diseases TO svc_enfermedades;
GRANT INSERT ON audit_log TO svc_enfermedades;

-- parametros: solo la columna default_params.
GRANT SELECT ON diseases TO svc_parametros;
GRANT UPDATE (default_params) ON diseases TO svc_parametros;
GRANT INSERT ON audit_log TO svc_parametros;

-- regiones: solo lectura. La fuente de cada cifra sale de los ajustes manuales
-- y de la última corrección de bandas en audit_log, con el nombre de quien la hizo.
GRANT SELECT ON regions, region_age_groups, region_population_adjustments TO svc_regiones;
GRANT SELECT (id, full_name) ON users TO svc_regiones;
GRANT SELECT (id, user_id, entity_type, entity_id, data_after, occurred_at) ON audit_log TO svc_regiones;

-- poblacion: corrige la población del municipio y recalcula la del estado;
-- population_60plus la deriva el trigger de la 022, que corre con los
-- permisos de este rol.
GRANT SELECT ON regions, region_age_groups, region_population_adjustments TO svc_poblacion;
GRANT UPDATE (population, population_60plus) ON regions TO svc_poblacion;
GRANT UPDATE (population) ON region_age_groups TO svc_poblacion;
GRANT INSERT, UPDATE ON region_population_adjustments TO svc_poblacion;
GRANT INSERT ON audit_log TO svc_poblacion;

-- tipos-intervencion: catálogo de solo lectura.
GRANT SELECT ON intervention_types TO svc_tipos_intervencion;

-- -----------------------------------------------------------------------------
-- Analítica (solo lectura)
-- -----------------------------------------------------------------------------
GRANT SELECT ON cases, regions, diseases, simulation_runs TO svc_indicadores;
GRANT SELECT ON cases, regions, diseases TO svc_series;
GRANT SELECT ON cases, regions, diseases TO svc_zonas;

-- -----------------------------------------------------------------------------
-- Secuencias de las tablas donde se inserta
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    par TEXT[];
    secuencia TEXT;
BEGIN
    FOREACH par SLICE 1 IN ARRAY ARRAY[
        ['svc_auth', 'audit_log'], ['svc_sesiones', 'audit_log'],
        ['svc_usuarios', 'audit_log'], ['svc_usuarios', 'users'],
        ['svc_roles', 'audit_log'], ['svc_roles', 'user_roles'],
        ['svc_enfermedades', 'audit_log'], ['svc_enfermedades', 'diseases'],
        ['svc_parametros', 'audit_log'],
        ['svc_poblacion', 'audit_log'], ['svc_poblacion', 'region_population_adjustments']
    ]
    LOOP
        secuencia := NULL;
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = par[2] AND column_name = 'id') THEN
            secuencia := pg_get_serial_sequence('public.' || par[2], 'id');
        END IF;
        IF secuencia IS NOT NULL THEN
            EXECUTE format('GRANT USAGE ON SEQUENCE %s TO %I', secuencia, par[1]);
        END IF;
    END LOOP;
END;
$$;

COMMENT ON ROLE svc_auth IS 'Microservicio auth (5201): lee cuentas y roles; actualiza intentos y ultimo acceso en users.';
COMMENT ON ROLE svc_sesiones IS 'Microservicio sesiones (5202): sesiones en Redis; solo inserta en audit_log.';
COMMENT ON ROLE svc_usuarios IS 'Microservicio usuarios (5203): duenio de users.';
COMMENT ON ROLE svc_roles IS 'Microservicio roles (5204): duenio de user_roles.';
COMMENT ON ROLE svc_enfermedades IS 'Microservicio enfermedades (5211): diseases menos default_params.';
COMMENT ON ROLE svc_parametros IS 'Microservicio parametros (5212): solo diseases.default_params.';
COMMENT ON ROLE svc_regiones IS 'Microservicio regiones (5213): solo lectura.';
COMMENT ON ROLE svc_poblacion IS 'Microservicio poblacion (5214): regions.population, region_age_groups y region_population_adjustments.';
COMMENT ON ROLE svc_tipos_intervencion IS 'Microservicio tipos-intervencion (5215): solo lectura.';
COMMENT ON ROLE svc_indicadores IS 'Microservicio indicadores (5251): solo lectura.';
COMMENT ON ROLE svc_series IS 'Microservicio series (5252): solo lectura.';
COMMENT ON ROLE svc_zonas IS 'Microservicio zonas (5253): solo lectura.';

INSERT INTO schema_migrations (version, description)
VALUES ('026', 'Seguridad: un rol de PostgreSQL por microservicio del grupo 14:00')
ON CONFLICT (version) DO NOTHING;

COMMIT;
