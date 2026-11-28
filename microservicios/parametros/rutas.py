"""Servicio parametros: los parámetros epidemiológicos de cada enfermedad, con su fuente, su
intervalo de incertidumbre y su historial de versiones (D58), y los ajustes que una versión de escenario
hace sobre ellos (D59). Sus reglas viven aquí (reglas.py y datos.py); los límites y el estado de cada
parámetro son los del motor (procesamiento.entrada_motor).
"""
from flask import g

from epidemia_comun import alcance
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo
from procesamiento.entrada_motor import estado_parametros

from . import datos
from .reglas import parametros_epidemiologicos

MOTIVO_MAX = 500
ROLES_LEEN = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR", "INVESTIGADOR", "AUTORIDAD_SANITARIA")
ROLES_AJUSTAN = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")


def _parametros(disease_id):
    params = datos.parametros(disease_id)
    if params is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
    return params


def _version(version_id):
    version = datos.version_de_escenario(version_id)
    if version is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la versión.")
    alcance.exige_region(version["region_id"])
    return version


def _editable(version):
    return (version["status"] == "borrador" and version["is_current"]
            and version["scenario_status"] != "archivado")


def _exige_editable(version):
    # Como las intervenciones: borrador vigente de un escenario sin archivar, de su dueño o de un ADMINISTRADOR.
    if version["scenario_status"] == "archivado":
        raise ErrorAPI(409, "CONFLICTO", "El escenario está archivado: restáuralo antes de ajustar sus parámetros.")
    if version["status"] != "borrador" or not version["is_current"]:
        raise ErrorAPI(409, "CONFLICTO", "Solo el borrador vigente se puede ajustar: para cambiar los parámetros "
                       "de una versión enviada hay que crear una versión nueva.")
    if (str(version["owner_id"]) != str(g.usuario.get("sub"))
            and "ADMINISTRADOR" not in (g.usuario.get("roles") or [])):
        raise ErrorAPI(403, "PERMISO_INSUFICIENTE", "Solo quien creó el escenario puede ajustar sus parámetros.")


def _ajustes_de(version, ajustes=None):
    ajustes = version["param_overrides"] if ajustes is None else ajustes
    catalogo = version["default_params"] or {}
    # Una versión enviada ya trae su foto (catálogo con los ajustes encima, D5); un borrador, el catálogo vivo.
    efectivos = version["disease_params"] if version["disease_params"] is not None else dict(catalogo, **ajustes)
    return {"version_id": version["id"], "scenario_id": version["scenario_id"],
            "version_number": version["version_number"], "status": version["status"],
            "editable": bool(_editable(version)), "disease_id": version["disease_id"],
            "catalogo": catalogo, "ajustes": ajustes, "efectivos": efectivos,
            "estado": estado_parametros(efectivos)}


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

    # Lo que una versión de escenario cambia del catálogo (D59). El catálogo no se toca.
    @app.get("/api/v1/versions/<int:version_id>/parameters")
    @requiere_token(roles=ROLES_LEEN)
    def ajustes_de_version(version_id):
        return responder(_ajustes_de(_version(version_id)), "ajustes_version")

    @app.put("/api/v1/versions/<int:version_id>/parameters")
    @requiere_token(roles=ROLES_AJUSTAN)
    def ajustar_version(version_id):
        cuerpo = diccionario(leer_cuerpo())
        if set(cuerpo) != {"parametros"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Envía el campo parametros; null en un parámetro quita su ajuste.")
        _version(version_id)
        datos.guardar_ajustes(version_id, _exige_editable,
                              lambda anteriores: parametros_epidemiologicos(cuerpo["parametros"], anteriores),
                              contexto=g.contexto)
        return responder(_ajustes_de(datos.version_de_escenario(version_id)), "ajustes_version")
