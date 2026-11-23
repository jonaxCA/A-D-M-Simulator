import psycopg2.extras

from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import a_jsonb, get_conn, query
from procesamiento.entrada_motor import estado_parametros, motivo_no_simulable

MAX_INTENTOS = 3
# La gente que el censo cuenta sin edad se reparte entre los grupos: la serie observada es de
# todos los residentes. Es supuesto del método, y el motor lo anota en la trazabilidad.
POLITICA_EDAD = "prorratear"

_COLUMNAS = """c.id, c.dataset_id, c.engine, c.engine_version, c.method, c.method_version,
               c.config, c.status, c.attempts, c.progress, c.error, c.requested_by,
               c.created_at, c.started_at, c.finished_at, o.code AS dataset_code,
               o.version AS dataset_version, o.disease_id, o.region_id,
               u.username AS requested_by_username"""
_DE = """FROM calibrations c
         JOIN observed_datasets o ON o.id = c.dataset_id
         LEFT JOIN users u ON u.id = c.requested_by"""


def conjunto(dataset_id):
    return query("""
        SELECT o.id, o.code, o.version, o.name, o.disease_id, o.region_id, o.metric, o.period,
               o.source, o.license, o.cutoff_date, o.sha256, d.code AS disease_code,
               d.name AS disease_name, d.default_params, d.is_active AS disease_active,
               r.code AS region_code, r.name AS region_name
        FROM observed_datasets o
        JOIN diseases d ON d.id = o.disease_id
        JOIN regions r ON r.id = o.region_id
        WHERE o.id = %s""", (dataset_id,), one=True)


def puntos(dataset_id):
    return [{"inicio": str(f["period_start"]), "valor": f["value"]} for f in query(
        "SELECT period_start, value FROM observed_points WHERE dataset_id = %s ORDER BY period_start",
        (dataset_id,))]


def _grupos(region_id, de_municipios):
    donde = ("g.region_id IN (SELECT id FROM regions WHERE parent_region_id = %s)" if de_municipios
             else "g.region_id = %s")
    return query("""SELECT g.age_group, min(g.lower_bound) AS lower_bound, sum(g.population) AS population
                    FROM region_age_groups g WHERE %s
                    GROUP BY g.age_group ORDER BY min(g.lower_bound) NULLS LAST""" % donde,
                 (region_id,))


def poblacion(region_id):
    # Del censo de la región o, si no lo trae, la suma de sus municipios (021). Factor 1 (D6).
    filas = _grupos(region_id, False) or _grupos(region_id, True)
    grupos = {f["age_group"]: int(f["population"]) for f in filas if f["lower_bound"] is not None}
    sin_edad = sum(int(f["population"]) for f in filas if f["lower_bound"] is None)
    return grupos, sin_edad


def base(fila):
    # Lo fijo de una calibración: la enfermedad del catálogo y la población por edad (D50).
    errores = []
    if fila["period"] != "semana":
        errores.append("Solo se calibra contra series semanales; esta es por %s." % fila["period"])
    if fila["metric"] != "casos_confirmados":
        errores.append("Solo se calibra contra casos confirmados; esta serie es de %s." % fila["metric"])
    estado = estado_parametros(fila["default_params"])
    if not estado["simulable"]:
        errores.append("La enfermedad no se puede simular: %s." % motivo_no_simulable(
            len(estado["faltan"]), len(estado["sin_fuente"])))
    grupos, sin_edad = poblacion(fila["region_id"])
    if not grupos:
        errores.append("La región no tiene población por grupo de edad.")
    salida = {"enfermedad": fila["default_params"], "poblacion": grupos}
    if sin_edad:
        salida.update(poblacion_edad_desconocida=sin_edad, politica_edad_desconocida=POLITICA_EDAD)
    return salida, errores


