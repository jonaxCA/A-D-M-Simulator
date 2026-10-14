from flask import request

from epidemia_comun import cache
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.validaciones import entero_positivo
from backend_web import queries

LIMITE_MAXIMO = 20
TTL_CACHE = 60


def registrar(app):
    # Públicas, como el dashboard del monolito, que se ve sin iniciar sesión.
    @app.get("/api/v1/dashboard/indicators")
    def indicadores():
        datos = cache.obtener("indicadores", "indicators", TTL_CACHE,
                              queries.get_resumen_indicadores)
        return responder(datos, "indicadores")

    @app.get("/api/v1/dashboard/situation")
    def situacion():
        limite = entero_positivo(request.args.get("limit", "5"), "limit")
        if limite > LIMITE_MAXIMO:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "limit no puede ser mayor que %d." % LIMITE_MAXIMO)
        filas = cache.obtener("indicadores", "situation:limit=%d" % limite, TTL_CACHE,
                              lambda: queries.get_resumen_situacion(limit=limite))
        return responder({"enfermedades": filas}, "situacion")
