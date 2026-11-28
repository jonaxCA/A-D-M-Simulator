"""Servicio aprobacion: envío a revisión, aprobación (con su firma), rechazo y devolución.

Las reglas viven en datos.py (E8: antes en backend_web.queries); ellas escriben el estado y la
bitácora en la misma transacción, con el Contexto del token. El motor lo revisa el servicio
validacion, que además da la huella de la entrada del motor con la que se firma la versión
aprobada (D55).
"""
import logging

from flask import current_app, g

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.http import llamar
from epidemia_comun.seguridad import requiere_token, token_servicio
from epidemia_comun.validaciones import diccionario, entero_positivo

from . import datos

log = logging.getLogger("aprobacion")

ROLES_ENVIAN = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
# scenarios.approve (D1, 034): ninguno revisa la versión que creó.
ROLES_REVISAN = ("EPIDEMIOLOGO", "ADMINISTRADOR")
ROLES_BANDEJA = ("EPIDEMIOLOGO", "ADMINISTRADOR")
# Los mismos de validacion: la firma se recalcula allá con el token de quien pregunta.
ROLES_FIRMA = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
DECISIONES = tuple(datos.DECISIONES)


def _detalle(scenario_id):
    encontrado = datos.escenario_y_version(entero_positivo(scenario_id, "id"))
    if encontrado is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el escenario.")
    escenario, version = encontrado
    if not version:
        raise ErrorAPI(409, "CONFLICTO", "Ese escenario no tiene una versión vigente.")
    return {"escenario": escenario, "version": version}


def _dictamen(version_id):
    """Pregunta al servicio validacion; devuelve su dictamen (valido, errores, avisos y huella)."""
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
        return resp.json()
    except ValueError as exc:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE",
                       "El servicio validacion devolvió una respuesta ilegible.") from exc


def _revisar_con_validacion(version_id, para):
    """El dictamen de una versión que el motor sí puede correr; si no, 422."""
    dictamen = _dictamen(version_id)
    if not dictamen.get("valido"):
        errores = dictamen.get("errores") or ["La versión no es válida."]
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "El motor no puede correr esta versión, así que no se %s: " % para
                       + " ".join(str(e) for e in errores))
    return dictamen


def _avisar(destino, tipo, titulo, cuerpo, payload, version_id):
    # Si falla, el cambio de estado ya está hecho: solo se anota. Va con token de servicio.
    # destino es {"user_id": n} o {"role": "EPIDEMIOLOGO"}.
    try:
        resp = llamar("notificaciones", "POST", "/api/v1/notifications", formato="json", timeout=3,
                      token=token_servicio(current_app.config, "aprobacion"),
                      cuerpo=dict(destino, type=tipo, title=titulo, body=cuerpo, payload=payload))
        if resp.status_code >= 400:
            log.warning("notificaciones respondió %d al avisar %s de la versión %s",
                        resp.status_code, tipo, version_id)
    except Exception as exc:  # incluye ErrorAPI 503: nunca debe tumbar la operación
        log.warning("No se pudo avisar %s de la versión %s: %s", tipo, version_id, exc)


def _payload(escenario, version):
    return {"scenario_id": escenario["id"], "version_id": version["id"],
            "version_number": version["version_number"]}


def _notificar_aprobacion(escenario, version):
    _avisar({"user_id": version["created_by"]}, "SCENARIO_APPROVED",
            "Versión %d aprobada" % version["version_number"],
            "Se aprobó la versión %d del escenario «%s»." % (version["version_number"], escenario["name"]),
            _payload(escenario, version), version["id"])


def _notificar_rechazo(escenario, version, comentario):
    _avisar({"user_id": version["created_by"]}, "SCENARIO_REJECTED",
            "Versión %d rechazada" % version["version_number"],
            "Se rechazó la versión %d del escenario «%s»: %s"
            % (version["version_number"], escenario["name"], comentario),
            _payload(escenario, version), version["id"])


