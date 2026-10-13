from flask import request

from epidemia_comun import cache
from epidemia_comun.ambito import clave_ambito, filtros_ambito
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from backend_web import queries

# Los periodos de la pantalla de Monitoreo del monolito.
PERIODOS = (7, 30, 90)
TTL_CACHE = 60


def _consulta(nombre, funcion):
    f = filtros_ambito(request.args, PERIODOS)
    datos = cache.obtener("series", "%s:%s" % (nombre, clave_ambito(f)), TTL_CACHE,
                          lambda: funcion(disease_id=f["disease_id"],
                                          region_id=f["region_id"], dias=f["dias"]))
    return f, datos


def _filtros(f):
    return {"disease_id": f["disease_id"], "region_id": f["region_id"], "days": f["dias"]}


def registrar(app):
    # Mismo acceso que Monitoreo en el monolito: cualquier cuenta con sesión.
    @app.get("/api/v1/series/cases")
    @requiere_token()
    def curva():
        f, puntos = _consulta("cases", queries.get_monitoreo_serie)
        return responder({"filtros": _filtros(f), "puntos": puntos}, "curva_epidemica")

    @app.get("/api/v1/series/cases/by-age")
    @requiere_token()
    def por_edad():
        f, grupos = _consulta("by-age", queries.get_monitoreo_edad)
        return responder({"filtros": _filtros(f), "grupos": grupos}, "casos_por_edad")

    @app.get("/api/v1/series/cases/by-sex")
    @requiere_token()
    def por_sexo():
        f, sexos = _consulta("by-sex", queries.get_monitoreo_sexo)
        return responder({"filtros": _filtros(f), "sexos": sexos}, "casos_por_sexo")

    @app.get("/api/v1/series/cases/totals")
    @requiere_token()
    def totales():
        f, datos = _consulta("totals", queries.get_monitoreo_totales)
        return responder({"filtros": _filtros(f), "totales": datos}, "totales")
