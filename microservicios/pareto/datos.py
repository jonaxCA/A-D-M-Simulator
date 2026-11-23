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


def get_tipos_intervencion():
    return [dict(r) for r in query(
        """SELECT id, code, name, description, target_layer, primitive, param_schema,
                  unit_cost, cost_unit, cost_source, cost_is_assumption,
                  person_days_per_unit, person_days_source, person_days_is_assumption
           FROM intervention_types WHERE is_active ORDER BY name""")]


def version_para_motor(version_id):
    version = query(
        """
        SELECT sv.id, sv.scenario_id, sv.version_number, sv.status, sv.population_size,
               sv.horizon_days, sv.initial_infected, sv.population_by_age,
               sv.population_age_unknown, sv.age_unknown_policy, sv.disease_params,
               sv.param_overrides, d.default_params
        FROM scenario_versions sv
        JOIN scenarios s ON s.id = sv.scenario_id
        JOIN diseases d ON d.id = s.disease_id
        WHERE sv.id = %s
        """,
        (version_id,), one=True)
    if not version:
        return None, []
    intervenciones = [dict(r) for r in query(
        """
        SELECT i.start_day, i.end_day, i.coverage, i.compliance, i.params, t.code
        FROM scenario_interventions i
        JOIN intervention_types t ON t.id = i.intervention_type_id
        WHERE i.scenario_version_id = %s
        ORDER BY i.order_index, i.start_day, i.id
        """,
        (version_id,))]
    return dict(version), intervenciones


def regiones_de_corridas(run_ids):
    filas = query("SELECT r.id, s.region_id FROM simulation_runs r"
                  " JOIN scenario_versions sv ON sv.id = r.scenario_version_id"
                  " JOIN scenarios s ON s.id = sv.scenario_id WHERE r.id = ANY(%s)", (list(run_ids),))
    return {f["region_id"] for f in filas}


def region_de_version(version_id):
    fila = query("SELECT s.region_id FROM scenario_versions sv JOIN scenarios s ON s.id = sv.scenario_id"
                 " WHERE sv.id = %s", (version_id,), one=True)
    return fila["region_id"] if fila else None
