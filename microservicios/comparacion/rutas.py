from flask import request

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo
from backend_web import queries
from procesamiento.motor import AVISO_SIMULACION

# Los mismos roles que la pantalla Comparación del monolito (ROLES_LEEN_SIMULACION).
ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
# El selector del monolito ofrece las 50 corridas completadas más recientes.
MAXIMO = 50


def ids_de_corridas(texto):
    piezas = [p.strip() for p in (texto or "").split(",")]
    if not any(piezas):
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "Indica las corridas en runs, separadas por comas (por ejemplo, runs=12,15).")
    ids = []
    for pieza in piezas:
        numero = entero_positivo(pieza, "runs")
        if numero not in ids:
            ids.append(numero)
    if len(ids) < 2:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Se necesitan al menos dos corridas distintas.")
    if len(ids) > MAXIMO:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "Se pueden comparar hasta %d corridas a la vez." % MAXIMO)
    return ids


def registrar(app):
    @app.get("/api/v1/comparisons")
    @requiere_token(roles=ROLES)
    def comparar():
        ids = ids_de_corridas(request.args.get("runs"))
        corridas = queries.get_corridas_para_comparar(ids)
        # La consulta solo regresa corridas completadas con resultado guardado.
        faltan = [i for i in ids if i not in {c["id"] for c in corridas}]
        if faltan:
            raise ErrorAPI(404, "NO_ENCONTRADO",
                           "No existen, no han terminado o no tienen resultados: %s."
                           % ", ".join(map(str, faltan)))
        return responder({"aviso": AVISO_SIMULACION, "corridas": corridas}, "comparacion")
