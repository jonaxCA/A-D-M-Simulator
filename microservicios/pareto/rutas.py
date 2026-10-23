from flask import request

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import corridas_a_comparar
from backend_web import simulaciones
from procesamiento.motor import AVISO_SIMULACION

# La frontera de Pareto vive en la pantalla Comparación del monolito: los mismos roles.
ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
MAXIMO = 50


def registrar(app):
    @app.get("/api/v1/pareto")
    @requiere_token(roles=ROLES)
    def pareto():
        ids = corridas_a_comparar(request.args.get("runs"), MAXIMO)
        # Lee las corridas, sus versiones y sus resultados directo de la base, como la
        # pantalla del monolito, mientras no exista el servicio resultados.
        comparacion, errores = simulaciones.construir_comparacion_costo_impacto(
            ids, request.args.get("metric", "fallecimientos"))
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        return responder({"aviso": AVISO_SIMULACION, **comparacion}, "pareto")
