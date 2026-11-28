from flask import request

from epidemia_comun import mongo
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import responder
from epidemia_comun.redis_compartido import RedisNoDisponible
from . import capacidad, sondeo

ESTADOS = ("ok", "degradado", "caido")


# Las cuatro rutas son públicas: las apps y la consola piden aquí la URL de auth antes de
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
        errores = sondeo.errores(list(sondeo.SERVICIOS)) or {}
        servicios = [dict(s, errores=errores.get(s["nombre"])) for s in servicios]
        resumen = {e: sum(s["estado"] == e for s in servicios) for e in ESTADOS}
        return responder({"resumen": resumen, "servicios": servicios}, "estado_servicios")

    # Colas y capacidad por motor (F7): sale de Redis, así que con Redis caído es 503.
    @app.get("/api/v1/services/capacity")
    def capacidad_simuladores():
        return responder(capacidad.por_motor(), "capacidad")

    # El historial sale de MongoDB (D28): con MongoDB caído responde 503, aunque Redis esté bien.
    @app.get("/api/v1/services/<nombre>/history")
    def historial(nombre):
        if nombre not in sondeo.SERVICIOS:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el servicio %s." % nombre)
        sondeos = mongo.requerido("estado-servicios: historial", lambda: sondeo.historial(nombre))
        resumen = mongo.requerido("estado-servicios: disponibilidad",
                                  lambda: sondeo.disponibilidad(nombre))
        return responder({"servicio": nombre, "resumen": resumen, "sondeos": sondeos},
                         "historial")
