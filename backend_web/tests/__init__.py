"""
Las pruebas corren contra su propia base, nunca contra la de la aplicacion.

audit_log es de solo insercion: lo que una prueba escribe ahi no se puede
limpiar, y pantallas como Regiones leen de ahi si una cifra fue corregida a
mano. Si las pruebas usaran la base de la demostracion, le dejarian marcas
visibles. Por eso este paquete cambia DATABASE_URL antes de que cualquier
prueba se conecte:

  - DATABASE_URL_PRUEBAS, si esta en el entorno o en el .env;
  - si no, la misma DATABASE_URL con "_pruebas" al final del nombre de la base
    (simulador_epidemico -> simulador_epidemico_pruebas): mismo usuario y
    contrasena, sin escribir otra credencial.

La base se crea con `python datos/scripts/prepara_base_pruebas.py`. Mientras no
exista, las pruebas que la necesitan se saltan con un aviso.
"""
import os
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()


def _ubicacion(url):
    partes = urlsplit(url)
    return ((partes.hostname or "localhost").lower(), partes.port or 5432,
            partes.path.lstrip("/"))


def url_de_pruebas(url_app, url_pruebas=""):
    """La DATABASE_URL de las pruebas. Se niega a devolver la misma base que la
    de la aplicacion."""
    if url_pruebas:
        url = url_pruebas
    else:
        partes = urlsplit(url_app)
        nombre = partes.path.lstrip("/")
        if not nombre:
            raise RuntimeError("DATABASE_URL no dice a que base conectarse; no se puede "
                               "derivar la de pruebas. Define DATABASE_URL_PRUEBAS.")
        url = partes._replace(path=f"/{nombre}_pruebas").geturl()
    if _ubicacion(url) == _ubicacion(url_app):
        raise RuntimeError("DATABASE_URL_PRUEBAS apunta a la misma base que DATABASE_URL. "
                           "Las pruebas dejan rastro en audit_log: usa una base aparte.")
    return url


URL_APP = (os.environ.get("DATABASE_URL") or "").strip()
BASE_DE_LA_APP = _ubicacion(URL_APP)[2] if URL_APP else ""

if URL_APP:
    os.environ["DATABASE_URL"] = url_de_pruebas(
        URL_APP, (os.environ.get("DATABASE_URL_PRUEBAS") or "").strip())
    # backend_web.db lee DATABASE_URL una sola vez, al importarse. Si algo lo
    # importo antes que este paquete, se corrige aqui.
    from backend_web import db as _db
    _db.DATABASE_URL = os.environ["DATABASE_URL"]
