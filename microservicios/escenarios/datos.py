# Proyectos de investigación, archivado y el historial de versiones con sus responsables (D54).
# El alta, las versiones y el duplicado siguen en backend_web.queries (E8 pendiente); lo nuevo vive
# aquí, con su SQL y su bitácora en la misma transacción.
import psycopg2
import psycopg2.extras

from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import get_conn, query
from epidemia_comun.errores import ErrorAPI

MOTORES = ("seir-ref", "abm-ref", "abm-gpu")
ESTADOS_PROYECTO = ("activo", "archivado")
CAMPOS_PROYECTO = ("name", "objective", "disease_id", "region_id", "period_start", "period_end",
                   "engines")

_PROYECTO = """
    SELECT p.id, p.name, p.objective, p.disease_id, d.name AS enfermedad, p.region_id,
           r.name AS region, p.period_start, p.period_end, p.engines, p.owner_id,
           u.full_name AS autor, p.status, p.created_at, p.updated_at,
           (SELECT count(*) FROM scenarios s WHERE s.project_id = p.id) AS n_escenarios
    FROM research_projects p
    JOIN diseases d ON d.id = p.disease_id
    JOIN regions r ON r.id = p.region_id
    JOIN users u ON u.id = p.owner_id"""


def _conflicto(mensaje):
    return ErrorAPI(409, "CONFLICTO", mensaje)


def proyectos(estado=None, busqueda=None, regiones=None):
    patron = "%%%s%%" % busqueda if busqueda else None
    return [dict(f) for f in query(
        _PROYECTO + """
        WHERE (%s IS NULL OR p.status = %s) AND (%s IS NULL OR p.name ILIKE %s)
          AND (%s IS NULL OR p.region_id = ANY(%s))
        ORDER BY p.updated_at DESC, p.id DESC""",
        (estado, estado, patron, patron, regiones, regiones))]


def proyecto(project_id):
    fila = query(_PROYECTO + " WHERE p.id = %s", (project_id,), one=True)
    return dict(fila) if fila else None


def escenarios_de(project_id):
    return [dict(f) for f in query(
        """SELECT s.id, s.name, s.status, s.owner_id, v.version_number, v.status AS version_status
           FROM scenarios s
           LEFT JOIN scenario_versions v ON v.scenario_id = s.id AND v.is_current
           WHERE s.project_id = %s
           ORDER BY s.name, s.id""", (project_id,))]


def crea_proyecto(datos, *, contexto):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO research_projects
                           (name, objective, disease_id, region_id, period_start, period_end,
                            engines, owner_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    tuple(datos[c] for c in CAMPOS_PROYECTO) + (contexto.user_id,))
                project_id = cur.fetchone()[0]
                log_audit(contexto, "CREATE", "research_projects", project_id,
                          data_after=dict(datos), cur=cur)
            conn.commit()
    except psycopg2.errors.UniqueViolation:
        raise _conflicto("Ya tienes un proyecto con ese nombre.")
    return project_id


def cambia_proyecto(project_id, cambios, *, contexto):
    columnas = [c for c in CAMPOS_PROYECTO if c in cambios]
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT %s, (SELECT count(*) FROM scenarios s WHERE s.project_id = p.id)"
                            " AS n FROM research_projects p WHERE p.id = %%s FOR UPDATE"
                            % ", ".join("p." + c for c in columnas + ["status"]), (project_id,))
                antes = cur.fetchone()
                if antes is None:
                    raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el proyecto.")
                if antes["status"] == "archivado":
                    raise _conflicto("El proyecto está archivado: restáuralo antes de cambiarlo.")
                cambia_lugar = any(c in ("disease_id", "region_id") and cambios[c] != antes[c]
                                   for c in columnas)
                if cambia_lugar and antes["n"]:
                    raise _conflicto("El proyecto ya tiene escenarios: su enfermedad y su región "
                                     "no cambian.")
                cur.execute("UPDATE research_projects SET %s, updated_at = now() WHERE id = %%s"
                            % ", ".join("%s = %%s" % c for c in columnas),
                            tuple(cambios[c] for c in columnas) + (project_id,))
                log_audit(contexto, "UPDATE", "research_projects", project_id,
                          data_before={c: antes[c] for c in columnas},
                          data_after={c: cambios[c] for c in columnas}, cur=cur)
            conn.commit()
    except psycopg2.errors.UniqueViolation:
        raise _conflicto("Ya tienes un proyecto con ese nombre.")
    except psycopg2.errors.CheckViolation:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "period_end no puede ser antes de period_start.")


