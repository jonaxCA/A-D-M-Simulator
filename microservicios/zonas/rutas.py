import json

from flask import request

from epidemia_comun import cache
from epidemia_comun.ambito import clave_ambito, filtros_ambito
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo
from backend_web import queries

# Periodos de cada pantalla del monolito: Monitoreo (tabla) y Mapa.
PERIODOS_TABLA = (7, 30, 90)
PERIODOS_MAPA = (7, 30, 60)
ORDENES = ("casos", "incidencia")
TAMANO_MAXIMO = 100
TTL_CACHE = 60
# Más que los 51 municipios: "todas las zonas" para el mayor cambio.
TODAS = 1000


def mayor_cambio(zonas):
    """La zona que más aumentó en 7 días, como dato (LIMP-20).

    `zonas` son todas las del ámbito en el orden fijo de la consulta, nunca una
    página: con un empate gana la primera. Solo se nombra una zona si alguna
    aumentó; si la mayor variación es 0 o negativa, no hay zona que nombrar.
    """
    con_casos = [z for z in zonas if z["casos"]]
    if not con_casos:
        return {"estado": "sin_casos", "zona": None}
    top = max(con_casos, key=lambda z: z["variacion"])
    if top["variacion"] <= 0:
        return {"estado": "sin_aumento", "zona": None}
    return {"estado": "con_aumento",
            "zona": {"id": top["id"], "zona": top["zona"], "variacion": top["variacion"]}}


def _mapa(disease_id, dias):
    municipios = queries.get_mapa_municipios(disease_id=disease_id, dias=dias)
    for m in municipios:
        m["tendencia"] = queries.get_tendencia_zona(m["id"], disease_id=disease_id, dias=14)
    serie = queries.get_mapa_serie_temporal(disease_id=disease_id, dias=dias)
    # La consulta indexa la serie por clave INEGI ("19039"); una etiqueta XML no
    # puede empezar con dígito, así que viaja como lista.
    serie["municipios"] = [dict(region_code=code, **datos)
                           for code, datos in sorted(serie.pop("series").items())]
    return {"municipios": municipios, "serie": serie}


def registrar(app):
    # Mismo acceso que Monitoreo y Mapa en el monolito: cualquier cuenta con sesión.
    @app.get("/api/v1/zones")
    @requiere_token()
    def zonas():
        f = filtros_ambito(request.args, PERIODOS_TABLA)
        orden = request.args.get("order", "incidencia")
        if orden not in ORDENES:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "order debe ser casos o incidencia.")
        pagina = entero_positivo(request.args.get("page", "1"), "page")
        tamano = entero_positivo(request.args.get("size", "10"), "size")
        if tamano > TAMANO_MAXIMO:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "size no puede ser mayor que %d." % TAMANO_MAXIMO)
        busqueda = (request.args.get("q") or "").strip() or None
        ambito = {"disease_id": f["disease_id"], "region_id": f["region_id"], "dias": f["dias"]}

        tabla = json.dumps([busqueda, orden, pagina, tamano], ensure_ascii=False)
        datos = cache.obtener("zonas", "zones:%s:%s" % (clave_ambito(f), tabla), TTL_CACHE,
                              lambda: queries.get_monitoreo_zonas(
                                  busqueda=busqueda, orden=orden, pagina=pagina,
                                  por_pagina=tamano, **ambito))
        todas = cache.obtener("zonas", "zones-all:%s" % clave_ambito(f), TTL_CACHE,
                              lambda: queries.get_monitoreo_zonas(pagina=1, por_pagina=TODAS,
                                                                  **ambito))
        datos["filtros"] = {"disease_id": f["disease_id"], "region_id": f["region_id"],
                            "days": f["dias"], "q": busqueda, "order": orden}
        datos["mayor_cambio"] = mayor_cambio(todas["zonas"])
        return responder(datos, "zonas_detalle")

    @app.get("/api/v1/zones/map")
    @requiere_token()
    def mapa():
        f = filtros_ambito(request.args, PERIODOS_MAPA, con_region=False)
        datos = cache.obtener("zonas", "map:%s" % clave_ambito(f), TTL_CACHE,
                              lambda: _mapa(f["disease_id"], f["dias"]))
        datos["filtros"] = {"disease_id": f["disease_id"], "days": f["dias"]}
        return responder(datos, "mapa")
