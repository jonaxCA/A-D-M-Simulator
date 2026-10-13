"""Utilidades de prueba para los servicios: Redis en memoria y tokens firmados.

La base y Redis siempre van simulados aquí; las pruebas de integración contra
los contenedores viven aparte (bloque O2).
"""
import importlib
import os
import sys
import time
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
for ruta in (str(RAIZ), str(RAIZ / "microservicios" / "comun")):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

SECRETO_PRUEBAS = "secreto-solo-para-pruebas-unitarias-0123456789"
os.environ.setdefault("JWT_SECRET_KEY", SECRETO_PRUEBAS)
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6399/0")


@pytest.fixture
def servidor_redis():
    import fakeredis
    return fakeredis.FakeServer()


@pytest.fixture
def redis_falso(servidor_redis):
    """Un solo fakeredis para crear_app (tokens) y redis_compartido (caché)."""
    import fakeredis
    from epidemia_comun import redis_compartido
    falso = fakeredis.FakeRedis(server=servidor_redis, decode_responses=True)
    redis_compartido.usar(falso)
    yield falso
    redis_compartido.usar(None)


@pytest.fixture
def apagar_redis(servidor_redis):
    """apagar_redis() hace que toda operación de Redis falle con ConnectionError."""
    def apagar():
        servidor_redis.connected = False
    return apagar


@pytest.fixture
def crear_cliente(redis_falso):
    """crear_cliente("series") regresa el cliente de prueba de ese servicio."""
    def crear(paquete):
        modulo = importlib.import_module("microservicios.%s.app" % paquete)
        app = modulo.app
        app.config["TESTING"] = True
        app.extensions["epidemia_redis"] = redis_falso
        return app.test_client()
    return crear


@pytest.fixture
def token(redis_falso):
    """token(roles) firma un access válido y abre su sesión en el Redis falso."""
    import jwt
    from epidemia_comun.seguridad import identificador_sesion

    def firmar(roles=("ANALISTA",), sesion_activa=True, **cambios):
        ahora = int(time.time())
        sid = str(uuid.uuid4())
        claims = {"iss": "epidemia-auth", "aud": "epidemia-api", "sub": "7",
                  "roles": list(roles), "sid": sid, "jti": str(uuid.uuid4()),
                  "iat": ahora, "nbf": ahora, "exp": ahora + 600}
        claims.update(cambios)
        if sesion_activa:
            redis_falso.set("session:" + identificador_sesion(sid), "1")
        return {"Authorization": "Bearer " + jwt.encode(claims, SECRETO_PRUEBAS,
                                                        algorithm="HS256")}
    return firmar
