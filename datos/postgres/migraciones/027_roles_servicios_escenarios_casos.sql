-- =============================================================================
-- 027_roles_servicios_escenarios_casos.sql
-- Un rol de PostgreSQL por microservicio de escenarios y de captura de casos
-- (escenarios, intervenciones, validacion, aprobacion, escenarios-xml, casos y
-- sincronizacion). Sigue el patrón de la 026.
--
-- Cada servicio se conecta con su propio rol y solo puede escribir lo que el
-- catálogo (docs/arquitectura/microservicios.md) dice que escribe. Lee únicamente
-- las tablas que consultan sus rutas y las funciones de backend_web que llaman.
--
-- - Los roles nacen con LOGIN y sin contraseña. La contraseña se fija fuera del
--   repositorio: ALTER ROLE svc_escenarios PASSWORD '...'; y el servicio la recibe
--   en su DATABASE_URL (ver infra/.env.example).
-- - No toca a epidemia_app ni a los roles app_* de la 009: el monolito sigue igual.
-- - Idempotente: cada corrida revoca y vuelve a otorgar exactamente lo de abajo.
-- - SELECT ... FOR UPDATE exige UPDATE en alguna columna; por eso quien bloquea
--   filas tiene UPDATE de las columnas que escribe y nada más.
-- - Las llaves foráneas (cases.device_id, scenario_versions.created_by, etc.) las
--   revisa PostgreSQL con los permisos del dueño de la tabla, así que no piden
--   SELECT sobre devices ni users.
-- =============================================================================

BEGIN;

DO $$
DECLARE
    r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY[
        'svc_escenarios', 'svc_intervenciones', 'svc_validacion', 'svc_aprobacion',
        'svc_escenarios_xml', 'svc_casos', 'svc_sincronizacion'
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
-- Escenarios
-- -----------------------------------------------------------------------------
-- escenarios: alta (scenarios + versión 1), versión siguiente (apaga is_current de
-- la anterior) y duplicado, que copia las intervenciones de la versión origen.
-- Lee los catálogos para validar y el nombre de quien arma cada versión.
GRANT SELECT ON scenarios, scenario_versions, scenario_interventions, intervention_types,
                diseases, regions, region_age_groups TO svc_escenarios;
GRANT SELECT (id, full_name) ON users TO svc_escenarios;
GRANT INSERT ON scenarios, scenario_versions, scenario_interventions TO svc_escenarios;
GRANT UPDATE (is_current) ON scenario_versions TO svc_escenarios;
GRANT INSERT ON audit_log TO svc_escenarios;

-- intervenciones: dueño de scenario_interventions (alta, baja, orden). El costo
-- unitario vive en el tipo de intervención (como en el monolito): solo esas tres
-- columnas de intervention_types.
GRANT SELECT ON scenarios, scenario_versions, intervention_types TO svc_intervenciones;
GRANT SELECT, INSERT, UPDATE, DELETE ON scenario_interventions TO svc_intervenciones;
GRANT UPDATE (unit_cost, cost_source, cost_is_assumption) ON intervention_types TO svc_intervenciones;
GRANT INSERT ON audit_log TO svc_intervenciones;

-- validacion: solo lectura. No guarda nada ni audita.
GRANT SELECT ON scenarios, scenario_versions, scenario_interventions, intervention_types,
                diseases, regions, region_age_groups TO svc_validacion;
GRANT SELECT (id, full_name) ON users TO svc_validacion;

-- aprobacion: pasa la versión a revisión (congela diseases.default_params en
-- disease_params) y la aprueba o rechaza. Lee el escenario completo para la bandeja.
GRANT SELECT ON scenarios, scenario_versions, scenario_interventions, intervention_types,
                diseases, regions TO svc_aprobacion;
GRANT SELECT (id, full_name) ON users TO svc_aprobacion;
GRANT UPDATE (status, submitted_at, disease_params, reviewed_by, reviewed_at, review_comment)
    ON scenario_versions TO svc_aprobacion;
GRANT INSERT ON audit_log TO svc_aprobacion;

-- escenarios-xml: solo lee para exportar y resolver códigos; audita EXPORT.
-- Importar no escribe tablas: llama a escenarios e intervenciones.
GRANT SELECT ON scenarios, scenario_versions, scenario_interventions, intervention_types,
                diseases, regions TO svc_escenarios_xml;
GRANT INSERT ON audit_log TO svc_escenarios_xml;

-- -----------------------------------------------------------------------------
-- Captura de casos
-- -----------------------------------------------------------------------------
-- casos: dueño de cases. Lee diseases y regions para los catálogos de captura y
-- para armar la respuesta.
GRANT SELECT, INSERT ON cases TO svc_casos;
GRANT SELECT ON diseases, regions TO svc_casos;
GRANT INSERT ON audit_log TO svc_casos;

-- sincronizacion: el lote vive en Redis y los casos los escribe casos por HTTP;
-- solo audita el SYNC de cada lote.
GRANT INSERT ON audit_log TO svc_sincronizacion;

-- -----------------------------------------------------------------------------
-- Secuencias de las tablas donde se inserta
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    par TEXT[];
    secuencia TEXT;
BEGIN
    FOREACH par SLICE 1 IN ARRAY ARRAY[
        ['svc_escenarios', 'audit_log'], ['svc_escenarios', 'scenarios'],
        ['svc_escenarios', 'scenario_versions'], ['svc_escenarios', 'scenario_interventions'],
        ['svc_intervenciones', 'audit_log'], ['svc_intervenciones', 'scenario_interventions'],
        ['svc_aprobacion', 'audit_log'],
        ['svc_escenarios_xml', 'audit_log'],
        ['svc_casos', 'audit_log'], ['svc_casos', 'cases'],
        ['svc_sincronizacion', 'audit_log']
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

COMMENT ON ROLE svc_escenarios IS 'Microservicio escenarios: scenarios, scenario_versions y copia de intervenciones al duplicar.';
COMMENT ON ROLE svc_intervenciones IS 'Microservicio intervenciones: scenario_interventions y las columnas de costo de intervention_types.';
COMMENT ON ROLE svc_validacion IS 'Microservicio validacion: solo lectura.';
COMMENT ON ROLE svc_aprobacion IS 'Microservicio aprobacion: estado y revision de scenario_versions.';
COMMENT ON ROLE svc_escenarios_xml IS 'Microservicio escenarios-xml: solo lectura y bitacora de EXPORT.';
COMMENT ON ROLE svc_casos IS 'Microservicio casos: duenio de cases.';
COMMENT ON ROLE svc_sincronizacion IS 'Microservicio sincronizacion: lotes en Redis; solo inserta en audit_log.';

INSERT INTO schema_migrations (version, description)
VALUES ('027', 'Seguridad: un rol de PostgreSQL por microservicio de escenarios y casos')
ON CONFLICT (version) DO NOTHING;

COMMIT;
