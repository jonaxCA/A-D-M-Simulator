import logging
import os
import threading
import time

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

log = logging.getLogger(__name__)

_candado = threading.Lock()
_clientes = {}
_fijo = None
_ultimo_aviso = 0.0


class RedisNoDisponible(Exception):
    codigo = "REDIS_NO_DISPONIBLE"
    http = 503


def cliente(espera=0):
    # `espera` son los segundos que un comando puede quedarse bloqueado (BRPOP de
    # la cola); por eso esos comandos usan otro cliente, con un timeout más largo.
    if _fijo is not None:
        return _fijo
    with _candado:
        if espera not in _clientes:
            limite = float(os.environ.get("REDIS_TIMEOUT_SECONDS", "0.5"))
            _clientes[espera] = redis.Redis.from_url(
                os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
                decode_responses=True,
                socket_timeout=limite + espera,
                socket_connect_timeout=limite,
                health_check_interval=15,
                # Un reintento inmediato, para una conexión que se cerró. Sin la espera
                # creciente de redis-py, que con Redis caído alarga cada petición.
                retry=Retry(NoBackoff(), 1),
            )
        return _clientes[espera]


def usar(nuevo):
    global _fijo
    with _candado:
        _fijo = nuevo
        _clientes.clear()


def requerido(operacion, funcion, espera=0):
    try:
        return funcion(cliente(espera))
    except redis.RedisError as error:
        _avisa(operacion, error)
        raise RedisNoDisponible(
            "Redis no está disponible; la operación no se puede completar con seguridad."
        ) from error


def opcional(operacion, funcion, defecto=None):
    try:
        return funcion(cliente())
    except redis.RedisError as error:
        _avisa(operacion, error)
        return defecto


def transaccion(operacion, funcion, *vigilar):
    # funcion(p) lee con p, llama p.multi() antes de escribir y regresa el resultado.
    # Si otra petición cambió una llave vigilada, redis-py la vuelve a correr.
    return requerido(
        operacion, lambda r: r.transaction(funcion, *vigilar, value_from_callable=True)
    )


def estado():
    inicio = time.perf_counter()
    try:
        cliente().ping()
    except redis.RedisError as error:
        return {"estado": "caido", "detalle": type(error).__name__}
    return {"estado": "ok", "latencia_ms": round((time.perf_counter() - inicio) * 1000, 1)}


def _avisa(operacion, error):
    # Uno cada 30 s: con Redis caído falla cada petición y el registro se llenaría de lo mismo.
    global _ultimo_aviso
    if time.monotonic() - _ultimo_aviso > 30:
        _ultimo_aviso = time.monotonic()
        log.warning("Redis no disponible en %s: %s", operacion, error)
