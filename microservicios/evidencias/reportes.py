"""
Reportes de una comparación: la tabla comparison_reports (migración 039, D35, RF-F17).

El ANALISTA o el ADMINISTRADOR los sube desde el escritorio o la web. El PDF va al bucket y
aquí sus metadatos. La comparación no se guarda en ningún lado: se identifica por las
corridas que compara. El mismo archivo con las mismas corridas regresa el que ya estaba.
"""
import hashlib
import uuid

import psycopg2.extras

from epidemia_comun import archivos
from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import get_conn, query

from .datos import quita_del_bucket

TIPOS = ("application/pdf",)
MAX_CORRIDAS = 100
MAX_TITULO = 200
MAX_LISTA = 100
_COLUMNAS = "id, run_ids, title, mime_type, size_bytes, sha256, privacy, uploaded_by, uploaded_at"


def valida_corridas(texto):
    """(lista de ids sin repetir, errores) a partir de "1,2,3"."""
    partes = [p.strip() for p in (texto or "").split(",") if p.strip()]
    if not partes:
        return [], ["Indica las corridas de la comparación en runs (por ejemplo runs=12,15)."]
    if not all(p.isdigit() and int(p) > 0 for p in partes):
        return [], ["runs debe ser una lista de ids de corrida separados por comas."]
    ids = list(dict.fromkeys(int(p) for p in partes))
    if len(ids) > MAX_CORRIDAS:
        return [], ["Una comparación tiene a lo más %d corridas." % MAX_CORRIDAS]
    return ids, []


def valida_titulo(titulo):
    titulo = (titulo or "").strip() or None
    if titulo and len(titulo) > MAX_TITULO:
        return None, ["El título tiene a lo más %d caracteres." % MAX_TITULO]
    return titulo, []


def corridas_que_faltan(run_ids):
    existen = {f["id"] for f in query("SELECT id FROM simulation_runs WHERE id = ANY(%s)", (run_ids,))}
    return [r for r in run_ids if r not in existen]


def _bitacora(fila, ruta):
    return {"run_ids": fila["run_ids"], "title": fila["title"], "size_bytes": fila["size_bytes"],
            "sha256": fila["sha256"], "storage_path": ruta}


def guardar_reporte(run_ids, datos, titulo, user_id, *, contexto):
    """Guarda el PDF en el bucket y su registro. Recibe datos que ya pasaron valida_archivo.
    Devuelve (reporte, creado)."""
    huella = hashlib.sha256(datos).hexdigest()
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended('reporte ' || %s, 0))", (huella,))
            cur.execute(f"SELECT {_COLUMNAS} FROM comparison_reports WHERE sha256 = %s AND run_ids = %s::bigint[]",
                        (huella, run_ids))
            previo = cur.fetchone()
            if previo:
                return dict(previo), False
            ruta = f"reportes/{run_ids[0]}/{uuid.uuid4().hex}.pdf"
            archivos.guardar(ruta, datos, "application/pdf")
            try:
                cur.execute(
                    f"""INSERT INTO comparison_reports
                            (run_ids, title, storage_path, size_bytes, sha256, uploaded_by)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING {_COLUMNAS}""",
                    (run_ids, titulo, ruta, len(datos), huella, user_id))
                fila = cur.fetchone()
                log_audit(contexto, "CREATE", "comparison_reports", fila["id"],
                          data_after=_bitacora(fila, ruta), cur=cur)
                conn.commit()
            except Exception:
                quita_del_bucket(ruta)
                raise
    return dict(fila), True


def listar_reportes(run_ids=None):
    """Los más recientes primero. Con run_ids, los que comparan al menos esas corridas."""
    if run_ids:
        filas = query(f"""SELECT {_COLUMNAS} FROM comparison_reports WHERE run_ids @> %s::bigint[]
                          ORDER BY uploaded_at DESC, id DESC LIMIT %s""", (run_ids, MAX_LISTA))
    else:
        filas = query(f"""SELECT {_COLUMNAS} FROM comparison_reports
                          ORDER BY uploaded_at DESC, id DESC LIMIT %s""", (MAX_LISTA,))
    return [dict(f) for f in filas]


def get_reporte(reporte_id):
    fila = query(f"SELECT {_COLUMNAS} FROM comparison_reports WHERE id = %s", (reporte_id,), one=True)
    return dict(fila) if fila else None


def objeto_de_reporte(reporte_id):
    """(reporte, ruta del objeto en el bucket), o (None, None) si no existe."""
    fila = query(f"SELECT {_COLUMNAS}, storage_path FROM comparison_reports WHERE id = %s",
                 (reporte_id,), one=True)
    if not fila:
        return None, None
    fila = dict(fila)
    return fila, fila.pop("storage_path")


def borrar_reporte(reporte_id, *, contexto):
    """Borra el registro y después el objeto. Devuelve el reporte borrado, o None."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"DELETE FROM comparison_reports WHERE id = %s RETURNING {_COLUMNAS}, storage_path",
                        (reporte_id,))
            fila = cur.fetchone()
            if fila is None:
                return None
            fila = dict(fila)
            ruta = fila.pop("storage_path")
            log_audit(contexto, "DELETE", "comparison_reports", reporte_id,
                      data_before=_bitacora(fila, ruta), cur=cur)
        conn.commit()
    quita_del_bucket(ruta)
    return fila
