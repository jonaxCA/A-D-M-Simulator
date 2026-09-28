"""Conexion directa a PostgreSQL. Sistema monolitico: sin capa de microservicios,
un solo pool de conexiones para toda la app (tal como se pidio: "se puede
entrar de manera indiscriminada a la DB").
"""
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

# Sin valor por omision. Antes habia uno que entraba como el superusuario
# `postgres` con una contrasena fija: si faltaba el .env, la app se conectaba
# con otra cuenta y otros permisos sin avisar, y el error que salia (si salia)
# no decia que el problema era la configuracion.
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


@contextmanager
def get_conn():
    _verifica_configuracion()
    conn = psycopg2.connect(DATABASE_URL)
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
