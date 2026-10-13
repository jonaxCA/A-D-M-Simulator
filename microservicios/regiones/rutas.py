from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from backend_web import queries


def registrar(app):
    @app.get("/api/v1/regions")
    def regiones():
        from flask import request
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
    def region(region_id):
        item = queries.get_region_municipio(region_id)
        if item is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No se encontró el municipio.")
        return responder(dict(item), "region")
