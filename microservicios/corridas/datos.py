import psycopg2

from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import get_conn, query


PRIORIDADES = ("baja", "normal", "alta")
# Los filtros de fecha de las corridas son días de Nuevo León, no de UTC.
ZONA_HORARIA = "America/Monterrey"


def crear_corrida(version_id, seed, user_id, engine_version, *, engine="seir-ref",
                  contexto=None, forzar_error=False, prioridad="normal"):
    version = query(
        "SELECT status FROM scenario_versions WHERE id = %s", (version_id,), one=True
    )
    if not version:
        return None, None, "La versión de escenario no existe."
    if version["status"] != "aprobado":
        return None, None, (
            f"Esta versión no está aprobada (estado: {version['status']}); "
            "solo se pueden ejecutar simulaciones sobre versiones aprobadas."
        )

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO simulation_batches
                        (scenario_version_id, requested_by, replicas, engine, status)
                    VALUES (%s, %s, 1, %s, 'encolado')
                    RETURNING id
                    """,
                    (version_id, user_id, engine),
                )
                batch_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO simulation_runs
                        (batch_id, scenario_version_id, seed, replica_index, status,
                         engine_version, requested_by, priority)
                    VALUES (%s, %s, %s, 0, 'encolado', %s, %s, %s)
                    RETURNING id
                    """,
                    (batch_id, version_id, seed, engine_version, user_id, prioridad),
                )
                run_id = cur.fetchone()[0]
                if contexto is not None:
                    log_audit(contexto, "RUN", "simulation_run", entity_id=str(run_id),
                              data_after={"estado": "encolado", "seed": seed,
                                          "scenario_version_id": version_id,
                                          "engine": engine, "forzar_error": forzar_error,
                                          "prioridad": prioridad},
                              cur=cur)
            conn.commit()
        return run_id, batch_id, None
    except psycopg2.Error as exc:
        return None, None, f"No se pudo encolar la corrida: {exc}"


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


def get_runs_recientes(limit=20, *, scenario_id=None, scenario_version_id=None, status=None,
                       engine=None, desde=None, hasta=None, regiones=None):
    condiciones, params = [], []
    for columna, valor in (("sv.scenario_id", scenario_id),
                           ("r.scenario_version_id", scenario_version_id),
                           ("r.status", status), ("b.engine", engine)):
        if valor is not None:
            condiciones.append(f"{columna} = %s")
            params.append(valor)
    if regiones is not None:
        condiciones.append("s.region_id = ANY(%s)")
        params.append(list(regiones))
    if desde is not None:
        condiciones.append("r.queued_at >= %s::timestamp AT TIME ZONE %s")
        params += [desde, ZONA_HORARIA]
    if hasta is not None:
        condiciones.append("r.queued_at < (%s::date + 1)::timestamp AT TIME ZONE %s")
        params += [hasta, ZONA_HORARIA]

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    params.append(limit)
    return query(
        f"""
        SELECT r.id, r.status, r.seed, b.engine, r.queued_at, r.started_at, r.finished_at,
               r.error_message, r.scenario_version_id, sv.scenario_id, sv.version_number,
               s.name AS scenario_name, u.username AS requested_by_username,
               d.name AS disease_name, reg.name AS region_name
        FROM simulation_runs r
        LEFT JOIN simulation_batches b ON b.id = r.batch_id
        JOIN scenario_versions sv ON sv.id = r.scenario_version_id
        JOIN scenarios s ON s.id = sv.scenario_id
        JOIN diseases d  ON d.id = s.disease_id
        JOIN regions reg ON reg.id = s.region_id
        JOIN users u     ON u.id = r.requested_by
        {where}
        ORDER BY r.queued_at DESC
        LIMIT %s
        """,
        tuple(params),
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


def cancelar_run(run_id, *, contexto):
    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE simulation_runs
                    SET status = 'cancelado', finished_at = now(),
                        started_at = COALESCE(started_at, now())
                    WHERE id = %s AND status = 'encolado'
                    RETURNING id
                    """,
                    (run_id,),
                )
                if not cur.fetchone():
                    conn.rollback()
                    return False
                _sincroniza_lote(cur, [run_id])
                log_audit(contexto, "CANCEL", "simulation_run", entity_id=str(run_id),
                          data_before={"estado": "encolado"},
                          data_after={"estado": "cancelado"}, cur=cur)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return True


def reintentar_run(run_id, *, contexto, puede_alta=False):
    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE simulation_runs
                    SET status = 'encolado', started_at = NULL, finished_at = NULL,
                        error_message = NULL, progress = 0, attempts = 0,
                        priority = CASE WHEN priority = 'alta' AND NOT %s THEN 'normal' ELSE priority END
                    WHERE id = %s AND status = 'fallido'
                    RETURNING priority, seed
                    """,
                    (puede_alta, run_id),
                )
                fila = cur.fetchone()
                if not fila:
                    conn.rollback()
                    return None
                _sincroniza_lote(cur, [run_id])
                log_audit(contexto, "RUN", "simulation_run", entity_id=str(run_id),
                          data_before={"estado": "fallido"},
                          data_after={"estado": "encolado", "seed": fila[1],
                                      "prioridad": fila[0], "motivo": "reintento manual (D44)"},
                          cur=cur)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return fila[0]


