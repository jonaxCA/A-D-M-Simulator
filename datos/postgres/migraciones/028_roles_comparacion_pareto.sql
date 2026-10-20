-- =============================================================================
-- 028_roles_comparacion_pareto.sql
-- Un rol de PostgreSQL para los microservicios comparacion y pareto (bloque L).
-- Sigue el patrón de la 026 y la 027.
--
-- Los dos son de solo lectura: no escriben nada, ni siquiera en audit_log.
-- - Los roles nacen con LOGIN y sin contraseña. En el compose la fija
--   infra/postgres/10-inicializa.sh; fuera de él: ALTER ROLE svc_pareto PASSWORD '...';
--   y el servicio la recibe en su DATABASE_URL (ver infra/.env.example).
-- - No toca a epidemia_app ni a los roles app_* de la 009: el monolito sigue igual.
-- - Idempotente: cada corrida revoca y vuelve a otorgar exactamente lo de abajo.
-- =============================================================================

BEGIN;

DO $$
DECLARE
    r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['svc_comparacion', 'svc_pareto']
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

-- comparacion: queries.get_corridas_para_comparar().
GRANT SELECT ON simulation_runs, simulation_results, scenario_versions, scenarios TO svc_comparacion;

-- pareto: simulaciones.construir_comparacion_costo_impacto(), que arma el escenario de
-- cada versión (get_run, get_version_simulacion y get_escenario_detalle), lee los costos
-- de intervention_types y el resultado guardado de cada corrida. De users, solo el nombre
-- de quien la creó, la posee o la revisó.
GRANT SELECT ON simulation_runs, simulation_results, scenario_versions, scenarios,
                scenario_interventions, intervention_types, diseases, regions TO svc_pareto;
GRANT SELECT (id, username, full_name) ON users TO svc_pareto;

COMMENT ON ROLE svc_comparacion IS 'Microservicio comparacion (5244): solo lectura de corridas y resultados.';
COMMENT ON ROLE svc_pareto IS 'Microservicio pareto (5245): solo lectura; costo contra impacto de corridas completadas.';

INSERT INTO schema_migrations (version, description)
VALUES ('028', 'Seguridad: roles de PostgreSQL de comparacion y pareto')
ON CONFLICT (version) DO NOTHING;

COMMIT;
