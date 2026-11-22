"""Servicio vacunas: lotes de vacuna leídos por QR o código de barras, y sus dosis, y las
campañas de salud (D49).

La app escanea el código del lote, lo busca (GET con lot_code) y, si no está, lo
registra; después le descuenta las dosis que aplica. Registran y aplican CAPTURISTA
y ADMINISTRADOR; consultan los cuatro roles. Las reglas de los lotes
están en lotes.py. Las campañas las crean EPIDEMIOLOGO y ADMINISTRADOR (campanas.py).
"""
import logging

from flask import current_app, g, request

from epidemia_comun.auditoria import log_audit
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.http import llamar
from epidemia_comun.seguridad import requiere_token, token_servicio
from epidemia_comun.validaciones import diccionario, entero_positivo

from . import campanas, lotes

log = logging.getLogger(__name__)

ROLES_ESCRIBEN = ("CAPTURISTA", "ADMINISTRADOR")
ROLES_LEEN = ("CAPTURISTA", "EPIDEMIOLOGO", "ANALISTA", "ADMINISTRADOR")
ROLES_CAMPANAS = ("EPIDEMIOLOGO", "ADMINISTRADOR")
LIMITE, LIMITE_MAX = 50, 200


def _dosis(cuerpo):
    if set(cuerpo) - {"doses"}:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Solo se acepta doses.")
    dosis = cuerpo.get("doses")
    if isinstance(dosis, bool) or dosis in (None, ""):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "doses es obligatorio: cuántas dosis se aplicaron.")
    dosis = entero_positivo(dosis, "doses")
    if dosis > lotes.APLICAR_MAX:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "No se aplican más de %d dosis en una sola llamada." % lotes.APLICAR_MAX)
    return dosis


def _avisa_campana(campana, titulo):
    """Un aviso CAMPAIGN a los CAPTURISTA (D49). Best-effort: la campaña ya quedó guardada."""
    donde = campana["municipio"] if campana["region_id"] else "todo Nuevo León"
    try:
        resp = llamar("notificaciones", "POST", "/api/v1/notifications", formato="json", timeout=3,
                      token=token_servicio(current_app.config, "vacunas"),
                      cuerpo={"role": "CAPTURISTA", "type": "CAMPAIGN", "title": titulo[:160],
                              "body": "%s, del %s al %s, en %s." % (campana["enfermedad"], campana["starts_on"],
                                                                     campana["ends_on"], donde),
                              "payload": {"campaign_id": campana["id"], "status": campana["status"],
                                          "disease_id": campana["disease_id"],
                                          "region_id": campana["region_id"]}})
        if resp.status_code >= 400:
            log.warning("notificaciones respondió %d al avisar la campaña %s", resp.status_code, campana["id"])
    except Exception as exc:
        log.warning("No se pudo avisar la campaña %s: %s", campana["id"], exc)


def registrar(app):
    # ---------------------------------------------------------- campañas (D49)

    @app.get("/api/v1/campaigns")
    @requiere_token(roles=ROLES_LEEN)
    def lista_campanas():
        limite = request.args.get("limit")
        limite = LIMITE if limite is None else entero_positivo(limite, "limit")
        if limite > LIMITE_MAX:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "limit no puede pasar de %d." % LIMITE_MAX)
        estado = request.args.get("status")
        if estado is not None and estado not in campanas.ESTADOS:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "status debe ser uno de: %s." % ", ".join(campanas.ESTADOS))
        filtros = {n: entero_positivo(request.args[n], n) for n in ("disease_id", "region_id")
                   if n in request.args}
        filas = campanas.lista(estado=estado, limite=limite, **filtros)
        return responder({"total": len(filas), "campanas": filas}, "campanas")

    @app.get("/api/v1/campaigns/<campana_id>")
    @requiere_token(roles=ROLES_LEEN)
    def campana(campana_id):
        fila = campanas.por_id(entero_positivo(campana_id, "id"))
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la campaña.")
        return responder(fila, "campana")

    @app.post("/api/v1/campaigns")
    @requiere_token(roles=ROLES_CAMPANAS)
    def crea_campana():
        limpios = campanas.datos(diccionario(leer_cuerpo()))
        campanas.verifica_catalogos(limpios["disease_id"], limpios["region_id"])
        nueva = campanas.crea(limpios, g.contexto.user_id)
        log_audit(g.contexto, "CREATE", "campaigns", nueva["id"],
                  data_after={"name": nueva["name"], "disease_id": nueva["disease_id"]})
        _avisa_campana(nueva, "Campaña: %s" % nueva["name"])
        return responder(nueva, "campana", estado=201)

    @app.put("/api/v1/campaigns/<campana_id>")
    @requiere_token(roles=ROLES_CAMPANAS)
    def edita_campana(campana_id):
        campana_id = entero_positivo(campana_id, "id")
        limpios = campanas.datos(diccionario(leer_cuerpo()))
        campanas.verifica_catalogos(limpios["disease_id"], limpios["region_id"])
        fila = campanas.actualiza(campana_id, limpios)
        log_audit(g.contexto, "UPDATE", "campaigns", campana_id, data_after={"name": fila["name"]})
        return responder(fila, "campana")

    @app.post("/api/v1/campaigns/<campana_id>/cancel")
    @requiere_token(roles=ROLES_CAMPANAS)
    def cancela_campana(campana_id):
        campana_id = entero_positivo(campana_id, "id")
        razon = campanas.motivo(diccionario(leer_cuerpo()))
        fila = campanas.cancela(campana_id, razon, g.contexto.user_id)
        log_audit(g.contexto, "UPDATE", "campaigns", campana_id,
                  data_after={"status": "cancelada", "reason": razon})
        _avisa_campana(fila, "Se canceló la campaña: %s" % fila["name"])
        return responder(fila, "campana")

    # ---------------------------------------------------------- lotes y dosis

    @app.post("/api/v1/vaccine-lots")
    @requiere_token(roles=ROLES_ESCRIBEN)
    def alta():
        datos, errores = lotes.valida_lote(diccionario(leer_cuerpo()))
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        lote, creado, conflicto = lotes.registrar_lote(datos, g.contexto.user_id,
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
        filas = lotes.listar_lotes(limite=limite, **filtros)
        return responder({"total": len(filas), "lotes": filas}, "listado")

    @app.get("/api/v1/vaccine-lots/<lote_id>")
    @requiere_token(roles=ROLES_LEEN)
    def consultar(lote_id):
        lote = lotes.get_lote(entero_positivo(lote_id, "id"))
        if lote is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el lote.")
        return responder(lote, "lote_vacuna")

    @app.post("/api/v1/vaccine-lots/<lote_id>/doses")
    @requiere_token(roles=ROLES_ESCRIBEN)
    def aplicar(lote_id):
        lote_id = entero_positivo(lote_id, "id")
        lote, error = lotes.aplicar_dosis(lote_id, _dosis(diccionario(leer_cuerpo())),
                                          contexto=g.contexto)
        if error and error.startswith("No existe"):
            raise ErrorAPI(404, "NO_ENCONTRADO", error)
        if error:
            raise ErrorAPI(409, "CONFLICTO", error)
        return responder(lote, "lote_vacuna")
