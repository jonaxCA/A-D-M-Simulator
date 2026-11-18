import os
import socket
import time
from urllib.parse import urlparse

import requests

DEPENDENCIAS_OPCIONALES = ("mongodb", "bucket")
ESPERA = 2


def usadas(declaradas=()):
    # Las que declara el servicio en crear_app más las de DEPENDENCIAS="mongodb,bucket".
    del_entorno = os.environ.get("DEPENDENCIAS", "").replace(" ", "").split(",")
    return {d for d in tuple(declaradas) + tuple(del_entorno) if d in DEPENDENCIAS_OPCIONALES}


def _mongodb():
    # Basta abrir el puerto: el cliente de epidemia_comun (bloque D) puede cambiar esto por un ping.
    url = os.environ.get("MONGO_URL")
    if not url:
        return "no_configurado"
    destino = urlparse(url.split(",")[0] if "," in url else url)
    socket.create_connection((destino.hostname, destino.port or 27017), ESPERA).close()
    return True


def _bucket():
    # Cualquier respuesta por debajo de 500 cuenta como viva: el emulador responde 404 en "/".
    url = os.environ.get("BUCKET_HEALTH_URL") or os.environ.get("BUCKET_URL")
    if not url:
        return "no_configurado"
    return requests.get(url, timeout=ESPERA).status_code < 500


REVISIONES = {"mongodb": _mongodb, "bucket": _bucket}


def revisar(nombre, comprobar):
    inicio = time.perf_counter()
    try:
        resultado = comprobar()
    except Exception:
        resultado = False
    return resultado, round((time.perf_counter() - inicio) * 1000, 1)


def informe(redis, postgres, declaradas=()):
    inicio = time.perf_counter()
    en_uso = usadas(declaradas)
    revisiones = {"postgresql": postgres, "redis": redis}
    revisiones.update({d: REVISIONES[d] for d in sorted(en_uso)})
    resultados, tiempos = {}, {}
    for nombre, comprobar in revisiones.items():
        resultados[nombre], tiempos[nombre] = revisar(nombre, comprobar)
    for d in DEPENDENCIAS_OPCIONALES:
        resultados.setdefault(d, "no_usa")
    sano = all(v is True or v == "no_usa" for v in resultados.values())
    datos = {k: resultados[k] for k in ("postgresql", "redis", "mongodb", "bucket")}
    datos["tiempos_ms"] = tiempos
    datos["tiempo_ms"] = round((time.perf_counter() - inicio) * 1000, 1)
    return sano, datos
