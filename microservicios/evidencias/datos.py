"""
Evidencias de los casos: la tabla case_attachments (migraciones 005 y 032).

La escribe solo este servicio (E8: antes vivía en backend_web). El archivo va al bucket
(epidemia_comun.archivos, D30) y aquí su ruta, su tipo, su tamaño y su huella. El tipo sale
del contenido, no de lo que diga el cliente. Subir la misma foto otra vez al mismo caso
regresa la que ya estaba, para que un reintento de la app no la duplique.
"""
import hashlib
import logging
import re
import uuid

import psycopg2.extras

from epidemia_comun import archivos
from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import get_conn, query

log = logging.getLogger(__name__)

# ck_case_attachments_max y ck_case_attachments_mime (005).
MAXIMO = 20 * 1024 * 1024
EXTENSIONES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
               "application/pdf": ".pdf"}
HUELLA = re.compile(r"^[0-9a-f]{64}$")
_COLUMNAS = "id, case_id, mime_type, size_bytes, sha256, privacy, uploaded_by, uploaded_at"


def tipo_por_contenido(datos):
    """El tipo según los primeros bytes, o None si no es uno de EXTENSIONES."""
    if datos.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    if datos.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def valida_archivo(datos, huella=None, tipos=tuple(EXTENSIONES)):
    """Errores en español; vacía si se puede guardar. `huella` es la SHA-256 que declara el
    cliente (RNF-C09): si viene, tiene que ser la del archivo."""
    if not datos:
        return ["El archivo llegó vacío."]
    if len(datos) > MAXIMO:
        return ["El archivo pasa de 20 MB."]
    if tipo_por_contenido(datos) not in tipos:
        if tipos == ("application/pdf",):
            return ["Solo se acepta un PDF, enviado tal cual en el cuerpo de la petición "
                    "(no como formulario)."]
        return ["Solo se aceptan fotos JPEG, PNG o WebP, o un PDF, enviados tal cual en el "
                "cuerpo de la petición (no como formulario)."]
    if huella is not None:
        huella = huella.strip().lower()
        if not HUELLA.match(huella):
            return ["La huella debe ser la SHA-256 del archivo en 64 caracteres hexadecimales."]
        if huella != hashlib.sha256(datos).hexdigest():
            return ["El archivo no coincide con su huella: llegó incompleto o cambió en el camino."]
    return []


def quita_del_bucket(objeto):
    """Borra el objeto sin fallar: si el bucket no responde, queda huérfano y se avisa."""
    try:
        archivos.borrar(objeto)
    except archivos.BucketNoDisponible:
        log.warning("No se pudo borrar el objeto %s del bucket", objeto)


def get_caso(case_id):
    """El caso con quien lo reportó, o None si no existe."""
    fila = query("SELECT id, reported_by FROM cases WHERE id = %s", (case_id,), one=True)
    return dict(fila) if fila else None


def _bitacora(case_id, tipo, tamano, huella, ruta):
    return {"case_id": case_id, "mime_type": tipo, "size_bytes": tamano, "sha256": huella,
            "storage_path": ruta}


def guardar_evidencia(case_id, datos, user_id, *, contexto):
    """Guarda el archivo en el bucket y su registro. Recibe datos que ya pasaron
    valida_archivo. Devuelve (evidencia, creada)."""
    huella = hashlib.sha256(datos).hexdigest()
    tipo = tipo_por_contenido(datos)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Dos subidas de la misma foto al mismo caso se esperan una a la otra.
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended('evidencia ' || %s || ' ' || %s, 0))",
                        (case_id, huella))
            cur.execute(f"SELECT {_COLUMNAS} FROM case_attachments WHERE case_id = %s AND sha256 = %s",
                        (case_id, huella))
            previa = cur.fetchone()
            if previa:
                return dict(previa), False
            ruta = f"evidencias/{case_id}/{uuid.uuid4().hex}{EXTENSIONES[tipo]}"
            archivos.guardar(ruta, datos, tipo)
            try:
                cur.execute(
                    f"""INSERT INTO case_attachments
                            (case_id, storage_path, mime_type, size_bytes, sha256, uploaded_by)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING {_COLUMNAS}""",
                    (case_id, ruta, tipo, len(datos), huella, user_id))
                fila = cur.fetchone()
                log_audit(contexto, "CREATE", "case_attachments", fila["id"],
                          data_after=_bitacora(case_id, tipo, len(datos), huella, ruta), cur=cur)
                conn.commit()
            except Exception:
                # Sin registro, el objeto no lo encontraría nadie.
                quita_del_bucket(ruta)
                raise
    return dict(fila), True


def listar_evidencias(case_id):
    return [dict(f) for f in query(
        f"SELECT {_COLUMNAS} FROM case_attachments WHERE case_id = %s ORDER BY uploaded_at, id",
        (case_id,))]


def get_evidencia(evidencia_id):
    fila = query(f"SELECT {_COLUMNAS} FROM case_attachments WHERE id = %s", (evidencia_id,), one=True)
    return dict(fila) if fila else None


def objeto_de_evidencia(evidencia_id):
    """(evidencia, ruta del objeto en el bucket), o (None, None) si no existe."""
    fila = query(f"SELECT {_COLUMNAS}, storage_path FROM case_attachments WHERE id = %s",
                 (evidencia_id,), one=True)
    if not fila:
        return None, None
    fila = dict(fila)
    return fila, fila.pop("storage_path")


def borrar_evidencia(evidencia_id, *, contexto):
    """Borra el registro y después el objeto. Devuelve la evidencia borrada, o None si no
    existía."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"DELETE FROM case_attachments WHERE id = %s RETURNING {_COLUMNAS}, storage_path",
                        (evidencia_id,))
            fila = cur.fetchone()
            if fila is None:
                return None
            fila = dict(fila)
            ruta = fila.pop("storage_path")
            log_audit(contexto, "DELETE", "case_attachments", evidencia_id,
                      data_before=_bitacora(fila["case_id"], fila["mime_type"], fila["size_bytes"],
                                            fila["sha256"], ruta), cur=cur)
        conn.commit()
    # Después del commit: si fallara antes, el registro apuntaría a un objeto borrado.
    quita_del_bucket(ruta)
    return fila