def cambia_estado_proyecto(project_id, estado, *, contexto):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM research_projects WHERE id = %s FOR UPDATE", (project_id,))
            fila = cur.fetchone()
            if fila is None:
                raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el proyecto.")
            if fila[0] == estado:
                raise _conflicto("El proyecto ya está %s." % estado)
            cur.execute("UPDATE research_projects SET status = %s, updated_at = now() WHERE id = %s",
                        (estado, project_id))
            log_audit(contexto, "UPDATE", "research_projects", project_id,
                      data_before={"status": fila[0]}, data_after={"status": estado}, cur=cur)
        conn.commit()


def escenarios(ids):
    # {id: {...}}: lo que la lista de queries.get_escenarios no trae (proyecto, región, dueño).
    if not ids:
        return {}
    return {f["id"]: dict(f) for f in query(
        "SELECT id, project_id, owner_id, disease_id, region_id, status FROM scenarios "
        "WHERE id = ANY(%s)", (list(ids),))}


def _escenario_para_cambiar(cur, scenario_id):
    cur.execute(
        """SELECT s.id, s.owner_id, s.disease_id, s.region_id, s.status, s.is_public, s.project_id,
                  v.status AS version_status
           FROM scenarios s
           LEFT JOIN scenario_versions v ON v.scenario_id = s.id AND v.is_current
           WHERE s.id = %s FOR UPDATE OF s""", (scenario_id,))
    fila = cur.fetchone()
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el escenario.")
    return fila


def asigna_proyecto(scenario_id, project_id, *, contexto):
    # Permisos y alcance los revisa la ruta antes; aquí, lo que puede cambiar entre medio.
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            escenario = _escenario_para_cambiar(cur, scenario_id)
            if escenario["status"] == "archivado":
                raise _conflicto("El escenario está archivado: restáuralo antes de cambiarlo.")
            if escenario["project_id"] == project_id:
                return
            if project_id is not None:
                cur.execute("SELECT disease_id, region_id, status FROM research_projects "
                            "WHERE id = %s FOR SHARE", (project_id,))
                destino = cur.fetchone()
                if destino is None:
                    raise ErrorAPI(422, "DATOS_INVALIDOS", "No existe el proyecto %s." % project_id)
                if destino["status"] != "activo":
                    raise _conflicto("El proyecto está archivado: no recibe escenarios.")
                if (destino["disease_id"], destino["region_id"]) != (escenario["disease_id"],
                                                                      escenario["region_id"]):
                    raise ErrorAPI(422, "DATOS_INVALIDOS", "El escenario no es de la enfermedad y "
                                   "la región del proyecto.")
            cur.execute("UPDATE scenarios SET project_id = %s WHERE id = %s", (project_id, scenario_id))
            log_audit(contexto, "UPDATE", "scenarios", scenario_id,
                      data_before={"project_id": escenario["project_id"]},
                      data_after={"project_id": project_id}, cur=cur)
        conn.commit()


def archiva(scenario_id, archivar, *, contexto):
    # Archivado deja de ser público (ck_scenarios_publico); al restaurarlo vuelve a borrador, sin
    # volver a publicarse (D54).
    nuevo = "archivado" if archivar else "borrador"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            escenario = _escenario_para_cambiar(cur, scenario_id)
            if escenario["status"] == nuevo:
                raise _conflicto("El escenario ya está %s." % ("archivado" if archivar else "activo"))
            if archivar and escenario["version_status"] == "en_revision":
                raise _conflicto("La versión vigente está en revisión: espera el dictamen antes de "
                                 "archivar el escenario.")
            cur.execute("UPDATE scenarios SET status = %s, is_public = false WHERE id = %s",
                        (nuevo, scenario_id))
            log_audit(contexto, "UPDATE", "scenarios", scenario_id,
                      data_before={"status": escenario["status"], "is_public": escenario["is_public"]},
                      data_after={"status": nuevo, "is_public": False}, cur=cur)
        conn.commit()


def versiones(scenario_id):
    # El historial de versiones con sus responsables: quién la creó, cuándo se envió, quién la
    # revisó y su firma (D55). Lo que pasó entre medio está en roles (/audit/history, D43).
    return [dict(f) for f in query(
        """SELECT v.id, v.version_number, v.status, v.is_current, v.population_size,
                  v.horizon_days, v.initial_infected, v.notes, v.created_at,
                  v.population_by_age IS NOT NULL AS por_edad,
                  v.created_by, u.full_name AS autor, v.submitted_at,
                  v.reviewed_by, rev.full_name AS revisor, v.reviewed_at, v.review_comment,
                  (v.status = 'borrador' AND v.review_comment IS NOT NULL) AS devuelta,
                  v.approval_sha256,
                  (SELECT count(*) FROM scenario_interventions i
                   WHERE i.scenario_version_id = v.id) AS n_intervenciones
           FROM scenario_versions v
           JOIN users u ON u.id = v.created_by
           LEFT JOIN users rev ON rev.id = v.reviewed_by
           WHERE v.scenario_id = %s
           ORDER BY v.version_number DESC""", (scenario_id,))]
