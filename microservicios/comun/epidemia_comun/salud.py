import os
import time

from . import archivos, mongo

DEPENDENCIAS_OPCIONALES = ("mongodb", "bucket")


def usadas(declaradas=()):
    # Las que declara el servicio en crear_app más las de DEPENDENCIAS="mongodb,bucket".
    del_entorno = os.environ.get("DEPENDENCIAS", "").replace(" ", "").split(",")
    return {d for d in tuple(declaradas) + tuple(del_entorno) if d in DEPENDENCIAS_OPCIONALES}


def _mongodb():
    if not os.environ.get("MONGO_URL"):
        return "no_configurado"
    return mongo.ping()


def _bucket():
    if not archivos.configurado():
        return "no_configurado"
    return archivos.ping()


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
