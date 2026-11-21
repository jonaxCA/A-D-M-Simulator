import logging
import os
import threading
import time

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

log = logging.getLogger(__name__)

TTL_HISTORIAL = 30 * 86400

# Las colecciones de D28 con sus índices: el diseño de MongoDB en un solo lugar.
INDICES = {
    "series_corridas": [
        ([("run_id", ASCENDING), ("dia", ASCENDING)], {"unique": True}),
        ([("scenario_version_id", ASCENDING), ("motor", ASCENDING), ("dia", ASCENDING)], {}),
    ],
    "historial_servicios": [
        ([("servicio", ASCENDING), ("fecha", DESCENDING)], {}),
        # MongoDB solo admite TTL en un índice de un solo campo.
        ([("fecha", ASCENDING)], {"expireAfterSeconds": TTL_HISTORIAL}),
    ],
}

_candado = threading.Lock()
_clientes = {}
_fija = None
_con_indices = set()
_ultimo_aviso = 0.0


class MongoNoDisponible(Exception):
    codigo = "SERVICIO_NO_DISPONIBLE"
    http = 503


def base():
    if _fija is not None:
        return _fija
    url = (os.environ.get("MONGO_URL") or "").strip()
    if not url:
        raise MongoNoDisponible("Falta MONGO_URL.")
    with _candado:
        if url not in _clientes:
            espera = int(os.environ.get("MONGO_TIMEOUT_MS", "2000"))
            # Sin socketTimeoutMS, una operación con MongoDB pausado se quedaría esperando.
            _clientes[url] = MongoClient(url, serverSelectionTimeoutMS=espera,
                                         connectTimeoutMS=espera, socketTimeoutMS=espera * 5,
                                         tz_aware=True)
        return _clientes[url].get_default_database("epidemia")


def usar(nueva):
    # Las pruebas fijan aquí una base de mongomock; None vuelve a MONGO_URL.
    global _fija
    with _candado:
        _fija = nueva
        _clientes.clear()
        _con_indices.clear()


def coleccion(nombre):
    col = base()[nombre]
    if nombre not in _con_indices:
        for campos, opciones in INDICES.get(nombre, ()):
            col.create_index(campos, **opciones)
        _con_indices.add(nombre)
    return col


def requerido(operacion, funcion):
    try:
        return funcion()
    except PyMongoError as error:
        _avisa(operacion, error)
        raise MongoNoDisponible(
            "MongoDB no está disponible; la operación no se puede completar.") from error


def opcional(operacion, funcion, defecto=None):
    try:
        return funcion()
    except (PyMongoError, MongoNoDisponible) as error:
        _avisa(operacion, error)
        return defecto


def ping():
    base().command("ping")
    return True


def _avisa(operacion, error):
    # Uno cada 30 s: con MongoDB caído falla cada sondeo y el registro se llenaría de lo mismo.
    global _ultimo_aviso
    if time.monotonic() - _ultimo_aviso > 30:
        _ultimo_aviso = time.monotonic()
        log.warning("MongoDB no disponible en %s: %s", operacion, error)
