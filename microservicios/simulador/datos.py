import json

from epidemia_comun.bd import get_conn, query


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


def get_motor_run(run_id):
    fila = query(
        """
        SELECT b.engine FROM simulation_runs r
        JOIN simulation_batches b ON b.id = r.batch_id
        WHERE r.id = %s
        """,
        (run_id,),
        one=True,
    )
    return fila["engine"] if fila else None


def _sincroniza_lote(cur, run_ids):
    if not run_ids:
        return
    cur.execute(
        """
        UPDATE simulation_batches b
        SET status = r.status,
            finished_at = CASE WHEN r.status IN ('completado', 'fallido', 'cancelado')
                               THEN r.finished_at END
        FROM simulation_runs r
        WHERE r.id = ANY(%s) AND b.id = r.batch_id
        """,
        (list(run_ids),),
    )


def _transiciona_run(sql, params):
    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                ids = [fila[0] for fila in cur.fetchall()]
                _sincroniza_lote(cur, ids)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return ids


def marcar_run_ejecutando(run_id):
    return len(_transiciona_run(
        """
        UPDATE simulation_runs SET status = 'ejecutando', started_at = now(),
               attempts = attempts + 1
        WHERE id = %s AND status = 'encolado' AND attempts < 3
        RETURNING id
        """,
        (run_id,),
    )) == 1


def guardar_resultado_run(run_id, resultado):
    resumen_json = json.dumps(resultado["resumen"], ensure_ascii=False, default=str)
    trazabilidad_json = json.dumps(
        resultado.get("trazabilidad_parametros", []), ensure_ascii=False, default=str
    )

    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                # Solo si seguia 'ejecutando': si otro proceso ya la cerro, no
                # se revive ni se guarda nada.
                cur.execute(
                    """
                    UPDATE simulation_runs
                    SET status = 'completado', progress = 100, finished_at = now(),
                        engine_version = %s, scenario_checksum = %s,
                        resumen = %s::jsonb, trazabilidad = %s::jsonb
                    WHERE id = %s AND status = 'ejecutando'
                    """,
                    (
                        resultado["engine_version"],
                        resultado["huella_escenario"],
                        resumen_json,
                        trazabilidad_json,
                        run_id,
                    ),
                )
                if cur.rowcount != 1:
                    conn.rollback()
                    return False
                _sincroniza_lote(cur, [run_id])
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return True


def marcar_run_fallido(run_id, mensaje):
    return len(_transiciona_run(
        """
        UPDATE simulation_runs
        SET status = 'fallido', error_message = %s, finished_at = now(),
            started_at = COALESCE(started_at, now())
        WHERE id = %s AND status NOT IN ('completado', 'fallido', 'cancelado')
        RETURNING id
        """,
        (mensaje, run_id),
    )) == 1


def reencola_corridas_interrumpidas(engine, engine_version, max_intentos=3):
    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE simulation_runs SET status = 'encolado', started_at = NULL
                       WHERE status = 'ejecutando' AND attempts < %s
                         AND (engine_version IS NULL OR engine_version = %s)
                         AND batch_id IN (SELECT id FROM simulation_batches WHERE engine = %s)
                       RETURNING id, requested_by, seed, attempts""",
                    (max_intentos, engine_version, engine))
                filas = [dict(zip(("id", "requested_by", "seed", "attempts"), f))
                         for f in cur.fetchall()]
                _sincroniza_lote(cur, [f["id"] for f in filas])
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return filas


def marca_corridas_interrumpidas(mensaje, run_ids=None, estados=("encolado", "ejecutando"),
                                 engine=None):
    filtro, params = "", [mensaje, list(estados)]
    if run_ids is not None:
        filtro = "AND id = ANY(%s)"
        params.append(list(run_ids))
    if engine is not None:
        filtro += " AND batch_id IN (SELECT id FROM simulation_batches WHERE engine = %s)"
        params.append(engine)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE simulation_runs
                SET status = 'fallido', error_message = %s, finished_at = now(),
                    started_at = COALESCE(started_at, now())
                WHERE status IN ('encolado', 'ejecutando') AND status = ANY(%s) {filtro}
                RETURNING id, requested_by, seed
                """,
                tuple(params),
            )
            filas = [{"id": i, "requested_by": u, "seed": s}
                     for i, u, s in cur.fetchall()]
            _sincroniza_lote(cur, [f["id"] for f in filas])
        conn.commit()
    return filas


def corridas_encoladas(engine):
    filas = query("SELECT r.id FROM simulation_runs r"
                  " JOIN simulation_batches b ON b.id = r.batch_id"
                  " WHERE r.status = 'encolado' AND b.engine = %s ORDER BY r.id", (engine,))
    return [fila["id"] for fila in filas]


def corridas_completadas(engine):
    return query("SELECT r.id, r.engine_version, r.scenario_checksum, r.resumen"
                 " FROM simulation_runs r JOIN simulation_batches b ON b.id = r.batch_id"
                 " WHERE r.status = 'completado' AND b.engine = %s ORDER BY r.id", (engine,))


def prioridades(run_ids):
    if not run_ids:
        return {}
    filas = query("SELECT id, priority FROM simulation_runs WHERE id = ANY(%s)", (list(run_ids),))
    return {fila["id"]: fila["priority"] for fila in filas}


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
