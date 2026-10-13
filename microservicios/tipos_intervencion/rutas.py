import re

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from backend_web import queries

CODIGO = re.compile(r"[A-Z][A-Z0-9_]{0,49}")


def registrar(app):
    # Catálogo público y de solo lectura, como regiones: lo consultan las apps
    # para armar el formulario de cada intervención a partir de su param_schema.
    @app.get("/api/v1/intervention-types")
    def tipos():
        datos = queries.get_tipos_intervencion()
        return responder({"total": len(datos), "tipos": datos}, "catalogo_tipos_intervencion")

    @app.get("/api/v1/intervention-types/<code>")
    def tipo(code):
        codigo = code.strip().upper()
        if not CODIGO.fullmatch(codigo):
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el tipo de intervención.")
        for item in queries.get_tipos_intervencion():
            if item["code"] == codigo:
                return responder(item, "tipo")
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el tipo de intervención.")
