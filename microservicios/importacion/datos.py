# Los conjuntos de datos observados en la base: observed_datasets y observed_points (061, D53).
# Un conjunto no se edita ni se borra (D52): importar otra vez la misma clave crea la versión
# siguiente, y el mismo archivo con la misma clave regresa la versión que ya estaba.
import psycopg2.extras

from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import get_conn, query

MAX_LISTA = 200
_COLUMNAS = """o.id, o.code, o.version, o.name, d.code AS disease, r.code AS region, o.region_id,
               o.metric, o.period, o.source, o.license, o.source_url, o.cutoff_date, o.sha256,
               o.imported_by, o.created_at"""
_DE = """FROM observed_datasets o JOIN diseases d ON d.id = o.disease_id
         JOIN regions r ON r.id = o.region_id"""
_RESUMEN = """SELECT count(*) AS puntos, min(period_start) AS inicio, max(period_start) AS fin,
                     coalesce(sum(value), 0) AS total, max(value) AS maximo,
                     count(*) FILTER (WHERE value = 0) AS periodos_en_cero
                FROM observed_points WHERE dataset_id = %s"""


def ids_de(disease, region):
    # (disease_id, region_id); None en el que no existe.
    enfermedad = query("SELECT id FROM diseases WHERE code = %s", (disease,), one=True)
    lugar = query("SELECT id FROM regions WHERE code = %s", (region,), one=True)
    return (enfermedad["id"] if enfermedad else None), (lugar["id"] if lugar else None)


def _conjunto(cur, dataset_id):
    cur.execute("SELECT %s %s WHERE o.id = %%s" % (_COLUMNAS, _DE), (dataset_id,))
    fila = dict(cur.fetchone())
    cur.execute(_RESUMEN, (dataset_id,))
    fila["resumen"] = dict(cur.fetchone())
    return fila


def guardar(meta, ids, puntos, huella, user_id, *, contexto):
    # (conjunto, creado). Recibe metadatos y puntos que ya pasaron lectura.revisa*.
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended('conjunto ' || %s, 0))", (meta["code"],))
            cur.execute("SELECT id FROM observed_datasets WHERE code = %s AND sha256 = %s",
                        (meta["code"], huella))
            previo = cur.fetchone()
            if previo:
                return _conjunto(cur, previo["id"]), False
            cur.execute(
                """INSERT INTO observed_datasets
                       (code, version, name, disease_id, region_id, metric, period, source, license,
                        source_url, cutoff_date, sha256, imported_by)
                   SELECT %s, coalesce(max(version), 0) + 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                     FROM observed_datasets WHERE code = %s
                   RETURNING id""",
                (meta["code"], meta["name"], ids[0], ids[1], meta["metric"], meta["period"],
                 meta["source"], meta["license"], meta["url"], meta["cutoff"], huella, user_id,
                 meta["code"]))
            dataset_id = cur.fetchone()["id"]
            psycopg2.extras.execute_values(
                cur, "INSERT INTO observed_points (dataset_id, period_start, value) VALUES %s",
                [(dataset_id, dia, valor) for dia, valor in puntos])
            fila = _conjunto(cur, dataset_id)
            log_audit(contexto, "CREATE", "observed_datasets", dataset_id,
                      data_after={k: fila[k] for k in ("code", "version", "name", "disease", "region",
                                                       "metric", "period", "source", "license",
                                                       "source_url", "cutoff_date", "sha256")}
                      | {"resumen": fila["resumen"]}, cur=cur)
        conn.commit()
    return fila, True


def listar(disease=None, region=None, regiones=None):
    # De la más nueva a la más vieja. regiones: los ids que cubre el alcance (D43), o None.
    condiciones, params = [], []
    for columna, valor in (("d.code", disease), ("r.code", region)):
        if valor:
            condiciones.append(columna + " = %s")
            params.append(valor)
    if regiones is not None:
        condiciones.append("o.region_id = ANY(%s)")
        params.append(sorted(regiones))
    donde = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return [dict(f) for f in query("SELECT %s %s %s ORDER BY o.created_at DESC, o.id DESC LIMIT %d"
                                   % (_COLUMNAS, _DE, donde, MAX_LISTA), params)]


def get(dataset_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM observed_datasets WHERE id = %s", (dataset_id,))
            return _conjunto(cur, dataset_id) if cur.fetchone() else None


def puntos(dataset_id):
    return [{"periodo_inicio": f["period_start"], "valor": f["value"]} for f in query(
        "SELECT period_start, value FROM observed_points WHERE dataset_id = %s ORDER BY period_start",
        (dataset_id,))]
