from flask import request

from epidemia_comun import alcance
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo
from procesamiento.analitica import (SensibilidadInvalida, sensibilidad, valores_por_porcentaje,
                                     PARAMETROS)
from procesamiento.categoria import ESTADO, estado_modelo
from procesamiento.motor import AVISO_SIMULACION

from . import datos, dominio
from .seleccion import corridas_a_comparar

# La frontera de Pareto vive en la pantalla Comparación del monolito: los mismos roles.
ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR", "INVESTIGADOR", "AUTORIDAD_SANITARIA")
MAXIMO = 50


def numeros(texto, campo):
    try:
        return [float(p) for p in texto.split(",")]
    except ValueError:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser una lista de numeros separados por comas." % campo)


def registrar(app):
    @app.get("/api/v1/pareto")
    @requiere_token(roles=ROLES)
    def pareto():
        ids = corridas_a_comparar(request.args.get("runs"), MAXIMO)
        permitidas = alcance.regiones_permitidas()
        if permitidas is not None and not datos.regiones_de_corridas(ids) <= permitidas:
            raise ErrorAPI(403, "PERMISO_INSUFICIENTE", "Hay corridas fuera del alcance de tu cuenta.")
        comparacion, errores = dominio.construir_comparacion_costo_impacto(
            ids, request.args.get("metric", "fallecimientos"))
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        return responder({"aviso": AVISO_SIMULACION, **comparacion}, "pareto")

    @app.get("/api/v1/pareto/sensitivity")
    @requiere_token(roles=ROLES)
    def sensibilidad_ruta():
        parametro = request.args.get("parameter", "")
        if parametro not in PARAMETROS:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "parameter debe ser uno de: " + ", ".join(PARAMETROS) + ".")
        valores, porcentajes = request.args.get("values"), request.args.get("percent")
        if (valores is None) == (porcentajes is None):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Indica values o percent, solo uno.")
        version = entero_positivo(request.args.get("version"), "version")
        alcance.exige_region_de(lambda: datos.region_de_version(version))
        escenario, _, errores = dominio.construir_escenario_desde_version(version)
        if errores:
            if escenario is None and "no existe" in errores[0]:
                raise ErrorAPI(404, "NO_ENCONTRADO", errores[0])
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        if valores is not None:
            lista = numeros(valores, "values")
        else:
            lista = valores_por_porcentaje(escenario, parametro, numeros(porcentajes, "percent"))
        try:
            resultado = sensibilidad(escenario, parametro, lista, request.args.get("metric", "fallecimientos"))
        except SensibilidadInvalida as ex:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(ex.errores))
        return responder({"aviso": AVISO_SIMULACION, "version": version, **resultado}, "sensibilidad")

    @app.get("/api/v1/pareto/calibration")
    @requiere_token(roles=ROLES)
    def calibracion_estado():
        version = request.args.get("engine")
        if version is not None and version not in ESTADO:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "engine debe ser uno de: " + ", ".join(ESTADO) + ".")
        enfermedad = entero_positivo(request.args["disease"], "disease") if "disease" in request.args else None
        region = entero_positivo(request.args["region"], "region") if "region" in request.args else None
        modelos = [estado_modelo(v, enfermedad, region) for v in ([version] if version else ESTADO)]
        return responder({"aviso": AVISO_SIMULACION, "disponible": False, "ejecucion": "no_disponible", "modelos": modelos,
                          "nota": "La calibracion la corre el servicio calibracion (D50): /api/v1/calibrations. Esta ruta solo "
                                  "informa el estado y se retira cuando el escritorio use /api/v1/calibrations/state (D46)."}, "calibracion")
