import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from xml.etree.ElementTree import ParseError

import requests
from defusedxml.common import DefusedXmlException

from epidemia_comun import llaves, mongo
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import de_xml
from epidemia_comun.http import llamar
from epidemia_comun.redis_compartido import opcional

from . import alertas

log = logging.getLogger(__name__)

# Los del catálogo (docs/arquitectura/microservicios.md), en su orden, con su perfil del
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
    "dispositivos": ("vigilancia", 5223),
    "evidencias": ("vigilancia", 5224),
    "vacunas": ("vigilancia", 5225),
    "importacion": ("vigilancia", 5226),
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
    "calibracion": ("simulacion", 5246),
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
# El historial vive en MongoDB (D28), 30 días por su índice TTL (epidemia_comun.mongo).
COLECCION = "historial_servicios"
VERSION_ESQUEMA = 1
CONOCIDAS = [1]
VENTANA_HORAS = 24


def intervalo():
    try:
        return max(1, int(os.environ.get("SONDEO_SEGUNDOS", INTERVALO)))
    except ValueError:
        return INTERVALO


HOST_VALIDO = re.compile(r"^(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+)$")


def host_de(cabecera):
    """El host con que llegó la petición, sin el puerto («[::1]» conserva los corchetes).
    Lo que no parezca un nombre o una IP se descarta."""
    host = (cabecera or "").strip()
    host = host[:host.find("]") + 1] if host.startswith("[") else host.rsplit(":", 1)[0]
    return host if HOST_VALIDO.match(host) else None


def url_publica(nombre, host=None):
    # La que usan las apps y la consola desde fuera de Docker. Si URL_PUBLICA no está, sale del
    # host con que preguntaron: el emulador de Android llega por 10.0.2.2 y un celular por la IP
    # de la PC, y cada uno recibe direcciones que puede alcanzar.
    plantilla = os.environ.get("URL_PUBLICA") or "http://%s:{puerto}" % (host or "localhost")
    return plantilla.format(servicio=nombre, puerto=SERVICIOS[nombre][1])


def url_sondeo(nombre):
    # En el compose es http://{servicio}:8000, por la red interna.
    plantilla = os.environ.get("URL_SONDEO") or "http://127.0.0.1:{puerto}"
    return plantilla.format(servicio=nombre, puerto=SERVICIOS[nombre][1])


def _registro(nombre, estado, causas=(), detalle=None, version=None, latencia_ms=None,
              revisado=None):
    return {"nombre": nombre, "estado": estado, "causas": list(causas), "detalle": detalle,
            "version": version, "latencia_ms": latencia_ms,
            "revisado": revisado or datetime.now(timezone.utc).isoformat(timespec="seconds")}


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
    # MongoDB y el bucket valen "no_usa" si el servicio no los usa; un servicio que no trae
    # esos campos (versión anterior de la biblioteca) tampoco se marca.
    causas = [c for c in ("postgresql", "redis", "mongodb", "bucket")
              if salud.get(c) is False or salud.get(c) == "no_configurado"]
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
            p.set(llaves.salud(registro["nombre"]), json.dumps(registro), ex=3 * intervalo())
        p.execute()
    opcional("estado-servicios: guardar la salud", escribir)
    # Con MongoDB caído se pierde el historial de ese lapso: lo único que D19 admite perder.
    documentos = [_documento(r) for r in registros]
    mongo.opcional("estado-servicios: guardar el historial",
                   lambda: mongo.coleccion(COLECCION).insert_many(documentos))


def _documento(registro):
    return {"servicio": registro["nombre"], "fecha": datetime.fromisoformat(registro["revisado"]),
            "estado": registro["estado"], "latencia_ms": registro["latencia_ms"],
            "version": registro["version"], "dependencias_caidas": registro["causas"],
            "error": registro["detalle"], "version_esquema": VERSION_ESQUEMA}


def historial(nombre):
    """Los últimos sondeos de un servicio, del más reciente al más viejo, con la forma de
    siempre (la del contrato)."""
    cursor = mongo.coleccion(COLECCION).find(
        {"servicio": nombre, "version_esquema": {"$in": CONOCIDAS}})
    return [_registro(d["servicio"], d["estado"], d["dependencias_caidas"], d["error"],
                      d["version"], d["latencia_ms"], _iso(d["fecha"]))
            for d in cursor.sort([("fecha", -1), ("_id", -1)]).limit(HISTORIAL)]


def disponibilidad(nombre, ahora=None):
    """Sondeos, fracción en «ok» y latencia promedio de las últimas VENTANA_HORAS (RF-K03)."""
    desde = (ahora or datetime.now(timezone.utc)) - timedelta(hours=VENTANA_HORAS)
    filas = list(mongo.coleccion(COLECCION).aggregate([
        {"$match": {"servicio": nombre, "fecha": {"$gte": desde},
                    "version_esquema": {"$in": CONOCIDAS}}},
        {"$group": {"_id": None, "sondeos": {"$sum": 1},
                    "ok": {"$sum": {"$cond": [{"$eq": ["$estado", "ok"]}, 1, 0]}},
                    "latencia": {"$avg": "$latencia_ms"}}},
    ]))
    resumen = {"horas": VENTANA_HORAS, "sondeos": 0, "disponibilidad": None,
               "latencia_promedio_ms": None}
    # Sin sondeos en la ventana no hay grupo (mongomock sí regresa uno vacío).
    if filas and filas[0]["sondeos"]:
        f = filas[0]
        resumen.update(sondeos=f["sondeos"], disponibilidad=round(f["ok"] / f["sondeos"], 4),
                       latencia_promedio_ms=None if f["latencia"] is None
                       else round(f["latencia"], 1))
    return resumen


def _iso(fecha):
    fecha = fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc).isoformat(timespec="seconds")


def errores(nombres):
    # Errores 5xx de las últimas 24 h por servicio; None si Redis no responde.
    valores = opcional("estado-servicios: leer los errores",
                       lambda r: r.mget([llaves.errores(n) for n in nombres]))
    return None if valores is None else {n: int(v or 0) for n, v in zip(nombres, valores)}


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


def _ciclo(vigia=None):
    while True:
        inicio = time.monotonic()
        registros = None
        try:
            registros = sondear_varios(list(SERVICIOS))
            guardar(registros)
        except Exception:
            log.exception("Falló una ronda del sondeo")
        if vigia is not None and registros:
            try:
                vigia.revisar(registros)
            except Exception:
                log.exception("Falló la revisión de las alertas técnicas")
        time.sleep(max(0, intervalo() - (time.monotonic() - inicio)))


def iniciar(ajustes=None):
    # Con los ajustes de la app (el token de servicio), cada ronda revisa también las alertas
    # técnicas (alertas.py, F7).
    vigia = None
    if ajustes is not None and alertas.activas():
        vigia = alertas.Alertas(ajustes)
    elif ajustes is not None:
        log.info("Alertas técnicas apagadas: falta SERVICIO_NOTIFICACIONES_URL o ALERTAS_TECNICAS=0.")
    threading.Thread(target=_ciclo, args=(vigia,), name="sondeo", daemon=True).start()
