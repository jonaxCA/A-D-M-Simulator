from epidemia_comun.bd import query


def get_run(run_id):
    return query(
        """
        SELECT r.id, r.batch_id, r.scenario_version_id, r.seed, r.status,
               r.progress, r.engine_version, r.queued_at, r.started_at,
               r.finished_at, r.error_message, r.requested_by,
               sv.version_number, sv.scenario_id, sv.status AS version_status,
               sv.population_size, sv.horizon_days, sv.initial_infected,
               s.name AS scenario_name, s.disease_id, s.region_id,
               d.name AS disease_name,
               reg.name AS region_name, reg.population AS region_population,
               u.username AS requested_by_username, u.full_name AS requested_by_nombre
        FROM simulation_runs r
        JOIN scenario_versions sv ON sv.id = r.scenario_version_id
        JOIN scenarios s   ON s.id   = sv.scenario_id
        JOIN diseases d    ON d.id   = s.disease_id
        JOIN regions reg   ON reg.id = s.region_id
        JOIN users u        ON u.id   = r.requested_by
        WHERE r.id = %s
        """,
        (run_id,),
        one=True,
    )


def get_resultado_run(run_id):
    return query(
        """
        SELECT id AS run_id, engine_version, scenario_checksum, resumen,
               trazabilidad, finished_at
        FROM simulation_runs
        WHERE id = %s AND resumen IS NOT NULL
        """,
        (run_id,),
        one=True,
    )


def get_run_ids_completados(scenario_version_id, engine_version):
    return [f["id"] for f in query(
        """
        SELECT id FROM simulation_runs
        WHERE scenario_version_id = %s AND engine_version = %s
          AND status = 'completado' AND resumen IS NOT NULL
        ORDER BY id
        """,
        (scenario_version_id, engine_version),
    )]
