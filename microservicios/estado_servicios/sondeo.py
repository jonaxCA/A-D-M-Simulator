import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from xml.etree.ElementTree import ParseError

import requests
from defusedxml.common import DefusedXmlException

from epidemia_comun import llaves
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import de_xml
from epidemia_comun.http import llamar
from epidemia_comun.redis_compartido import opcional

log = logging.getLogger(__name__)

# Los 26 del catálogo (docs/arquitectura/microservicios.md), en su orden, con su perfil del
# compose y su puerto. Una prueba revisa que coincidan con el catálogo y con el compose.
SERVICIOS = {
    "auth": ("identidad", 5201),
    "sesiones": ("identidad", 5202),
    "usuarios": ("identidad", 5203),
    "roles": ("identidad", 5204),
    "enfermedades": ("catalogos", 5211),
    "parametros": ("catalogos", 5212),
    "regiones": ("catalogos", 5213),
    "poblacion": ("catalogos", 5214),
    "tipos-intervencion": ("catalogos", 5215),
    "casos": ("vigilancia", 5221),
    "sincronizacion": ("vigilancia", 5222),
    "escenarios": ("escenarios", 5231),
    "intervenciones": ("escenarios", 5232),
    "aprobacion": ("escenarios", 5233),
    "validacion": ("escenarios", 5234),
    "escenarios-xml": ("escenarios", 5235),
    "corridas": ("simulacion", 5241),
    "simulador": ("simulacion", 5242),
    "resultados": ("simulacion", 5243),
    "comparacion": ("simulacion", 5244),
    "pareto": ("simulacion", 5245),
    "indicadores": ("analitica", 5251),
    "series": ("analitica", 5252),
    "zonas": ("analitica", 5253),
    "notificaciones": ("plataforma", 5261),
    "estado-servicios": ("plataforma", 5262),
}

INTERVALO = 10
# Más que los ~4 s que tarda Docker Desktop en no resolver el nombre de un contenedor
# detenido: con Redis caído, el /health de cada servicio tarda eso en responder 503.
ESPERA = 5
HISTORIAL = 30
TTL_HISTORIAL = 3600


def intervalo():
    try:
        return max(1, int(os.environ.get("SONDEO_SEGUNDOS", INTERVALO)))
    except ValueError:
        return INTERVALO


def url_publica(nombre):
    # La que usan las apps y la consola desde fuera de Docker.
    plantilla = os.environ.get("URL_PUBLICA") or "http://localhost:{puerto}"
    return plantilla.format(servicio=nombre, puerto=SERVICIOS[nombre][1])


def url_sondeo(nombre):
    # En el compose es http://{servicio}:8000, por la red interna.
    plantilla = os.environ.get("URL_SONDEO") or "http://127.0.0.1:{puerto}"
    return plantilla.format(servicio=nombre, puerto=SERVICIOS[nombre][1])


def _registro(nombre, estado, causas=(), detalle=None, version=None, latencia_ms=None):
    return {"nombre": nombre, "estado": estado, "causas": list(causas), "detalle": detalle,
            "version": version, "latencia_ms": latencia_ms,
            "revisado": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def sondear(nombre):
    inicio = time.perf_counter()
    try:
        # /health es público: no se reenvía el token de quien consulta.
        r = llamar(nombre, "GET", "/health", formato="xml", token="", timeout=ESPERA,
                   urls={nombre: url_sondeo(nombre)})
    except ErrorAPI as exc:
        agotado = isinstance(exc.__cause__, requests.Timeout)
        return _registro(nombre, "caido", ["proceso"], "tiempo_agotado" if agotado else "sin_conexion")
    latencia = round((time.perf_counter() - inicio) * 1000, 1)
    try:
        salud = de_xml(r.content)
    except (ValueError, ParseError, DefusedXmlException):
        salud = None
    # Una página de error o la salud de otro servicio: el puerto no es el de ese servicio.
    if not isinstance(salud, dict) or salud.get("servicio") != nombre:
        return _registro(nombre, "caido", ["proceso"], "respuesta_invalida", latencia_ms=latencia)
    causas = [c for c in ("postgresql", "redis") if salud.get(c) is False]
    # Manda el código, como en el HEALTHCHECK de Docker: un 503 es degradado aunque no diga por qué.
    estado = "ok" if r.status_code == 200 else "degradado"
    return _registro(nombre, estado, causas, None, salud.get("version"), latencia)


def sondear_varios(nombres):
    with ThreadPoolExecutor(max_workers=len(nombres)) as hilos:
        return list(hilos.map(sondear, nombres))


def guardar(registros):
    def escribir(r):
        p = r.pipeline(transaction=False)
        for registro in registros:
            valor = json.dumps(registro)
            historial = llaves.historial_salud(registro["nombre"])
            p.set(llaves.salud(registro["nombre"]), valor, ex=3 * intervalo())
            p.lpush(historial, valor)
            p.ltrim(historial, 0, HISTORIAL - 1)
            p.expire(historial, TTL_HISTORIAL)
        p.execute()
    opcional("estado-servicios: guardar la salud", escribir)


def ultimos(nombres):
    # None si Redis no responde.
    valores = opcional("estado-servicios: leer la salud",
                       lambda r: r.mget([llaves.salud(n) for n in nombres]))
    if valores is None:
        return None
    return {n: json.loads(v) for n, v in zip(nombres, valores) if v}


def vigentes(nombres):
    # Lo que no está en Redis (venció, Redis caído o el sondeo no ha corrido) se sondea ahora.
    guardados = ultimos(nombres)
    registros = guardados or {}
    faltan = [n for n in nombres if n not in registros]
    if faltan:
        nuevos = sondear_varios(faltan)
        # Con Redis caído, guardar solo sumaría otra espera.
        if guardados is not None:
            guardar(nuevos)
        registros.update((r["nombre"], r) for r in nuevos)
    return [registros[n] for n in nombres]


def _ciclo():
    while True:
        inicio = time.monotonic()
        try:
            guardar(sondear_varios(list(SERVICIOS)))
        except Exception:
            log.exception("Falló una ronda del sondeo")
        time.sleep(max(0, intervalo() - (time.monotonic() - inicio)))


def iniciar():
    threading.Thread(target=_ciclo, name="sondeo", daemon=True).start()