def crear(dataset_id, motor, engine_version, metodo, version_metodo, config, user_id, *, contexto):
    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO calibrations (dataset_id, engine, engine_version, method,
                                                         method_version, config, requested_by)
                               VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s) RETURNING id""",
                            (dataset_id, motor, engine_version, metodo, version_metodo,
                             a_jsonb(config), user_id))
                cal_id = cur.fetchone()[0]
                log_audit(contexto, "RUN", "calibration", entity_id=cal_id,
                          data_after={"estado": "encolado", "dataset_id": dataset_id,
                                      "engine": motor, "engine_version": engine_version,
                                      "config": config}, cur=cur)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return cal_id


def get(cal_id, con_resultado=False):
    extra = ", c.result" if con_resultado else ""
    return query("SELECT %s%s %s WHERE c.id = %%s" % (_COLUMNAS, extra, _DE), (cal_id,), one=True)


def listar(limite, estado=None, dataset_id=None, regiones=None):
    condiciones, params = [], []
    if estado:
        condiciones.append("c.status = %s")
        params.append(estado)
    if dataset_id:
        condiciones.append("c.dataset_id = %s")
        params.append(dataset_id)
    if regiones is not None:
        condiciones.append("o.region_id = ANY(%s)")
        params.append(list(regiones))
    donde = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return query("SELECT %s %s %s ORDER BY c.created_at DESC, c.id DESC LIMIT %%s"
                 % (_COLUMNAS, _DE, donde), tuple(params) + (limite,))


def region_de(cal_id):
    fila = query("""SELECT o.region_id FROM calibrations c JOIN observed_datasets o ON o.id = c.dataset_id
                    WHERE c.id = %s""", (cal_id,), one=True)
    return fila["region_id"] if fila else None


def estado(cal_id):
    fila = query("SELECT status FROM calibrations WHERE id = %s", (cal_id,), one=True)
    return fila["status"] if fila else None


def _transicion(sql, params, cal_id, accion, datos_despues, contexto):
    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                fila = cur.fetchone()
                if fila:
                    log_audit(contexto, accion, "calibration", entity_id=cal_id,
                              data_before={"estado": fila["anterior"]} if "anterior" in fila else None,
                              data_after=datos_despues, cur=cur)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return fila is not None


def cancelar(cal_id, *, contexto):
    return _transicion("""
        UPDATE calibrations c SET status = 'cancelado', finished_at = now()
        FROM calibrations a
        WHERE a.id = c.id AND c.id = %s AND c.status IN ('encolado', 'ejecutando')
        RETURNING a.status AS anterior""", (cal_id,), cal_id, "CANCEL",
                       {"estado": "cancelado"}, contexto)


def marcar_ejecutando(cal_id, *, contexto):
    return _transicion("""
        UPDATE calibrations SET status = 'ejecutando', started_at = now(), progress = 0,
                                attempts = attempts + 1
        WHERE id = %s AND status = 'encolado' AND attempts < %s
        RETURNING attempts""", (cal_id, MAX_INTENTOS), cal_id, "RUN",
                       {"estado": "ejecutando"}, contexto)


def completar(cal_id, resultado, *, contexto):
    return _transicion("""
        UPDATE calibrations SET status = 'completado', progress = 100, result = %s::jsonb,
                                error = NULL, finished_at = now()
        WHERE id = %s AND status = 'ejecutando'
        RETURNING id""", (a_jsonb(resultado), cal_id), cal_id, "RUN",
                       {"estado": "completado", "parametros": resultado["parametros"],
                        "metricas": resultado["metricas"]}, contexto)


def fallar(cal_id, error, *, contexto):
    return _transicion("""
        UPDATE calibrations SET status = 'fallido', error = %s, finished_at = now()
        WHERE id = %s AND status = 'ejecutando'
        RETURNING id""", (error, cal_id), cal_id, "RUN",
                       {"estado": "fallido", "error": error}, contexto)


def reencola_interrumpidas(engine_version, contexto_de):
    # D38: las que dejó a medias un trabajador muerto vuelven a 'encolado' y se repiten con la
    # misma configuración; sin intentos o con otra versión del motor se cierran como fallidas.
    error = "El trabajador se detuvo y la calibración ya no tiene intentos, o es de otra versión del motor."
    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""UPDATE calibrations SET status = 'encolado', started_at = NULL
                               WHERE status = 'ejecutando' AND attempts < %s AND engine_version = %s
                               RETURNING id, requested_by, attempts""",
                            (MAX_INTENTOS, engine_version))
                reencoladas = cur.fetchall()
                cur.execute("""UPDATE calibrations SET status = 'fallido', error = %s, finished_at = now()
                               WHERE status = 'ejecutando'
                               RETURNING id, requested_by, attempts""", (error,))
                cerradas = cur.fetchall()
                for filas, estado_nuevo in ((reencoladas, "encolado"), (cerradas, "fallido")):
                    for f in filas:
                        log_audit(contexto_de(f["requested_by"]), "RUN", "calibration",
                                  entity_id=f["id"], data_before={"estado": "ejecutando"},
                                  data_after={"estado": estado_nuevo, "intentos": f["attempts"],
                                              "motivo": "recuperacion_al_arrancar"}, cur=cur)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return [f["id"] for f in reencoladas], [f["id"] for f in cerradas]


def encoladas():
    return [f["id"] for f in query(
        "SELECT id FROM calibrations WHERE status = 'encolado' ORDER BY id")]
