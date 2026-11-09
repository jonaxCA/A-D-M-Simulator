import json

from flask import request

from epidemia_comun import llaves
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import responder
from epidemia_comun.redis_compartido import RedisNoDisponible, requerido
from . import sondeo

ESTADOS = ("ok", "degradado", "caido")


# Las tres rutas son públicas: las apps y la consola piden aquí la URL de auth antes de
# iniciar sesión, y la salud de cada servicio ya es pública en su /health.
def registrar(app):
    @app.errorhandler(RedisNoDisponible)
    def redis_caido(exc):
        return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "Redis no está disponible."))

    @app.get("/api/v1/services")
    def directorio():
        nombres = list(sondeo.SERVICIOS)
        ultimos = sondeo.ultimos(nombres) or {}
        host = sondeo.host_de(request.host)
        servicios = []
        for nombre, (dominio, puerto) in sondeo.SERVICIOS.items():
            url = sondeo.url_publica(nombre, host)
            servicios.append({"nombre": nombre, "dominio": dominio, "puerto": puerto, "url": url,
                              "docs": url + "/docs", "openapi": url + "/openapi.json",
                              "version": ultimos.get(nombre, {}).get("version")})
        return responder({"servicios": servicios}, "directorio")

    @app.get("/api/v1/services/health")
    def salud():
        servicios = sondeo.vigentes(list(sondeo.SERVICIOS))
        resumen = {e: sum(s["estado"] == e for s in servicios) for e in ESTADOS}
        return responder({"resumen": resumen, "servicios": servicios}, "estado_servicios")

    @app.get("/api/v1/services/<nombre>/history")
    def historial(nombre):
        if nombre not in sondeo.SERVICIOS:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el servicio %s." % nombre)
        sondeos = requerido("estado-servicios: historial",
                            lambda r: r.lrange(llaves.historial_salud(nombre), 0, -1))
        return responder({"servicio": nombre, "sondeos": [json.loads(s) for s in sondeos]},
                         "historial")
