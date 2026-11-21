import json
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from .conexiones import conexion


@contextmanager
def get_conn():
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("Falta DATABASE_URL.")
    # Prestada y reutilizada (conexiones.py, F4), en lugar de abrir una por consulta.
    with conexion(url, lambda u: psycopg2.connect(u)) as conn:
        yield conn


def query(sql, params=None, one=False):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            filas = cur.fetchall()
            return (filas[0] if filas else None) if one else filas


def execute(sql, params=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            filas = cur.rowcount
        conn.commit()
        return filas


def a_jsonb(datos):
    return None if datos is None else json.dumps(datos, default=str, ensure_ascii=False)