def estimar_corrida(run_id):
    r = query(
        """
        SELECT r.id, r.status, r.priority, b.engine, sv.population_size, sv.horizon_days,
               EXTRACT(EPOCH FROM now() - r.started_at) AS transcurrido
        FROM simulation_runs r
        JOIN simulation_batches b ON b.id = r.batch_id
        JOIN scenario_versions sv ON sv.id = r.scenario_version_id
        WHERE r.id = %s
        """,
        (run_id,), one=True)
    est = {"priority": r["priority"], "queue_position": None, "estimated_seconds": None,
           "estimate_samples": 0, "estimate_reason": "La corrida ya terminó."}
    if r["status"] not in ("encolado", "ejecutando"):
        return est
    hist = query(
        """
        SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY d) AS mediana, count(*) AS n FROM (
            SELECT EXTRACT(EPOCH FROM x.finished_at - x.started_at) AS d
            FROM simulation_runs x
            JOIN simulation_batches xb ON xb.id = x.batch_id
            JOIN scenario_versions xv ON xv.id = x.scenario_version_id
            WHERE x.status = 'completado' AND xb.engine = %s
              AND xv.population_size = %s AND xv.horizon_days = %s
            ORDER BY x.finished_at DESC LIMIT 50) t
        """,
        (r["engine"], r["population_size"], r["horizon_days"]), one=True)
    est["estimate_samples"] = hist["n"]
    if r["status"] == "encolado":
        cola = query(
            """
            SELECT count(*) FILTER (WHERE x.status = 'ejecutando') AS ejecutando,
                   count(*) FILTER (WHERE x.status = 'encolado' AND (
                       array_position(%s::text[], x.priority) > array_position(%s::text[], %s)
                       OR (x.priority = %s AND x.id < %s))) AS delante
            FROM simulation_runs x JOIN simulation_batches xb ON xb.id = x.batch_id
            WHERE xb.engine = %s
            """,
            (list(PRIORIDADES), list(PRIORIDADES), r["priority"], r["priority"], r["id"],
             r["engine"]), one=True)
        est["queue_position"] = cola["delante"] + 1
    if not hist["n"]:
        est["estimate_reason"] = ("Aún no hay corridas completadas con ese motor, población y "
                                  "horizonte para estimar.")
        return est
    mediana = float(hist["mediana"])
    est["estimate_reason"] = None
    if r["status"] == "ejecutando":
        est["estimated_seconds"] = round(max(mediana - float(r["transcurrido"]), 0))
    else:
        est["estimated_seconds"] = round(mediana * (cola["ejecutando"] + cola["delante"] + 1))
    return est


def region_de_version(version_id):
    fila = query("SELECT s.region_id FROM scenario_versions sv JOIN scenarios s ON s.id = sv.scenario_id"
                 " WHERE sv.id = %s", (version_id,), one=True)
    return fila["region_id"] if fila else None
