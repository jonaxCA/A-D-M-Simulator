from epidemia_comun import cola, llaves
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import responder
from epidemia_comun.redis_compartido import RedisNoDisponible
from epidemia_comun.seguridad import requiere_token
from . import trabajador

# Los mismos roles que leen corridas en el monolito (ROLES_LEEN_SIMULACION).
ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")


def registrar(app):
    @app.errorhandler(RedisNoDisponible)
    def redis_caido(exc):
        return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "Redis no está disponible."))

    @app.get("/api/v1/worker/status")
    @requiere_token(roles=ROLES)
    def estado():
        return responder(dict(trabajador.estado, pendientes=cola.pendientes(llaves.COLA_SIMULACIONES)),
                         "trabajador")
