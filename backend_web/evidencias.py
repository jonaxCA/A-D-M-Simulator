"""
Evidencias de los casos: la tabla case_attachments (migraciones 005 y 032).

La escribe solo el microservicio evidencias. El archivo vive en una carpeta del
servicio (un volumen de Docker), no en la base: aqui va su ruta, su tipo, su
tamano y su huella. El tipo sale del contenido, no de lo que diga el cliente.
Subir la misma foto otra vez al mismo caso regresa la que ya estaba, para que un
reintento de la app no la duplique.
"""
import hashlib
import logging
import uuid
from pathlib import Path

import psycopg2.extras

from .audit import log_audit
from .db import get_conn, query

log = logging.getLogger(__name__)

# ck_case_attachments_max y ck_case_attachments_mime (005).
MAXIMO = 20 * 1024 * 1024
EXTENSIONES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
               "application/pdf": ".pdf"}
_COLUMNAS = "id, case_id, mime_type, size_bytes, sha256, privacy, uploaded_by, uploaded_at"


def tipo_por_contenido(datos):
    """El tipo segun los primeros bytes, o None si no es uno de EXTENSIONES."""
    if datos.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    if datos.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def valida_archivo(datos):
    """Lista de errores en espanol; vacia si se puede guardar."""
    if not datos:
        return ["El archivo llegó vacío."]
    if len(datos) > MAXIMO:
        return ["El archivo pasa de 20 MB."]
    if tipo_por_contenido(datos) is None:
        return ["Solo se aceptan fotos JPEG, PNG o WebP, o un PDF, enviados tal cual en el "
                "cuerpo de la petición (no como formulario)."]
    return []


def get_caso(case_id):
    """El caso con quien lo reporto, o None si no existe."""
    fila = query("SELECT id, reported_by FROM cases WHERE id = %s", (case_id,), one=True)
    return dict(fila) if fila else None


def _bitacora(case_id, tipo, tamano, huella, ruta):
    return {"case_id": case_id, "mime_type": tipo, "size_bytes": tamano, "sha256": huella,
            "storage_path": ruta}


def guardar_evidencia(case_id, datos, user_id, carpeta, *, contexto):
    """Guarda el archivo en `carpeta` y su registro. Recibe datos que ya pasaron
    valida_archivo. Devuelve (evidencia, creada)."""
    huella = hashlib.sha256(datos).hexdigest()
    tipo = tipo_por_contenido(datos)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Dos subidas de la misma foto al mismo caso se esperan una a la otra.
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                        (f"evidencia:{case_id}:{huella}",))
            cur.execute(f"SELECT {_COLUMNAS} FROM case_attachments WHERE case_id = %s AND sha256 = %s",
                        (case_id, huella))
            previa = cur.fetchone()
            if previa:
                return dict(previa), False
            ruta = f"evidence/{case_id}/{uuid.uuid4().hex}{EXTENSIONES[tipo]}"
            destino = Path(carpeta) / ruta
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(datos)
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
                # Sin registro, el archivo no lo encontraria nadie.
                destino.unlink(missing_ok=True)
                raise
    return dict(fila), True


def listar_evidencias(case_id):
    return [dict(f) for f in query(
        f"SELECT {_COLUMNAS} FROM case_attachments WHERE case_id = %s ORDER BY uploaded_at, id",
        (case_id,))]


def get_evidencia(evidencia_id):
    fila = query(f"SELECT {_COLUMNAS} FROM case_attachments WHERE id = %s", (evidencia_id,), one=True)
    return dict(fila) if fila else None


def archivo_de_evidencia(evidencia_id, carpeta):
    """(evidencia, ruta del archivo en `carpeta`), o (None, None) si no existe."""
    fila = query(f"SELECT {_COLUMNAS}, storage_path FROM case_attachments WHERE id = %s",
                 (evidencia_id,), one=True)
    if not fila:
        return None, None
    fila = dict(fila)
    return fila, Path(carpeta) / fila.pop("storage_path")


def borrar_evidencia(evidencia_id, carpeta, *, contexto):
    """Borra el registro y despues el archivo. Devuelve la evidencia borrada, o None si
    no existia."""
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
    # Despues del commit: si fallara, el registro seguiria apuntando a un archivo borrado.
    try:
        (Path(carpeta) / ruta).unlink(missing_ok=True)
    except OSError:
        log.warning("No se pudo borrar el archivo %s de la evidencia %s", ruta, evidencia_id)
    return fila
