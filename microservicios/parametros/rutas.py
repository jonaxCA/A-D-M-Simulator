"""Servicio parametros: los parámetros epidemiológicos de cada enfermedad, con su fuente, su
intervalo de incertidumbre y su historial de versiones (D58). Sus reglas viven aquí (reglas.py y
datos.py); los límites y el estado de cada parámetro son los del motor (procesamiento.entrada_motor).
"""
from flask import g

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo
from procesamiento.entrada_motor import estado_parametros

from . import datos
from .reglas import parametros_epidemiologicos

MOTIVO_MAX = 500


def _parametros(disease_id):
    params = datos.parametros(disease_id)
    if params is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
    return params


def registrar(app):
    @app.get("/api/v1/diseases/<int:disease_id>/parameters")
    def consultar(disease_id):
        return responder({"disease_id": disease_id, "parametros": _parametros(disease_id)}, "parametros")

    @app.get("/api/v1/diseases/<int:disease_id>/parameters/status")
    def estado(disease_id):
        return responder(estado_parametros(_parametros(disease_id)), "estado_parametros")

    @app.get("/api/v1/diseases/<int:disease_id>/parameters/versions")
    def versiones(disease_id):
        _parametros(disease_id)
        filas = datos.versiones(disease_id)
        return responder({"disease_id": disease_id, "total": len(filas), "versiones": filas},
                         "versiones_parametros")

    @app.get("/api/v1/diseases/<int:disease_id>/parameters/versions/<version>")
    def version(disease_id, version):
        fila = datos.version(disease_id, entero_positivo(version, "version"))
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe esa versión de los parámetros.")
        return responder(dict(fila, disease_id=disease_id), "version_parametros")

    @app.put("/api/v1/diseases/<int:disease_id>/parameters")
    @requiere_token(roles=("EPIDEMIOLOGO", "ADMINISTRADOR"))
    def actualizar(disease_id):
        cuerpo = diccionario(leer_cuerpo())
        if "parametros" not in cuerpo or set(cuerpo) - {"parametros", "motivo"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Envía el campo parametros y, si quieres, motivo.")
        motivo = cuerpo.get("motivo")
        if motivo is not None and (not isinstance(motivo, str) or len(motivo.strip()) > MOTIVO_MAX):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "motivo debe ser texto de hasta 500 caracteres.")
        nuevos, numero = datos.guardar(
            disease_id, lambda anteriores: parametros_epidemiologicos(cuerpo["parametros"], anteriores),
            (motivo or "").strip() or None, contexto=g.contexto)
        return responder({"disease_id": disease_id, "parametros": nuevos, "version": numero}, "parametros")
