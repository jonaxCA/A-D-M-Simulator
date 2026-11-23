"""Servicio poblacion: la población de cada municipio de Nuevo León y sus bandas de edad, su
corrección manual, sus versiones y sus periodos de referencia (D56). Sus reglas viven en datos.py
(E8: ya no importa backend_web).
"""
from flask import g

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo

from . import datos as bd


def _municipio(region_id):
    item = bd.get_region_municipio(region_id)
    if item is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No se encontró el municipio.")
    return dict(item)


def _conflicto_o_invalido(error):
    # Los tres mensajes de concurrencia de backend_web dicen "mientras editabas".
    if "mientras editabas" in error.lower():
        raise ErrorAPI(409, "CONFLICTO", error)
    raise ErrorAPI(422, "DATOS_INVALIDOS", error)


def registrar(app):
    @app.get("/api/v1/regions/<int:region_id>/population")
    def poblacion(region_id):
        municipio = _municipio(region_id)
        return responder({"region_id": region_id, "population": municipio["population"],
                          "population_60plus": municipio["population_60plus"]}, "poblacion")

    @app.put("/api/v1/regions/<int:region_id>/population")
    @requiere_token(roles=("ADMINISTRADOR",))
    def corregir_poblacion(region_id):
        municipio = _municipio(region_id)
        datos = diccionario(leer_cuerpo())
        if set(datos) != {"population", "expected_population", "reason"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Se requiere population, expected_population y reason.")
        try:
            esperado = entero_positivo(datos["expected_population"], "expected_population")
        except ErrorAPI:
            raise
        motivo = datos["reason"]
        if not isinstance(motivo, str):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "reason debe ser texto.")
        nueva, errores = bd.valida_poblacion_municipio(datos["population"], motivo,
                                                             municipio["population_60plus"])
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        ok, error, resultado = bd.actualiza_poblacion_municipio(
            region_id, nueva, motivo, esperado, contexto=g.contexto)
        if not ok:
            _conflicto_o_invalido(error)
        return responder(resultado, "poblacion")

    @app.get("/api/v1/regions/<int:region_id>/age-groups")
    def grupos(region_id):
        _municipio(region_id)
        grupos_edad = bd.get_grupos_edad_municipio(region_id)
        if grupos_edad is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No hay grupos de edad cargados.")
        return responder(grupos_edad, "grupos_edad")

    @app.put("/api/v1/regions/<int:region_id>/age-groups")
    @requiere_token(roles=("ADMINISTRADOR",))
    def corregir_grupos(region_id):
        _municipio(region_id)
        datos = diccionario(leer_cuerpo())
        if set(datos) != {"groups", "expected_groups", "reason"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Se requiere groups, expected_groups y reason.")
        if not isinstance(datos["groups"], dict) or not isinstance(datos["expected_groups"], dict):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "groups y expected_groups deben ser objetos.")
        if not isinstance(datos["reason"], str):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "reason debe ser texto.")
        grupos_validados, errores = bd.valida_grupos_edad_municipio(datos["groups"])
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        esperados, errores = bd.valida_grupos_edad_municipio(datos["expected_groups"])
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        # valida_grupos_edad_municipio solo regresa las cinco bandas; el control de
        # concurrencia también compara la edad no especificada, como en el monolito.
        sin_edad = datos["expected_groups"].get("edad_no_especificada")
        try:
            if isinstance(sin_edad, bool) or not isinstance(sin_edad, (int, str)):
                raise ValueError
            sin_edad = int(str(sin_edad).strip())
            if not 0 <= sin_edad <= 2147483647:
                raise ValueError
        except ValueError:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "expected_groups.edad_no_especificada debe ser un entero no negativo.")
        esperados["edad_no_especificada"] = sin_edad
        ok, error, resultado = bd.actualiza_grupos_edad_municipio(
            region_id, grupos_validados, esperados, datos["reason"], contexto=g.contexto)
        if not ok:
            _conflicto_o_invalido(error)
        return responder(resultado, "grupos_edad")

    def _region(region_id):
        item = bd.region_nl(region_id)
        if item is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No se encontró la región.")
        return item

    @app.get("/api/v1/regions/<int:region_id>/population/versions")
    def versiones(region_id):
        item = _region(region_id)
        filas = bd.versiones(region_id)
        return responder({"region_id": region_id, "code": item["code"], "total": len(filas), "versiones": filas},
                         "versiones_poblacion")

    @app.get("/api/v1/regions/<int:region_id>/population/periods")
    def periodos(region_id):
        item = _region(region_id)
        filas = bd.periodos(item["code"])
        return responder({"region_id": region_id, "code": item["code"], "total": len(filas), "censos": filas},
                         "periodos_poblacion")
