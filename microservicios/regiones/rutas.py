"""Servicio regiones: el estado y sus municipios, la jerarquía territorial, las jurisdicciones
sanitarias y la búsqueda territorial (D58). El catálogo de municipios sigue con las reglas de
backend_web.queries (E8 pendiente); lo nuevo vive en datos.py. Todo es público.
"""
from flask import request

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.limites import limitar
from epidemia_comun.validaciones import entero_positivo
from backend_web import queries
from backend_web.db import query

from . import datos as bd

ESTADO_NL = "19"
FUENTE_60 = "Grupos 60-79 y 80+ del Censo 2020"


def estado():
    # Su población es el agregado de sus municipios y nunca se edita aparte. El 60+ se deriva de
    # los grupos de edad: si alguien corrigió los de 60-79 u 80+, la fuente es esa corrección.
    fila = query("SELECT id, code, name, population, population_60plus FROM regions WHERE code = %s",
                 (ESTADO_NL,), one=True)
    if fila is None:
        return None
    correccion = query("""SELECT a.data_after ->> 'age_correction_reason' AS motivo, a.occurred_at AS fecha,
                                 u.full_name AS por
                          FROM audit_log a LEFT JOIN users u ON u.id = a.user_id
                          WHERE a.entity_type = 'regions' AND a.entity_id = %s
                            AND a.data_after ? 'population_by_age'
                            AND (a.data_after -> 'age_groups_modified') ?| ARRAY['60-79', '80+']
                          ORDER BY a.occurred_at DESC, a.id DESC LIMIT 1""", (str(fila["id"]),), one=True)
    if correccion is None:
        fuente_60 = {"tipo": "derivado", "fuente": FUENTE_60}
    elif correccion["motivo"] is None:
        fuente_60 = {"tipo": "censal", "fuente": FUENTE_60}
    else:
        fuente_60 = {"tipo": "manual", **correccion}
    return {"id": fila["id"], "code": fila["code"], "nombre": fila["name"],
            "poblacion": fila["population"], "poblacion_60": fila["population_60plus"],
            "fuente_poblacion": {"tipo": "agregado"}, "fuente_poblacion_60": fuente_60}


def registrar(app):
    @app.get("/api/v1/regions/state")
    @limitar("normal")
    def region_estado():
        fila = estado()
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No se encontró el estado.")
        return responder(fila, "estado")

    @app.get("/api/v1/regions")
    @limitar("normal")
    def regiones():
        buscar = (request.args.get("q") or "").strip() or None
        orden = request.args.get("order", "nombre")
        direccion = request.args.get("direction", "asc")
        if orden not in ("nombre", "poblacion", "poblacion_60"):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "order debe ser nombre, poblacion o poblacion_60.")
        if direccion not in ("asc", "desc"):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "direction debe ser asc o desc.")
        datos = queries.get_regiones_catalogo(busqueda=buscar, orden=orden, direccion=direccion)
        return responder(datos, "catalogo_regiones")

    @app.get("/api/v1/regions/<int:region_id>")
    @limitar("normal")
    def region(region_id):
        item = queries.get_region_municipio(region_id)
        if item is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No se encontró el municipio.")
        return responder(dict(item), "region")

    @app.get("/api/v1/regions/<int:region_id>/children")
    @limitar("normal")
    def hijos(region_id):
        padre = bd.region(region_id)
        if padre is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No se encontró la región.")
        filas = bd.hijos(region_id)
        return responder({"region": padre, "total": len(filas), "hijos": filas}, "jerarquia")

    @app.get("/api/v1/regions/<int:region_id>/health-areas")
    @limitar("normal")
    def jurisdicciones_de(region_id):
        item = bd.region(region_id)
        if item is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No se encontró la región.")
        filas = bd.jurisdicciones_de(item["code"])
        return responder({"region_id": region_id, "code": item["code"], "total": len(filas),
                          "jurisdicciones_sanitarias": filas}, "jurisdicciones_de_region")

    @app.get("/api/v1/health-areas")
    @limitar("normal")
    def jurisdicciones():
        filas = bd.jurisdicciones()
        return responder({"total": len(filas), "jurisdicciones_sanitarias": filas}, "jurisdicciones_sanitarias")

    @app.get("/api/v1/health-areas/<numero>")
    @limitar("normal")
    def jurisdiccion(numero):
        filas = bd.jurisdicciones(entero_positivo(numero, "numero"))
        if not filas:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe esa jurisdicción sanitaria.")
        return responder(filas[0], "jurisdiccion")

    @app.get("/api/v1/regions/search")
    @limitar("normal")
    def buscar():
        texto = (request.args.get("q") or "").strip()
        if not 2 <= len(texto) <= 80:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "q debe tener de 2 a 80 caracteres.")
        filas = bd.busca(texto)
        return responder({"q": texto, "total": len(filas), "coincidencias": filas}, "busqueda_territorial")
