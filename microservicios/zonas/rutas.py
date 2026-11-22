import json
import math

from flask import Response, g, request

from epidemia_comun import cache
from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import query
from epidemia_comun.ambito import clave_ambito, filtros_ambito
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo

from . import calor, consultas, geometria, jurisdicciones

ESTADO_NL = "19"

# Periodos de cada pantalla del monolito: Monitoreo (tabla) y Mapa.
PERIODOS_TABLA = (7, 30, 90)
PERIODOS_MAPA = (7, 30, 60)
PERIODOS_CALOR = (7, 30, 60, 90)
ORDENES = ("casos", "incidencia")
TAMANO_MAXIMO = 100
TTL_CACHE = 60
# Más que los 51 municipios: "todas las zonas" para el mayor cambio.
TODAS = 1000


def _coordenada(nombre, minimo, maximo):
    crudo = request.args.get(nombre)
    try:
        valor = float(crudo)
    except (TypeError, ValueError):
        valor = math.nan
    if not math.isfinite(valor) or not minimo <= valor <= maximo:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser un número entre %g y %g." % (nombre, minimo, maximo))
    return valor


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
    municipios = consultas.get_mapa_municipios(disease_id=disease_id, dias=dias)
    for m in municipios:
        m["tendencia"] = consultas.get_tendencia_zona(m["id"], disease_id=disease_id, dias=14)
    serie = consultas.get_mapa_serie_temporal(disease_id=disease_id, dias=dias)
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
        f = filtros_ambito(request.args, PERIODOS_TABLA, catalogos=consultas)
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
                              lambda: consultas.get_monitoreo_zonas(
                                  busqueda=busqueda, orden=orden, pagina=pagina,
                                  por_pagina=tamano, **ambito))
        todas = cache.obtener("zonas", "zones-all:%s" % clave_ambito(f), TTL_CACHE,
                              lambda: consultas.get_monitoreo_zonas(pagina=1, por_pagina=TODAS,
                                                                    **ambito))
        datos["filtros"] = {"disease_id": f["disease_id"], "region_id": f["region_id"],
                            "days": f["dias"], "q": busqueda, "order": orden}
        datos["mayor_cambio"] = mayor_cambio(todas["zonas"])
        return responder(datos, "zonas_detalle")

    # Las enfermedades con casos en algún municipio de Nuevo León: el filtro del mapa y del
    # monitoreo, que no ofrece enfermedades sin nada que mostrar.
    @app.get("/api/v1/zones/diseases")
    @requiere_token()
    def enfermedades_con_casos():
        filas = cache.obtener("zonas", "diseases", TTL_CACHE, lambda: [dict(f) for f in query(
            """SELECT d.id, d.name FROM diseases d
               JOIN cases c ON c.disease_id = d.id JOIN regions r ON r.id = c.region_id
               WHERE r.parent_region_id = (SELECT id FROM regions WHERE code = %s)
               GROUP BY d.id, d.name ORDER BY d.name""", (ESTADO_NL,))])
        return responder({"total": len(filas), "enfermedades": filas}, "enfermedades_con_casos")

    # Todas las zonas del ámbito, para exportarlas: queda en la bitácora como EXPORT.
    @app.get("/api/v1/zones/export")
    @requiere_token()
    def exportar_zonas():
        f = filtros_ambito(request.args, PERIODOS_TABLA, catalogos=consultas)
        orden = request.args.get("order", "incidencia")
        if orden not in ORDENES:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "order debe ser casos o incidencia.")
        datos = consultas.get_monitoreo_zonas(
            disease_id=f["disease_id"], region_id=f["region_id"], dias=f["dias"],
            busqueda=(request.args.get("q") or "").strip() or None, orden=orden,
            pagina=1, por_pagina=TODAS)
        log_audit(g.contexto, "EXPORT", "reports", entity_id="monitoreo_zonas")
        datos["filtros"] = {"disease_id": f["disease_id"], "region_id": f["region_id"],
                            "days": f["dias"], "order": orden}
        return responder(datos, "zonas_detalle")

    # Los casos con coordenadas, agregados en celdas para un mapa de calor (calor.py, F7).
    @app.get("/api/v1/zones/heatmap")
    @requiere_token()
    def mapa_de_calor():
        f = filtros_ambito(request.args, PERIODOS_CALOR, catalogos=consultas)
        celda = request.args.get("cell") or calor.CELDAS[0]
        if celda not in calor.CELDAS:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "cell debe ser uno de: %s." % ", ".join(calor.CELDAS))
        datos = cache.obtener("zonas", "heatmap:%s:celda=%s" % (clave_ambito(f), celda), TTL_CACHE,
                              lambda: calor.calcular(celda, f["dias"], f["disease_id"],
                                                     f["region_id"]))
        datos["filtros"] = {"disease_id": f["disease_id"], "region_id": f["region_id"],
                            "days": f["dias"], "cell": float(celda)}
        return responder(datos, "mapa_calor")

    # Las mismas cifras de /zones, sumadas por jurisdicción sanitaria (jurisdicciones.py, F7).
    @app.get("/api/v1/zones/jurisdictions")
    @requiere_token()
    def por_jurisdiccion():
        f = filtros_ambito(request.args, PERIODOS_TABLA, con_region=False, catalogos=consultas)
        grupos = cache.obtener("zonas", "jurisdictions:%s" % clave_ambito(f), TTL_CACHE,
                               lambda: jurisdicciones.calcular(f["dias"], f["disease_id"]))
        return responder({"filtros": {"disease_id": f["disease_id"], "days": f["dias"]},
                          "fuente": jurisdicciones.fuente(), "jurisdicciones": grupos},
                         "zonas_por_jurisdiccion")

    # La geometría oficial de los 51 municipios (INEGI, geometria.py, F7): el GeoJSON tal cual, con
    # su ETag; con If-None-Match igual, 304 sin cuerpo. ?format no aplica.
    @app.get("/api/v1/zones/geometry")
    @requiere_token()
    def geometria_de_municipios():
        etiqueta = geometria.etag()
        cabeceras = {"ETag": etiqueta, "Cache-Control": "private, max-age=86400"}
        if request.headers.get("If-None-Match") == etiqueta:
            return Response(status=304, headers=cabeceras)
        return Response(geometria.crudo(), content_type="application/geo+json; charset=utf-8",
                        headers=cabeceras)

    # En qué municipio y jurisdicción cae un punto (F7, consultas espaciales).
    @app.get("/api/v1/zones/locate")
    @requiere_token()
    def ubicar():
        lat, lon = _coordenada("lat", -90, 90), _coordenada("lon", -180, 180)
        propiedades, aproximado = geometria.localiza(lat, lon)
        municipio = jurisdiccion = None
        if propiedades:
            codigo, nombre = propiedades["region_code"], propiedades["name"]
            ids = cache.obtener("zonas", "region-ids", TTL_CACHE, geometria.ids_de_municipios)
            municipio = {"region_id": ids.get(codigo), "region_code": codigo, "nombre": nombre}
            jurisdiccion = jurisdicciones.de_municipio(codigo, nombre)
        return responder({"lat": lat, "lon": lon, "en_nuevo_leon": municipio is not None,
                          "aproximado": aproximado, "precision_m": geometria.PRECISION_METROS,
                          "municipio": municipio, "jurisdiccion": jurisdiccion}, "ubicacion")

    @app.get("/api/v1/zones/map")
    @requiere_token()
    def mapa():
        f = filtros_ambito(request.args, PERIODOS_MAPA, con_region=False, catalogos=consultas)
        datos = cache.obtener("zonas", "map:%s" % clave_ambito(f), TTL_CACHE,
                              lambda: _mapa(f["disease_id"], f["dias"]))
        datos["filtros"] = {"disease_id": f["disease_id"], "days": f["dias"]}
        return responder(datos, "mapa")
