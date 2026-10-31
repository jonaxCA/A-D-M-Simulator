"""Pruebas contra los contenedores del compose de pruebas: las corre python infra/pruebas_integracion.py.

Sin EPIDEMIA_PRUEBAS_ENV, que pone ese script, se saltan: el pytest de siempre no usa Docker.
Las sesiones se abren directo en el Redis de pruebas, como microservicios/comun/scripts/
token_pruebas.py, porque el inicio de sesión lleva captcha; auth tiene sus propias pruebas.
"""
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
ENTORNO = os.environ.get("EPIDEMIA_PRUEBAS_ENV")
DIRECTORIO = "http://127.0.0.1:5262/api/v1/services?format=json"
CUENTAS = {"analista": ("alex.cavazos", "ANALISTA"), "epidemiologo": ("diana.flores", "EPIDEMIOLOGO"),
           "admin": ("admin", "ADMINISTRADOR"), "capturista": ("karla.trevino", "CAPTURISTA")}
INTERVENCIONES = [
    {"code": "VACUNACION", "start_day": 10, "end_day": None, "coverage": 0.5, "compliance": None,
     "params": {"eficacia": 0.7, "dosis_diarias": 2000}},
    {"code": "CIERRE_ESCUELAS", "start_day": 15, "end_day": 45, "coverage": 1, "compliance": 0.8, "params": {}},
]
TERMINADAS = ("completado", "fallido", "cancelado")


def pytest_collection_modifyitems(config, items):
    if ENTORNO:
        return
    salta = pytest.mark.skip(reason="Sin compose de pruebas: python infra/pruebas_integracion.py")
    for item in items:
        if AQUI in Path(str(item.fspath)).parents:
            item.add_marker(salta)


def espera(condicion, limite, falla, cada=1):
    fin = time.monotonic() + limite
    while True:
        valor = condicion()
        if valor:
            return valor
        assert time.monotonic() < fin, falla
        time.sleep(cada)


@pytest.fixture(scope="session")
def entorno():
    from dotenv import dotenv_values
    return dotenv_values(ENTORNO)


@pytest.fixture(scope="session")
def compose():
    base = ["docker", "compose", "-p", os.environ.get("EPIDEMIA_PRUEBAS_PROYECTO", "epidemia-pruebas"),
            "-f", str(RAIZ / "infra/docker-compose.yml"), "-f", str(RAIZ / "infra/docker-compose.pruebas.yml"),
            "--env-file", ENTORNO, "--profile", "*"]

    def correr(*argumentos):
        return subprocess.run(base + list(argumentos), capture_output=True, text=True, check=True).stdout
    return correr


@pytest.fixture(scope="session")
def api():
    """api(servicio, metodo, ruta, token): la URL sale del directorio de estado-servicios."""
    import requests
    urls = {s["nombre"]: s["url"] for s in requests.get(DIRECTORIO, timeout=10).json()["servicios"]}

    def pide(servicio, metodo, ruta, token=None, formato="json", params=None, headers=None, **opciones):
        params = dict(params or {})
        if formato == "json":
            params["format"] = "json"
        headers = dict(headers or {})
        if token:
            headers["Authorization"] = "Bearer " + token
        return requests.request(metodo, urls[servicio] + ruta, params=params, headers=headers,
                                timeout=opciones.pop("timeout", 30), **opciones)
    return pide


@pytest.fixture(scope="session")
def base(entorno):
    """base() conecta como postgres; base("regiones"), como svc_regiones con su contraseña."""
    import psycopg2

    def conecta(servicio=None):
        clave = entorno["DB_PASSWORD_" + servicio.upper().replace("-", "_")] if servicio else entorno["POSTGRES_PASSWORD"]
        return psycopg2.connect(host="127.0.0.1", port=entorno["POSTGRES_PUERTO_LOCAL"],
                                dbname=entorno["POSTGRES_DB"], password=clave,
                                user="svc_" + servicio.replace("-", "_") if servicio else "postgres")
    return conecta


