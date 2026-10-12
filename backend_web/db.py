"""Conexion directa a PostgreSQL. Sistema monolitico: sin capa de microservicios,
un solo pool de conexiones para toda la app (tal como se pidio: "se puede
entrar de manera indiscriminada a la DB").
"""
import json
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

# Sin valor por omision: con uno fijo (por ejemplo, el superusuario `postgres`
# con una contrasena escrita en el codigo), si faltara el .env la app se
# conectaria con otra cuenta y otros permisos sin avisar, y el error, si
# saliera, no diria que el problema es la configuracion.
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()


def _verifica_configuracion():
    if not DATABASE_URL:
        raise RuntimeError(
            "Falta DATABASE_URL en el archivo .env. Copia .env.example como .env "
            "y pon la cadena de conexion de tu base (docs/INSTALACION.md, paso 4.2).")
    if "CAMBIAR_CONTRASENA" in DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL todavia tiene el valor de ejemplo de .env.example: "
            "cambia CAMBIAR_CONTRASENA por la contrasena real de epidemia_app.")


def _conecta():
    """psycopg2.connect, con el error de conexion legible.

    PostgreSQL en Windows instalado en espanol (lc_messages =
    'Spanish_Mexico.1252') manda sus errores de conexion en cp1252, antes de
    que se acuerde la codificacion de la sesion. psycopg2 los lee como UTF-8 y
    en vez del error revienta con `UnicodeDecodeError: ... byte 0xf3`, que no
    dice nada. El mensaje real viene completo en los bytes (p. ej. "la
    autentificacion password fallo para el usuario ..."): se recupera y se
    lanza como el OperationalError que debio ser.
    """
    try:
        return psycopg2.connect(DATABASE_URL)
    except UnicodeDecodeError as exc:
        crudo = exc.object if isinstance(exc.object, (bytes, bytearray)) else b""
        mensaje = bytes(crudo).decode("cp1252", "replace").strip() or str(exc)
        raise psycopg2.OperationalError(mensaje) from exc


@contextmanager
def get_conn():
    _verifica_configuracion()
    conn = _conecta()
    try:
        yield conn
    finally:
        conn.close()


def query(sql, params=None, one=False):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            return (rows[0] if rows else None) if one else rows


def execute(sql, params=None):
    """Ejecuta sql y hace commit. Devuelve cur.rowcount, util para que el
    llamador sepa si el UPDATE/DELETE de verdad afecto alguna fila (p.ej.
    marcar_run_ejecutando/marcar_run_fallido en queries.py, que dependen de
    esto para no auditar una transicion de estado que no ocurrio)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            rowcount = cur.rowcount
        conn.commit()
        return rowcount


def a_jsonb(datos):
    """El valor para un parametro `%s::jsonb`, o None para guardar NULL. Lo que
    JSON no sabe escribir (fechas, Decimal) se guarda como texto, y los acentos
    tal cual."""
    if datos is None:
        return None
    return json.dumps(datos, default=str, ensure_ascii=False)
