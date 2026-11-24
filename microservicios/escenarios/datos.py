# Los escenarios: alta, versiones nuevas y duplicado (antes en backend_web.queries, E8), proyectos de
# investigación, archivado y el historial de versiones con sus responsables (D54). Cada escritura y
# su bitácora van en la misma transacción. Revisar un escenario contra el motor es de validacion.
import psycopg2
import psycopg2.extras

from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import a_jsonb, get_conn, query
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


ESTADO_NL = "19"
NOMBRE_DUPLICADO = ("Ya tienes un escenario con ese nombre. El nombre es único por autor, así que "
                    "elige otro.")
_SQL_COPIA_INTERVENCIONES = """
    INSERT INTO scenario_interventions
        (scenario_version_id, intervention_type_id, target_region_id, start_day,
         end_day, coverage, compliance, params, order_index)
    SELECT %s, intervention_type_id, target_region_id, start_day, end_day,
           coverage, compliance, params, order_index
    FROM scenario_interventions
    WHERE scenario_version_id = %s
"""


def enfermedad_activa(disease_id):
    return query("SELECT 1 FROM diseases WHERE id = %s AND is_active", (disease_id,), one=True) is not None


def region_de_nl(region_id):
    return query("""SELECT 1 FROM regions WHERE id = %s
                      AND (code = %s OR parent_region_id = (SELECT id FROM regions WHERE code = %s))""",
                 (region_id, ESTADO_NL, ESTADO_NL), one=True) is not None


def lista(busqueda=None):
    condiciones, params = [], []
    if busqueda:
        condiciones.append("(s.name ILIKE %s OR d.name ILIKE %s OR g.name ILIKE %s)")
        params += ["%" + busqueda + "%"] * 3
    donde = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    filas = query(
        """SELECT s.id, s.name, s.description, s.status, s.created_at,
                  d.name AS enfermedad, g.name AS region, u.full_name AS autor,
                  v.version_number, v.status AS version_status, v.population_size,
                  v.horizon_days, v.initial_infected,
                  v.population_by_age, v.population_age_unknown, v.age_unknown_policy
           FROM scenarios s
           JOIN diseases d ON d.id = s.disease_id
           JOIN regions  g ON g.id = s.region_id
           JOIN users    u ON u.id = s.owner_id
           LEFT JOIN scenario_versions v ON v.scenario_id = s.id AND v.is_current
           %s
           ORDER BY s.created_at DESC, s.name""" % donde, tuple(params))
    return [dict(f, por_edad=bool(f["population_by_age"])) for f in filas]


def escenario_detalle(scenario_id, version_number=None):
    escenario = query(
        """SELECT s.id, s.name, s.description, s.status, s.owner_id, s.created_at,
                  d.id AS disease_id, d.name AS enfermedad, d.default_params,
                  g.id AS region_id, g.name AS region, g.population AS region_poblacion,
                  u.full_name AS autor
           FROM scenarios s
           JOIN diseases d ON d.id = s.disease_id
           JOIN regions  g ON g.id = s.region_id
           JOIN users    u ON u.id = s.owner_id
           WHERE s.id = %s""", (scenario_id,), one=True)
    if not escenario:
        return None
    filtro = "v.version_number = %s" if version_number is not None else "v.is_current"
    params = (scenario_id, version_number) if version_number is not None else (scenario_id,)
    version = query(
        """SELECT v.id, v.version_number, v.status, v.is_current, v.population_size,
                  v.horizon_days, v.initial_infected, v.notes, v.created_at,
                  v.population_by_age, v.population_age_unknown, v.age_unknown_policy,
                  v.created_by, v.submitted_at, v.reviewed_at, v.review_comment,
                  v.param_overrides, v.disease_params,
                  u.full_name AS autor, r.full_name AS revisor
           FROM scenario_versions v
           JOIN users u ON u.id = v.created_by
           LEFT JOIN users r ON r.id = v.reviewed_by
           WHERE v.scenario_id = %s AND """ + filtro, params, one=True)
    if version_number is not None and version is None:
        return None
    intervenciones = []
    if version:
        intervenciones = [dict(r) for r in query(
            """SELECT i.id, i.start_day, i.end_day, i.coverage, i.compliance, i.params,
                      i.order_index, t.code, t.name, t.target_layer, t.param_schema
               FROM scenario_interventions i
               JOIN intervention_types t ON t.id = i.intervention_type_id
               WHERE i.scenario_version_id = %s
               ORDER BY i.order_index, i.start_day, i.id""", (version["id"],))]
    # Un borrador usa el catálogo vivo con los ajustes de la versión encima (044, D59); una versión
    # enviada, su fotografía (D5). Sin fotografía fuera de borrador, la pantalla lo advierte.
    congelada = version["disease_params"] if version else None
    return {
        "escenario": dict(escenario),
        "version": dict(version) if version else None,
        "intervenciones": intervenciones,
        "parametros_enfermedad": congelada or {**(escenario["default_params"] or {}),
                                               **((version or {}).get("param_overrides") or {})},
        "parametros_congelados": congelada is not None,
        "parametros_sin_congelar": bool(version and version["status"] != "borrador" and congelada is None),
        "editable": bool(version and version["is_current"] and version["status"] == "borrador"),
    }


