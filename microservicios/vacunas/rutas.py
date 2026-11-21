"""Servicio vacunas: lotes de vacuna leídos por QR o código de barras, y sus dosis.

La app escanea el código del lote, lo busca (GET con lot_code) y, si no está, lo
registra; después le descuenta las dosis que aplica. Registran y aplican CAPTURISTA
y ADMINISTRADOR; consultan los cuatro roles. Las reglas están en
backend_web.vacunas.
"""
from flask import g, request

from backend_web import vacunas
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo

ROLES_ESCRIBEN = ("CAPTURISTA", "ADMINISTRADOR")
ROLES_LEEN = ("CAPTURISTA", "EPIDEMIOLOGO", "ANALISTA", "ADMINISTRADOR")
LIMITE, LIMITE_MAX = 50, 200


def _dosis(cuerpo):
    if set(cuerpo) - {"doses"}:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Solo se acepta doses.")
    dosis = cuerpo.get("doses")
    if isinstance(dosis, bool) or dosis in (None, ""):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "doses es obligatorio: cuántas dosis se aplicaron.")
    dosis = entero_positivo(dosis, "doses")
    if dosis > vacunas.APLICAR_MAX:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "No se aplican más de %d dosis en una sola llamada." % vacunas.APLICAR_MAX)
    return dosis


def registrar(app):
    @app.post("/api/v1/vaccine-lots")
    @requiere_token(roles=ROLES_ESCRIBEN)
    def alta():
        datos, errores = vacunas.valida_lote(diccionario(leer_cuerpo()))
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        lote, creado, conflicto = vacunas.registrar_lote(datos, g.contexto.user_id,
                                                         contexto=g.contexto)
        if conflicto:
            raise ErrorAPI(409, "CONFLICTO", conflicto)
        return responder(lote, "lote_vacuna", estado=201 if creado else 200)

    @app.get("/api/v1/vaccine-lots")
    @requiere_token(roles=ROLES_LEEN)
    def listar():
        limite = request.args.get("limit")
        limite = LIMITE if limite is None else entero_positivo(limite, "limit")
        if limite > LIMITE_MAX:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "limit no puede pasar de %d." % LIMITE_MAX)
        filtros = {}
        for nombre in ("disease_id", "region_id"):
            if nombre in request.args:
                filtros[nombre] = entero_positivo(request.args[nombre], nombre)
        if "lot_code" in request.args:
            filtros["lot_code"] = request.args["lot_code"].strip()
        filas = vacunas.listar_lotes(limite=limite, **filtros)
        return responder({"total": len(filas), "lotes": filas}, "listado")

    @app.get("/api/v1/vaccine-lots/<lote_id>")
    @requiere_token(roles=ROLES_LEEN)
    def consultar(lote_id):
        lote = vacunas.get_lote(entero_positivo(lote_id, "id"))
        if lote is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el lote.")
        return responder(lote, "lote_vacuna")

    @app.post("/api/v1/vaccine-lots/<lote_id>/doses")
    @requiere_token(roles=ROLES_ESCRIBEN)
    def aplicar(lote_id):
        lote_id = entero_positivo(lote_id, "id")
        lote, error = vacunas.aplicar_dosis(lote_id, _dosis(diccionario(leer_cuerpo())),
                                            contexto=g.contexto)
        if error and error.startswith("No existe"):
            raise ErrorAPI(404, "NO_ENCONTRADO", error)
        if error:
            raise ErrorAPI(409, "CONFLICTO", error)
        return responder(lote, "lote_vacuna")
