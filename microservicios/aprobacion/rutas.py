"""Servicio aprobacion: envío a revisión, aprobación y rechazo de versiones.

Las reglas son las del monolito (backend_web.queries.envia_a_revision y
resuelve_revision); ellas escriben el estado y la bitácora (log_audit con el cursor
de la misma transacción, con el Contexto del token). Aquí solo se traducen a HTTP:
los textos de error en español son los que ya da backend_web.
"""
import logging

from flask import g

from backend_web import queries
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.http import llamar
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo

log = logging.getLogger("aprobacion")

ROLES_ENVIAN = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
ROLES_REVISAN = ("EPIDEMIOLOGO",)
ROLES_BANDEJA = ("EPIDEMIOLOGO", "ADMINISTRADOR")
DECISIONES = ("aprobar", "rechazar")


def _detalle(scenario_id):
    detalle = queries.get_escenario_detalle(entero_positivo(scenario_id, "id"))
    if detalle is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el escenario.")
    if not detalle["version"]:
        raise ErrorAPI(409, "CONFLICTO", "Ese escenario no tiene una versión vigente.")
    return detalle


def _revisar_con_validacion(version_id):
    """Pregunta al servicio validacion; devuelve sus avisos o lanza el error HTTP."""
    resp = llamar("validacion", "GET", "/api/v1/versions/%d/validation" % version_id,
                  formato="json")
    if resp.status_code == 404:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la versión.")
    if resp.status_code == 403:
        raise ErrorAPI(403, "PERMISO_INSUFICIENTE", "No tienes permiso para validar la versión.")
    if resp.status_code != 200:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE",
                       "El servicio validacion respondió %d." % resp.status_code)
    try:
        dictamen = resp.json()
    except ValueError as exc:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE",
                       "El servicio validacion devolvió una respuesta ilegible.") from exc
    if not dictamen.get("valido"):
        errores = dictamen.get("errores") or ["La versión no es válida."]
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "El motor no puede correr esta versión, así que no se envía a revisión: "
                       + " ".join(str(e) for e in errores))
    return list(dictamen.get("avisos") or [])


def _error_de_negocio(mensaje):
    """Traduce el texto de backend_web a un estado HTTP."""
    if "no tiene una versión vigente" in mensaje:
        return ErrorAPI(404, "NO_ENCONTRADO", mensaje)
    if mensaje.startswith(("El motor no puede correr", "Decisión inválida", "Para rechazar",
                           "El comentario no puede")):
        return ErrorAPI(422, "DATOS_INVALIDOS", mensaje)
    # Estado distinto, autorrevisión, cambio concurrente o CHECK de la base.
    return ErrorAPI(409, "CONFLICTO", mensaje)


def _notificar_aprobacion(escenario, version):
    """Avisa a quien armó la versión. Si falla, la aprobación ya está hecha: solo se anota."""
    try:
        resp = llamar("notificaciones", "POST", "/api/v1/notifications", formato="json", timeout=3,
                      cuerpo={"user_id": version["created_by"], "type": "SCENARIO_APPROVED",
                              "entity_type": "scenario_versions", "entity_id": version["id"],
                              "message": "Se aprobó la versión %d del escenario «%s»."
                                         % (version["version_number"], escenario["name"])})
        if resp.status_code >= 400:
            log.warning("notificaciones respondió %d al avisar la aprobación de la versión %s",
                        resp.status_code, version["id"])
    except Exception as exc:  # incluye ErrorAPI 503: nunca debe tumbar la aprobación
        log.warning("No se pudo notificar la aprobación de la versión %s: %s", version["id"], exc)


def registrar(app):
    @app.post("/api/v1/scenarios/<scenario_id>/submit")
    @requiere_token(roles=ROLES_ENVIAN)
    def enviar(scenario_id):
        detalle = _detalle(scenario_id)
        escenario, version = detalle["escenario"], detalle["version"]
        es_admin = "ADMINISTRADOR" in g.usuario.get("roles", [])
        if escenario["owner_id"] != g.contexto.user_id and not es_admin:
            raise ErrorAPI(403, "PERMISO_INSUFICIENTE",
                           "Solo quien creó el escenario puede enviarlo a revisión.")
        if version["status"] != "borrador":
            raise ErrorAPI(409, "CONFLICTO", "Esta versión ya está en «%s»: solo se envía un "
                           "borrador." % version["status"])
        avisos = _revisar_con_validacion(version["id"])
        ok, error = queries.envia_a_revision(escenario["id"], contexto=g.contexto)
        if not ok:
            raise _error_de_negocio(error)
        return responder({"scenario_id": escenario["id"], "version_id": version["id"],
                          "version_number": version["version_number"],
                          "status": "en_revision", "avisos": avisos}, "envio")

    @app.post("/api/v1/scenarios/<scenario_id>/review")
    @requiere_token(roles=ROLES_REVISAN)
    def revisar(scenario_id):
        cuerpo = diccionario(leer_cuerpo())
        decision = cuerpo.get("decision")
        comentario = cuerpo.get("comentario")
        if decision not in DECISIONES:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "decision debe ser aprobar o rechazar.")
        if comentario is not None and not isinstance(comentario, str):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "comentario debe ser texto.")
        comentario = (comentario or "").strip()
        if decision == "rechazar" and not comentario:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Para rechazar hay que explicar por qué en comentario.")
        if len(comentario) > 1000:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "El comentario no puede pasar de 1,000 caracteres.")
        detalle = _detalle(scenario_id)
        version = detalle["version"]
        if version["status"] != "en_revision":
            raise ErrorAPI(409, "CONFLICTO", "Esta versión está en «%s», no en revisión."
                           % version["status"])
        if version["created_by"] == g.contexto.user_id:
            raise ErrorAPI(409, "CONFLICTO", "No puedes revisar una versión que tú creaste: la "
                           "revisión la hace otra persona.")
        ok, error, estado = queries.resuelve_revision(
            detalle["escenario"]["id"], decision, comentario, contexto=g.contexto)
        if not ok:
            raise _error_de_negocio(error)
        if estado == "aprobado":
            _notificar_aprobacion(detalle["escenario"], version)
        return responder({"scenario_id": detalle["escenario"]["id"], "version_id": version["id"],
                          "version_number": version["version_number"], "status": estado,
                          "decision": decision}, "revision")

    @app.get("/api/v1/reviews/pending")
    @requiere_token(roles=ROLES_BANDEJA)
    def pendientes():
        filas = queries.get_pendientes_revision()
        return responder({"total": len(filas), "pendientes": filas}, "bandeja")
