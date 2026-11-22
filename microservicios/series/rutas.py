import json

from flask import request

from epidemia_comun import cache
from epidemia_comun.ambito import clave_ambito, filtros_ambito
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo

from . import agregadas, consultas

# Los periodos de la pantalla de Monitoreo del monolito.
PERIODOS = (7, 30, 90)
TTL_CACHE = 60


def _consulta(nombre, funcion):
    f = filtros_ambito(request.args, PERIODOS, catalogos=consultas)
    datos = cache.obtener("series", "%s:%s" % (nombre, clave_ambito(f)), TTL_CACHE,
                          lambda: funcion(disease_id=f["disease_id"],
                                          region_id=f["region_id"], dias=f["dias"]))
    return f, datos


def _filtros(f):
    return {"disease_id": f["disease_id"], "region_id": f["region_id"], "days": f["dias"]}


def _agregadas():
    # Rango libre, intervalo y grupo (agregadas.py, F7); los filtros de enfermedad y municipio,
    # con sus 404, son los de siempre.
    f = filtros_ambito(request.args, PERIODOS, catalogos=consultas)
    dias = f["dias"] if request.args.get("days") not in (None, "") else None
    desde, hasta = agregadas.rango(request.args, dias)
    filtros = {"disease_id": f["disease_id"], "region_id": f["region_id"],
               "desde": desde.isoformat(), "hasta": hasta.isoformat(),
               "intervalo": agregadas.opcion(request.args, "interval", agregadas.INTERVALOS, "dia"),
               "agrupar": agregadas.opcion(request.args, "group_by", agregadas.AGRUPACIONES)}
    datos = cache.obtener("series", "aggregate:%s" % json.dumps(filtros, sort_keys=True), TTL_CACHE,
                          lambda: agregadas.calcular(desde, hasta, filtros["intervalo"],
                                                     filtros["agrupar"], f["disease_id"],
                                                     f["region_id"]))
    return filtros, datos


def registrar(app):
    # Mismo acceso que Monitoreo en el monolito: cualquier cuenta con sesión.
    @app.get("/api/v1/series/cases")
    @requiere_token()
    def curva():
        f, puntos = _consulta("cases", consultas.get_monitoreo_serie)
        return responder({"filtros": _filtros(f), "puntos": puntos}, "curva_epidemica")

    @app.get("/api/v1/series/cases/by-age")
    @requiere_token()
    def por_edad():
        f, grupos = _consulta("by-age", consultas.get_monitoreo_edad)
        return responder({"filtros": _filtros(f), "grupos": grupos}, "casos_por_edad")

    @app.get("/api/v1/series/cases/by-sex")
    @requiere_token()
    def por_sexo():
        f, sexos = _consulta("by-sex", consultas.get_monitoreo_sexo)
        return responder({"filtros": _filtros(f), "sexos": sexos}, "casos_por_sexo")

    @app.get("/api/v1/series/cases/totals")
    @requiere_token()
    def totales():
        f, datos = _consulta("totals", consultas.get_monitoreo_totales)
        return responder({"filtros": _filtros(f), "totales": datos}, "totales")

    @app.get("/api/v1/series/cases/aggregate")
    @requiere_token()
    def agregada():
        numero = entero_positivo(request.args.get("page", "1"), "page")
        tamano = entero_positivo(request.args.get("size", str(agregadas.TAMANO_POR_OMISION)), "size")
        if tamano > agregadas.TAMANO_MAXIMO:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "size no puede ser mayor que %d." % agregadas.TAMANO_MAXIMO)
        filtros, datos = _agregadas()
        return responder(dict(agregadas.pagina(datos, numero, tamano), filtros=filtros),
                         "serie_agregada")

    # La misma serie, sin paginar, como la espera Highcharts: {xAxis, yAxis, series}.
    @app.get("/api/v1/series/cases/highcharts")
    @requiere_token()
    def para_highcharts():
        filtros, datos = _agregadas()
        return responder(dict(agregadas.highcharts(datos), filtros=filtros), "highcharts")
