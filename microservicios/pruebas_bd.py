import functools
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Nunca la base de la demostración: audit_log es de solo inserción.
_url = (os.environ.get("DATABASE_URL_PRUEBAS") or os.environ.get("DATABASE_URL") or "").strip()
if _url and not urlsplit(_url).path.endswith("_pruebas"):
    _url = urlsplit(_url)._replace(path=urlsplit(_url).path + "_pruebas").geturl()
if _url:
    os.environ["DATABASE_URL"] = _url

from epidemia_comun.auditoria import Contexto  # noqa: E402
from epidemia_comun.bd import get_conn, query  # noqa: E402


@functools.lru_cache(maxsize=None)
def tiene_base():
    try:
        query("SELECT 1", one=True)
        return True
    except Exception:
        return False


def escribe(sql, params=()):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


def contexto_de_prueba(user_id):
    return Contexto(user_id, "127.0.0.1", "pytest")


def id_de_usuario(username):
    return query("SELECT id FROM users WHERE username = %s", (username,), one=True)["id"]
