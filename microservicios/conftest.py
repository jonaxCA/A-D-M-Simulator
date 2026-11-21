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
def mongo_falso():
    """Una base de mongomock para epidemia_comun.mongo; se descarta al terminar."""
    import mongomock
    from epidemia_comun import mongo
    # tz_aware, como el cliente de epidemia_comun.mongo: las fechas regresan en UTC.
    base = mongomock.MongoClient(tz_aware=True)["epidemia_pruebas"]
    mongo.usar(base)
    yield base
    mongo.usar(None)


class _MongoCaido:
    def __getitem__(self, nombre):
        from pymongo.errors import ServerSelectionTimeoutError
        raise ServerSelectionTimeoutError("MongoDB apagado en la prueba")

    def command(self, *args, **kwargs):
        return self[""]


@pytest.fixture
def apagar_mongo(mongo_falso):
    """apagar_mongo() hace que toda operación de MongoDB falle; encender() lo regresa."""
    from epidemia_comun import mongo

    def apagar():
        mongo.usar(_MongoCaido())

    def encender():
        mongo.usar(mongo_falso)
    apagar.encender = encender
    return apagar


@pytest.fixture
def crear_cliente(redis_falso):
    """crear_cliente("series") regresa el cliente de prueba de ese servicio."""
    def crear(paquete):
        modulo = importlib.import_module("microservicios.%s.app" % paquete)
        app = modulo.app
        app.config["TESTING"] = True
        # El fixture token firma con SECRETO_PRUEBAS. El entorno puede traer otro: en un
        # pytest sin carpetas, backend_web/tests carga antes el .env de la raíz.
        app.config["JWT_SECRET_KEY"] = SECRETO_PRUEBAS
        app.extensions["epidemia_redis"] = redis_falso
        return app.test_client()
    return crear


@pytest.fixture(autouse=True)
def negados(monkeypatch):
    """Los PERMISSION_DENIED que anota requiere_token; así un 403 nunca escribe en una base."""
    from epidemia_comun import auditoria as audit
    eventos = []
    monkeypatch.setattr(audit, "log_audit",
                        lambda ctx, accion, entidad, entity_id=None, data_after=None, **_:
                        eventos.append((ctx.user_id, accion, entidad, entity_id, data_after)))
    return eventos


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


class _RespuestaAlcance:
    def __init__(self, alcance):
        self.status_code, self._alcance = 200, alcance

    def json(self):
        return self._alcance


@pytest.fixture(autouse=True)
def alcance_falso(monkeypatch):
    """El alcance (D43) que `roles` regresa en GET /scopes/me: nacional, salvo que la prueba lo
    cambie con alcance_falso["regiones"] = [ids]. Las llamadas a roles quedan en ["llamadas"]."""
    from epidemia_comun import alcance
    estado = {"regiones": None, "llamadas": []}

    def llamar(servicio, metodo, ruta, **kw):
        estado["llamadas"].append((servicio, metodo, ruta))
        regiones = estado["regiones"]
        return _RespuestaAlcance({"nacional": regiones is None, "region_ids": regiones or [],
                                  "regiones_cubiertas": regiones or [], "institution_ids": []})

    monkeypatch.setattr(alcance, "llamar", llamar)
    return estado


class _RespuestaServicio:
    def __init__(self, respuesta):
        self.status_code, self._respuesta = respuesta.status_code, respuesta

    def json(self):
        return self._respuesta.get_json()


@pytest.fixture
def llamar_a_sesiones(crear_cliente):
    """Un `llamar` que atiende en proceso lo dirigido a `sesiones`, con su app real y el Redis falso."""
    cliente = crear_cliente("sesiones")

    def llamar(servicio, metodo, ruta, cuerpo=None, token=None, **_):
        assert servicio == "sesiones"
        return _RespuestaServicio(cliente.open(
            ruta, method=metodo, json=cuerpo, headers={"Authorization": "Bearer " + token,
                                                       "Accept": "application/json"}))
    return llamar


@pytest.fixture
def sesiones_en_proceso(monkeypatch, llamar_a_sesiones):
    """Para usuarios y roles: cerrar sesiones llega a la app de `sesiones` sin red."""
    from epidemia_comun import sesiones
    monkeypatch.setattr(sesiones, "llamar", llamar_a_sesiones)
