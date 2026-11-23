"""Servicio tipos-intervencion: el catálogo de tipos de intervención y los supuestos de efectividad de
cada uno (D56). Leer es público, como regiones; los supuestos los cambian EPIDEMIOLOGO y
ADMINISTRADOR. Sus reglas viven en datos.py (E8: ya no importa backend_web).
"""
import math
import re

from flask import g

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario

from . import datos

CODIGO = re.compile(r"[A-Z][A-Z0-9_]{0,49}")
# Los parámetros de efecto que puede llevar un tipo, si su param_schema los tiene.
PARAMETROS_EFECTO = ("eficacia", "reduccion", "deteccion")
CAMPOS = {"parametro", "enfermedad", "valor", "min", "max", "fuente", "supuesto"}


def _invalido(mensaje):
    return ErrorAPI(422, "DATOS_INVALIDOS", mensaje)


def _tipo(code):
    codigo = code.strip().upper()
    if CODIGO.fullmatch(codigo):
        for item in datos.tipos():
            if item["code"] == codigo:
                return item
    raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el tipo de intervención.")


def _fraccion(valor, campo):
    # None se queda en None; en XML los números llegan como texto.
    if valor is None:
        return None
    if isinstance(valor, str):
        try:
            valor = float(valor)
        except ValueError:
            pass
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) \
            or not 0 <= valor <= 1:
        raise _invalido("%s debe ser un número de 0 a 1." % campo)
    return float(valor)


def _supuesto(cuerpo, tipo):
    cuerpo = diccionario(cuerpo)
    if set(cuerpo) - CAMPOS or not {"parametro", "fuente", "supuesto"} <= set(cuerpo):
        raise _invalido("Se requieren parametro, fuente y supuesto; opcionales: enfermedad, valor, min y max.")
    parametro = cuerpo["parametro"]
    propios = [p for p in PARAMETROS_EFECTO if p in ((tipo["param_schema"] or {}).get("properties") or {})]
    if parametro not in propios:
        raise _invalido("El parámetro de efecto de %s es: %s." % (tipo["code"], ", ".join(propios) or "ninguno"))
    valores = {"valor": _fraccion(cuerpo.get("valor"), "valor"), "min": _fraccion(cuerpo.get("min"), "min"),
               "max": _fraccion(cuerpo.get("max"), "max")}
    conocidos = [v for v in (valores["min"], valores["valor"], valores["max"]) if v is not None]
    if conocidos != sorted(conocidos):
        raise _invalido("Debe cumplirse min <= valor <= max.")
    fuente = cuerpo["fuente"]
    if not isinstance(fuente, str) or not 3 <= len(fuente.strip()) <= 2000:
        raise _invalido("fuente debe ser texto de 3 a 2,000 caracteres: la cita o el razonamiento del supuesto.")
    supuesto = cuerpo["supuesto"]
    if isinstance(supuesto, str) and supuesto.lower() in ("true", "false"):
        supuesto = supuesto.lower() == "true"
    if not isinstance(supuesto, bool):
        raise _invalido("supuesto debe ser booleano.")
    enfermedad = cuerpo.get("enfermedad")
    if enfermedad in (None, ""):
        disease_id = None
    else:
        disease_id = datos.enfermedad_id(str(enfermedad).strip().upper())
        if disease_id is None:
            raise _invalido("No existe la enfermedad %s." % enfermedad)
    return parametro, disease_id, dict(valores, fuente=fuente.strip(), supuesto=supuesto)


def registrar(app):
    # Catálogo público y de solo lectura, como regiones: lo consultan las apps
    # para armar el formulario de cada intervención a partir de su param_schema.
    @app.get("/api/v1/intervention-types")
    def tipos():
        lista = datos.tipos()
        return responder({"total": len(lista), "tipos": lista}, "catalogo_tipos_intervencion")

    @app.get("/api/v1/intervention-types/<code>")
    def tipo(code):
        item = _tipo(code)
        return responder(dict(item, efectividad=datos.efectividad(item["id"])), "tipo")

    @app.get("/api/v1/intervention-types/<code>/effectiveness")
    def efectividad(code):
        item = _tipo(code)
        lista = datos.efectividad(item["id"])
        return responder({"code": item["code"], "total": len(lista), "efectividad": lista},
                         "efectividad_tipo")

    @app.put("/api/v1/intervention-types/<code>/effectiveness")
    @requiere_token(roles=("EPIDEMIOLOGO", "ADMINISTRADOR"))
    def guardar_efectividad(code):
        item = _tipo(code)
        parametro, disease_id, valores = _supuesto(leer_cuerpo(), item)
        nuevo = datos.guarda_efectividad(item["id"], parametro, disease_id, valores, contexto=g.contexto)
        return responder(dict(datos.efectividad_de(item["id"], parametro, disease_id), code=item["code"]),
                         "supuesto", estado=201 if nuevo else 200)