@pytest.fixture(scope="session")
def sesion(entorno, base):
    """sesion("analista") abre una sesión en el Redis de pruebas: {"access", "refresh", "id"}."""
    import jwt
    import redis
    from epidemia_comun import redis_compartido, sesiones

    conexion = base()
    with conexion.cursor() as cur:
        cur.execute("SELECT username, id FROM users WHERE username = ANY(%s)",
                    ([usuario for usuario, _ in CUENTAS.values()],))
        ids = dict(cur.fetchall())
    conexion.close()
    redis_compartido.usar(redis.Redis(host="127.0.0.1", port=int(entorno["REDIS_PUERTO_LOCAL"]),
                                      password=entorno["REDIS_PASSWORD"], decode_responses=True))

    def abre(cuenta):
        usuario, rol = CUENTAS[cuenta]
        abierta = sesiones.abrir(ids[usuario], [rol], ttl=3600)
        ahora = int(time.time())
        claims = {"iss": "epidemia-auth", "aud": "epidemia-api", "sub": str(ids[usuario]), "roles": [rol],
                  "sid": abierta["sid"], "jti": str(uuid.uuid4()), "iat": ahora, "nbf": ahora, "exp": ahora + 1200}
        return {"access": jwt.encode(claims, entorno["JWT_SECRET_KEY"], algorithm="HS256"),
                "refresh": abierta["refresh"], "id": ids[usuario]}
    yield abre
    redis_compartido.usar(None)


@pytest.fixture(scope="session")
def analista(sesion):
    return sesion("analista")


@pytest.fixture(scope="session")
def catalogo(api):
    enfermedades = api("enfermedades", "GET", "/api/v1/diseases").json()["enfermedades"]
    municipios = api("regiones", "GET", "/api/v1/regions").json()["municipios"]
    monterrey = next(m for m in municipios if m["code"] == "19039")
    return {"disease_id": next(e["id"] for e in enfermedades if e["code"] == "INFLUENZA_ESTACIONAL"),
            "region_id": monterrey["id"], "poblacion": monterrey["poblacion"]}


@pytest.fixture(scope="session")
def crea_escenario(api, analista, catalogo):
    """crea_escenario(nombre, intervenciones) -> (escenario, versión, {código: id de la intervención})."""
    def crea(nombre, intervenciones=()):
        r = api("escenarios", "POST", "/api/v1/scenarios", analista["access"], json={
            "name": "%s %s" % (nombre, uuid.uuid4().hex[:8]), "description": "Prueba de integración.",
            "disease_id": catalogo["disease_id"], "region_id": catalogo["region_id"],
            "population_size": catalogo["poblacion"], "horizon_days": 90, "initial_infected": 10,
            "stratify": False, "notes": None})
        assert r.status_code == 201, r.text
        escenario = r.json()["id"]
        version = api("escenarios", "GET", "/api/v1/scenarios/%d" % escenario, analista["access"]).json()["version"]["id"]
        creadas = {}
        for intervencion in intervenciones:
            r = api("intervenciones", "POST", "/api/v1/versions/%d/interventions" % version, analista["access"],
                    json=intervencion)
            assert r.status_code == 201, r.text
            creadas[intervencion["code"]] = r.json()["id"]
        return escenario, version, creadas
    return crea


@pytest.fixture(scope="session")
def aprueba(api, analista, sesion):
    epidemiologa = sesion("epidemiologo")

    def aprobar(escenario):
        r = api("aprobacion", "POST", "/api/v1/scenarios/%d/submit" % escenario, analista["access"])
        assert r.status_code == 200, r.text
        r = api("aprobacion", "POST", "/api/v1/scenarios/%d/review" % escenario, epidemiologa["access"],
                json={"decision": "aprobar", "comentario": "Aprobado en la prueba de integración."})
        assert r.status_code == 200 and r.json()["status"] == "aprobado", r.text
    return aprobar


@pytest.fixture(scope="session")
def lanza(api, analista):
    """lanza(versión, semilla) encola una corrida y regresa su id."""
    def lanzar(version, semilla):
        r = api("corridas", "POST", "/api/v1/runs", analista["access"],
                json={"scenario_version_id": version, "seed": semilla})
        assert r.status_code == 202, r.text
        return r.json()["id"]
    return lanzar


@pytest.fixture(scope="session")
def termina(api, analista):
    """termina(ids) espera a que terminen las corridas y regresa {id: estado}."""
    def terminar(ids, limite=180):
        def estados():
            actuales = {i: api("corridas", "GET", "/api/v1/runs/%d" % i, analista["access"]).json()["status"]
                        for i in ids}
            return actuales if all(e in TERMINADAS for e in actuales.values()) else None
        return espera(estados, limite, "Las corridas %s no terminaron en %d s." % (ids, limite))
    return terminar