def crea_escenario(datos, *, contexto):
    # El escenario y su versión 1 (borrador y vigente) en una sola transacción: un escenario sin
    # versión no se puede simular ni revisar. (ok, error, scenario_id).
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO scenarios (name, description, disease_id, region_id,
                                                      owner_id, status, is_public)
                               VALUES (%s, %s, %s, %s, %s, 'borrador', false)
                               RETURNING id""",
                            (datos["name"], datos["description"], datos["disease_id"],
                             datos["region_id"], contexto.user_id))
                scenario_id = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO scenario_versions
                           (scenario_id, version_number, is_current, population_size,
                            horizon_days, initial_infected, notes, created_by, status,
                            population_by_age, population_age_unknown, age_unknown_policy)
                       VALUES (%s, 1, true, %s, %s, %s, %s, %s, 'borrador', %s::jsonb, %s, %s)
                       RETURNING id""",
                    (scenario_id, datos["population_size"], datos["horizon_days"],
                     datos["initial_infected"], datos["notes"], contexto.user_id,
                     a_jsonb(datos["population_by_age"]) if datos["population_by_age"] else None,
                     datos["population_age_unknown"], datos["age_unknown_policy"]))
                version_id = cur.fetchone()[0]
                log_audit(contexto, "CREATE", "scenarios", scenario_id,
                          data_after={**datos, "scenario_id": scenario_id, "version_id": version_id,
                                      "version_number": 1}, cur=cur)
            conn.commit()
        return True, None, scenario_id
    except psycopg2.errors.UniqueViolation:
        return False, NOMBRE_DUPLICADO, None
    except psycopg2.errors.CheckViolation as exc:
        return False, "Los datos no cumplen las restricciones de la base: %s" % exc, None


