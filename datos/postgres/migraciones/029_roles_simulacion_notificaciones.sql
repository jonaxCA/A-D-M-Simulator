SET client_encoding = 'UTF8';
-- =============================================================================
-- 029_roles_simulacion_notificaciones.sql
-- Un rol de PostgreSQL para los microservicios corridas, simulador, resultados y
-- notificaciones (bloque L), y el tipo de aviso SCENARIO_APPROVED. Sigue el patrón
-- de la 026 a la 028.
--
-- - Los roles nacen con LOGIN y sin contraseña. En el compose la fija
--   infra/postgres/10-inicializa.sh; fuera de él: ALTER ROLE svc_corridas PASSWORD '...';
--   y el servicio la recibe en su DATABASE_URL (ver infra/.env.example).
-- - No toca a epidemia_app ni a los roles app_* de la 009: el monolito sigue igual.
-- - Idempotente: cada corrida revoca y vuelve a otorgar exactamente lo de abajo.
-- - simulation_runs.status lo cambian corridas (cancelar una encolada) y simulador
--   (ejecutarla), las dos con la transición condicionada (WHERE status = ...). Las
--   dos llevan simulation_batches al estado de su corrida (_sincroniza_lote).
-- - Las llaves foráneas las revisa PostgreSQL con los permisos del dueño de la
--   tabla; el trigger fn_version_aprobada (014), con los de quien inserta: por eso
--   corridas lee scenario_versions.
-- =============================================================================

BEGIN;

DO $$
DECLARE
    r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['svc_corridas', 'svc_simulador', 'svc_resultados', 'svc_notificaciones']
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

-- corridas: crear_corrida (lote y corrida, auditados), cancelar_run, get_run y
-- get_runs_recientes. De users, solo el nombre de quien pidió la corrida.
GRANT SELECT ON simulation_batches, simulation_runs, scenario_versions, scenarios,
                diseases, regions TO svc_corridas;
GRANT SELECT (id, username, full_name) ON users TO svc_corridas;
GRANT INSERT ON simulation_batches, simulation_runs TO svc_corridas;
GRANT UPDATE (status, started_at, finished_at) ON simulation_runs TO svc_corridas;
GRANT UPDATE (status, finished_at) ON simulation_batches TO svc_corridas;
GRANT INSERT ON audit_log TO svc_corridas;

-- simulador: simulaciones.ejecutar_run y recupera_corridas_interrumpidas. Arma la
-- entrada del motor desde la versión aprobada (get_version_simulacion y
-- get_escenario_detalle), guarda el resultado y cierra la corrida.
GRANT SELECT ON simulation_batches, simulation_runs, scenario_versions, scenarios,
                scenario_interventions, intervention_types, diseases, regions TO svc_simulador;
GRANT SELECT (id, username, full_name) ON users TO svc_simulador;
GRANT UPDATE (status, progress, started_at, finished_at, error_message)
    ON simulation_runs TO svc_simulador;
GRANT UPDATE (status, finished_at) ON simulation_batches TO svc_simulador;
GRANT INSERT ON simulation_results TO svc_simulador;
GRANT INSERT ON audit_log TO svc_simulador;

-- resultados: solo lectura (get_run y get_resultado_run). No escribe, ni en audit_log.
GRANT SELECT ON simulation_runs, simulation_results, scenario_versions, scenarios,
                diseases, regions TO svc_resultados;
GRANT SELECT (id, username, full_name) ON users TO svc_resultados;

-- notificaciones: dueño de notifications. Marcar como leída solo toca read_at.
GRANT SELECT, INSERT ON notifications TO svc_notificaciones;
GRANT UPDATE (read_at) ON notifications TO svc_notificaciones;
GRANT INSERT ON audit_log TO svc_notificaciones;

-- -----------------------------------------------------------------------------
-- Secuencias de las tablas donde se inserta (simulation_results no tiene: su
-- llave es run_id)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    par TEXT[];
    secuencia TEXT;
BEGIN
    FOREACH par SLICE 1 IN ARRAY ARRAY[
        ['svc_corridas', 'audit_log'], ['svc_corridas', 'simulation_batches'],
        ['svc_corridas', 'simulation_runs'],
        ['svc_simulador', 'audit_log'],
        ['svc_notificaciones', 'audit_log'], ['svc_notificaciones', 'notifications']
    ]
    LOOP
        secuencia := pg_get_serial_sequence('public.' || par[2], 'id');
        IF secuencia IS NOT NULL THEN
            EXECUTE format('GRANT USAGE ON SEQUENCE %s TO %I', secuencia, par[1]);
        END IF;
    END LOOP;
END;
$$;

-- -----------------------------------------------------------------------------
-- notifications.type: el aviso de versión aprobada
-- -----------------------------------------------------------------------------
-- aprobacion avisa a quien armó la versión cuando se aprueba. SCENARIO_PUBLISHED
-- es otra cosa (publicar al sitio público, permiso scenarios.publish).
ALTER TABLE notifications DROP CONSTRAINT IF EXISTS ck_notifications_type;
ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type CHECK (type IN
    ('RUN_FINISHED', 'RUN_FAILED', 'THRESHOLD_EXCEEDED', 'ASSIGNMENT',
     'SCENARIO_PUBLISHED', 'SCENARIO_APPROVED', 'SYSTEM'));

COMMENT ON COLUMN notifications.type IS
    'Tipo: RUN_FINISHED, RUN_FAILED, THRESHOLD_EXCEEDED, ASSIGNMENT, SCENARIO_PUBLISHED, SCENARIO_APPROVED o SYSTEM.';

COMMENT ON ROLE svc_corridas IS 'Microservicio corridas (5241): alta y cancelacion de corridas.';
COMMENT ON ROLE svc_simulador IS 'Microservicio simulador (5242): ejecuta corridas y guarda resultados.';
COMMENT ON ROLE svc_resultados IS 'Microservicio resultados (5243): solo lectura de corridas y resultados.';
COMMENT ON ROLE svc_notificaciones IS 'Microservicio notificaciones (5261): duenio de notifications.';

INSERT INTO schema_migrations (version, description)
VALUES ('029', 'Seguridad: roles de corridas, simulador, resultados y notificaciones; aviso SCENARIO_APPROVED')
ON CONFLICT (version) DO NOTHING;

COMMIT;