def _notificar_devolucion(escenario, version, comentario):
    _avisar({"user_id": version["created_by"]}, "SCENARIO_RETURNED",
            "Versión %d devuelta para cambios" % version["version_number"],
            "Se devolvió la versión %d del escenario «%s» para cambios: %s"
            % (version["version_number"], escenario["name"], comentario),
            _payload(escenario, version), version["id"])


def _notificar_envio(escenario, version):
    _avisar({"role": "EPIDEMIOLOGO"}, "SCENARIO_SUBMITTED",
            "Versión %d por revisar" % version["version_number"],
            "Se envió a revisión la versión %d del escenario «%s»."
            % (version["version_number"], escenario["name"]),
            _payload(escenario, version), version["id"])


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
        if escenario["status"] == "archivado":
            raise ErrorAPI(409, "CONFLICTO", "El escenario está archivado: restáuralo antes de "
                           "enviarlo a revisión.")
        if version["status"] != "borrador":
            raise ErrorAPI(409, "CONFLICTO", "Esta versión ya está en «%s»: solo se envía un "
                           "borrador." % version["status"])
        avisos = list(_revisar_con_validacion(version["id"], "envía a revisión").get("avisos") or [])
        datos.envia(version["id"], contexto=g.contexto)
        _notificar_envio(escenario, version)
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
            raise ErrorAPI(422, "DATOS_INVALIDOS", "decision debe ser aprobar, rechazar o devolver.")
        if comentario is not None and not isinstance(comentario, str):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "comentario debe ser texto.")
        comentario = (comentario or "").strip()
        if decision != "aprobar" and not comentario:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Para %s hay que explicar por qué en comentario: es "
                           "lo único que tiene quien va a corregir." % decision)
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
        # La firma (D55): la huella de la entrada del motor en el momento de aprobar, la misma
        # que guardará cada corrida de esta versión. Sin ella no se aprueba.
        huella = None
        if decision == "aprobar":
            huella = _revisar_con_validacion(version["id"], "aprueba").get("huella")
            if not huella:
                raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE",
                               "El servicio validacion no dio la huella de la versión.")
        estado = datos.resuelve(version["id"], decision, comentario, contexto=g.contexto,
                                huella=huella)
        aviso = {"aprobar": _notificar_aprobacion, "rechazar": _notificar_rechazo,
                 "devolver": _notificar_devolucion}[decision]
        aviso(detalle["escenario"], version, *([] if decision == "aprobar" else [comentario]))
        respuesta = {"scenario_id": detalle["escenario"]["id"], "version_id": version["id"],
                     "version_number": version["version_number"], "status": estado,
                     "decision": decision}
        if huella:
            respuesta["approval_sha256"] = huella
        return responder(respuesta, "revision")

    @app.get("/api/v1/reviews/pending")
    @requiere_token(roles=ROLES_BANDEJA)
    def pendientes():
        filas = datos.pendientes()
        return responder({"total": len(filas), "pendientes": filas}, "bandeja")

    @app.get("/api/v1/versions/<version_id>/signature")
    @requiere_token(roles=ROLES_FIRMA)
    def firma(version_id):
        numero = entero_positivo(version_id, "version_id")
        guardada = datos.firma(numero)
        if guardada is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la versión.")
        actual = _dictamen(numero).get("huella")
        firmada = guardada["approval_sha256"] is not None
        return responder({
            "version_id": guardada["version_id"], "scenario_id": guardada["scenario_id"],
            "version_number": guardada["version_number"], "status": guardada["status"],
            "firmada": firmada, "huella": guardada["approval_sha256"],
            "revisor": guardada["revisor"], "reviewed_at": guardada["reviewed_at"],
            "huella_actual": actual, "integra": firmada and guardada["approval_sha256"] == actual,
            "corridas": guardada["corridas"]}, "firma")