def crea_version(scenario_id, datos, *, contexto):
    # La versión siguiente a partir de la vigente, con sus intervenciones y sus ajustes de
    # parámetros (D59) copiados. Nace borrador aunque la anterior estuviera aprobada.
    # (ok, error, version_number).
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT id, version_number FROM scenario_versions
                               WHERE scenario_id = %s ORDER BY version_number DESC FOR UPDATE""",
                            (scenario_id,))
                filas = cur.fetchall()
                if not filas:
                    return False, "Ese escenario no tiene ninguna versión de la que partir.", None
                origen_id, ultimo = filas[0]
                siguiente = ultimo + 1
                # Primero apagar: el índice único sobre is_current no es diferible.
                cur.execute("UPDATE scenario_versions SET is_current = false "
                            "WHERE scenario_id = %s AND is_current", (scenario_id,))
                cur.execute(
                    """INSERT INTO scenario_versions
                           (scenario_id, version_number, is_current, population_size,
                            horizon_days, initial_infected, notes, created_by, status,
                            population_by_age, population_age_unknown, age_unknown_policy,
                            param_overrides)
                       VALUES (%s, %s, true, %s, %s, %s, %s, %s, 'borrador', %s::jsonb, %s, %s,
                               (SELECT param_overrides FROM scenario_versions WHERE id = %s))
                       RETURNING id""",
                    (scenario_id, siguiente, datos["population_size"], datos["horizon_days"],
                     datos["initial_infected"], datos["notes"], contexto.user_id,
                     a_jsonb(datos["population_by_age"]) if datos["population_by_age"] else None,
                     datos["population_age_unknown"], datos["age_unknown_policy"], origen_id))
                nueva_id = cur.fetchone()[0]
                cur.execute(_SQL_COPIA_INTERVENCIONES, (nueva_id, origen_id))
                log_audit(contexto, "CREATE", "scenario_versions", nueva_id,
                          data_before={"version_vigente_anterior": ultimo},
                          data_after={**datos, "scenario_id": scenario_id, "version_number": siguiente,
                                      "intervenciones_copiadas": cur.rowcount}, cur=cur)
            conn.commit()
        return True, None, siguiente
    except psycopg2.errors.CheckViolation as exc:
        return False, "Los datos no cumplen las restricciones de la base: %s" % exc, None
    except psycopg2.errors.UniqueViolation:
        return False, ("Otra persona creó una versión al mismo tiempo. Recarga la página y vuelve a "
                       "intentarlo."), None


def duplica_escenario(scenario_id, version_number, nombre, *, contexto):
    # Un escenario nuevo de quien duplica, en borrador y con versión 1, a partir de una versión de
    # otro: no hereda su aprobación, porque nadie ha revisado esto. (ok, error, scenario_id).
    nombre = (nombre or "").strip()
    if not nombre:
        return False, "Ponle un nombre al escenario nuevo.", None
    if len(nombre) > 160:
        return False, "El nombre no puede pasar de 160 caracteres.", None
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT s.disease_id, s.region_id, s.description, v.id, v.population_size,
                                      v.horizon_days, v.initial_infected, v.population_by_age,
                                      v.population_age_unknown, v.age_unknown_policy
                               FROM scenarios s
                               JOIN scenario_versions v ON v.scenario_id = s.id
                               WHERE s.id = %s AND v.version_number = %s""",
                            (scenario_id, version_number))
                fila = cur.fetchone()
                if not fila:
                    return False, "Esa versión del escenario ya no existe.", None
                (disease_id, region_id, descripcion, origen_id, poblacion, dias, iniciales, por_edad,
                 sin_edad, politica) = fila
                cur.execute("""INSERT INTO scenarios (name, description, disease_id, region_id,
                                                      owner_id, status, is_public)
                               VALUES (%s, %s, %s, %s, %s, 'borrador', false)
                               RETURNING id""",
                            (nombre, descripcion, disease_id, region_id, contexto.user_id))
                nuevo_id = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO scenario_versions
                           (scenario_id, version_number, is_current, population_size,
                            horizon_days, initial_infected, notes, created_by, status,
                            population_by_age, population_age_unknown, age_unknown_policy,
                            param_overrides)
                       VALUES (%s, 1, true, %s, %s, %s, %s, %s, 'borrador', %s::jsonb, %s, %s,
                               (SELECT param_overrides FROM scenario_versions WHERE id = %s))
                       RETURNING id""",
                    (nuevo_id, poblacion, dias, iniciales,
                     "Duplicado de la versión %s del escenario #%s." % (version_number, scenario_id),
                     contexto.user_id, a_jsonb(por_edad) if por_edad else None, sin_edad, politica,
                     origen_id))
                cur.execute(_SQL_COPIA_INTERVENCIONES, (cur.fetchone()[0], origen_id))
                log_audit(contexto, "CREATE", "scenarios", nuevo_id,
                          data_after={"name": nombre, "duplicado_de": scenario_id,
                                      "version_origen": version_number,
                                      "intervenciones_copiadas": cur.rowcount}, cur=cur)
            conn.commit()
        return True, None, nuevo_id
    except psycopg2.errors.UniqueViolation:
        return False, NOMBRE_DUPLICADO, None
    except psycopg2.errors.CheckViolation as exc:
        return False, "Los datos no cumplen las restricciones de la base: %s" % exc, None
