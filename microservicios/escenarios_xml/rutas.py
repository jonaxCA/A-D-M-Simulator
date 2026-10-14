from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

import xmlschema
from defusedxml import ElementTree as XMLSeguro
from defusedxml.common import DefusedXmlException
from flask import Response, current_app, g, request

from backend_web.audit import log_audit
from backend_web.db import get_conn
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import a_json, a_xml, de_xml, formato_solicitado, responder
from epidemia_comun.http import llamar
from epidemia_comun.seguridad import requiere_token

from . import lectura, mapeo

ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
RUTA_XSD = Path(__file__).resolve().parents[2] / "docs/contratos/escenarios-xml/escenario.xsd"
MAX_BYTES = 1024 * 1024
MAX_FALLAS = 50


class ErrorValidacion(ErrorAPI):
    """422 con la lista de fallas (ruta y mensaje); sale en el miembro `errores` del problema."""

    def __init__(self, detalle, fallas):
        super().__init__(422, "DATOS_INVALIDOS", detalle)
        self.fallas = [{"ruta": r or "/", "mensaje": m} for r, m in fallas[:MAX_FALLAS]]


@lru_cache(maxsize=1)
def esquema():
    return xmlschema.XMLSchema(str(RUTA_XSD))


def _detalle_fallas(titulo, fallas):
    primera = "; ".join("%s: %s" % (r or "/", m) for r, m in fallas[:3])
    return "%s (%d %s). %s" % (titulo, len(fallas), "falla" if len(fallas) == 1 else "fallas", primera)


def fallas_xsd(elemento):
    return [(e.path or "/", (e.reason or str(e.message)).strip())
            for e in esquema().iter_errors(elemento)]


def _respuesta_validacion(error):
    try:
        formato = formato_solicitado(request.args.get("format"), request.headers.get("Accept", ""))
    except ValueError:
        formato = "json"
    datos = {"type": "about:blank", "title": "Unprocessable Entity", "status": error.estado,
             "detail": error.detalle, "codigo": error.codigo, "instance": request.path,
             "errores": error.fallas}
    if formato == "json":
        cuerpo, tipo = a_json(datos), "application/problem+json"
    else:
        cuerpo, tipo = a_xml(datos, "problem"), "application/problem+xml"
    return Response(cuerpo, status=error.estado, content_type=tipo + "; charset=utf-8")


def _leer_xml_entrada():
    if request.mimetype not in ("application/xml", "text/xml"):
        raise ErrorAPI(415, "DATOS_INVALIDOS", "Usa Content-Type: application/xml.")
    if request.content_length is not None and request.content_length > MAX_BYTES:
        raise ErrorAPI(413, "DATOS_INVALIDOS", "La solicitud excede el tamaño permitido.")
    datos = request.get_data(cache=True)
    if len(datos) > MAX_BYTES:
        raise ErrorAPI(413, "DATOS_INVALIDOS", "La solicitud excede el tamaño permitido.")
    try:
        return XMLSeguro.fromstring(datos, forbid_dtd=True)
    except (ET.ParseError, DefusedXmlException, ValueError) as exc:
        raise ErrorAPI(400, "DATOS_INVALIDOS", "El cuerpo XML está mal formado.") from exc


# ------------------------------------------------------------------ llamadas aguas abajo

def _cuerpo_de(respuesta):
    try:
        tipo = respuesta.headers.get("Content-Type", "")
        datos = respuesta.json() if "json" in tipo else de_xml(respuesta.content)
        return datos if isinstance(datos, dict) else {}
    except Exception:
        return {}


def _error_de(servicio, respuesta):
    """Traduce un HTTP no exitoso de otro servicio a nuestro ErrorAPI."""
    estado = respuesta.status_code
    detalle = _cuerpo_de(respuesta).get("detail")
    texto = "El servicio %s respondió HTTP %d%s" % (servicio, estado, (": %s" % detalle) if detalle else ".")
    if estado >= 500:
        return ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", texto)
    if estado == 401:
        return ErrorAPI(401, "TOKEN_INVALIDO", texto)
    if estado == 403:
        return ErrorAPI(403, "PERMISO_INSUFICIENTE", texto)
    if estado == 409:
        return ErrorAPI(409, "CONFLICTO", texto)
    return ErrorAPI(422, "DATOS_INVALIDOS", texto)


def _con_parcial(error, parcial):
    return ErrorAPI(error.estado, error.codigo, "%s %s" % (error.detalle, parcial))


def _validar_con_validacion(doc, ids):
    r = llamar("validacion", "POST", "/api/v1/validate", formato="json",
               cuerpo=mapeo.cuerpo_validacion(doc, ids))
    cuerpo = _cuerpo_de(r)
    if not 200 <= r.status_code < 300 and r.status_code != 422:
        raise _error_de("validacion", r)
    errores = mapeo.fallas_de(cuerpo, "errores", "errors")
    if r.status_code == 422 and not errores:
        raise _error_de("validacion", r)
    if errores or cuerpo.get("valido") is False:
        raise ErrorValidacion(_detalle_fallas("El escenario no pasa la validación del motor",
                                              errores or [("", "validacion lo marcó como no válido")]),
                              errores)
    return [m for _, m in mapeo.fallas_de(cuerpo, "avisos", "warnings")]


def _crear_escenario(doc, ids):
    r = llamar("escenarios", "POST", "/api/v1/scenarios", formato="xml",
               cuerpo=mapeo.cuerpo_escenarios(doc, ids))
    if r.status_code not in (200, 201):
        raise _error_de("escenarios", r)
    scenario_id, version_id = mapeo.ids_de_respuesta(_cuerpo_de(r))
    if scenario_id is None:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE",
                       "El servicio escenarios no devolvió el id del escenario creado.")
    if version_id is None:  # la respuesta de alta no trae la versión: se pide el detalle
        detalle = llamar("escenarios", "GET", "/api/v1/scenarios/%d" % scenario_id, formato="json")
        if detalle.status_code == 200:
            version_id = mapeo.ids_de_respuesta(_cuerpo_de(detalle))[1]
        if version_id is None:
            raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE",
                           "Se creó el escenario %d pero no se pudo averiguar el id de su versión; "
                           "no se agregó ninguna intervención." % scenario_id)
    return scenario_id, version_id


def _crear_intervenciones(doc, ids, scenario_id, version_id):
    total = len(doc["intervenciones"])
    for hechas, intervencion in enumerate(doc["intervenciones"]):
        parcial = ("Estado parcial: el escenario %d (versión %d, borrador) ya existe con %d de %d "
                   "intervenciones; falló la de orden %d (%s) y las siguientes no se intentaron. "
                   "No se reintentó ni se borró nada: agrega las faltantes con POST "
                   "/api/v1/versions/%d/interventions o descarta el escenario."
                   % (scenario_id, version_id, hechas, total, intervencion["orden"],
                      intervencion["tipo"], version_id))
        try:
            r = llamar("intervenciones", "POST", "/api/v1/versions/%d/interventions" % version_id,
                       formato="json", cuerpo=mapeo.cuerpo_intervencion(intervencion, ids))
        except ErrorAPI as exc:
            raise _con_parcial(exc, parcial) from exc
        if r.status_code not in (200, 201):
            raise _con_parcial(_error_de("intervenciones", r), parcial)
    return total


# ------------------------------------------------------------------------------ rutas

def registrar(app):
    app.register_error_handler(ErrorValidacion, _respuesta_validacion)

    @app.get("/api/v1/schemas/scenario.xsd")
    def xsd():
        return Response(RUTA_XSD.read_bytes(), content_type="application/xml; charset=utf-8",
                        headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/api/v1/scenarios/<int:scenario_id>/export")
    @requiere_token(roles=ROLES)
    def exportar(scenario_id):
        if request.args.get("format") not in (None, "xml"):
            raise ErrorAPI(400, "DATOS_INVALIDOS",
                           "El export es un documento y solo existe en XML (application/xml).")
        version = request.args.get("version")
        if version is not None:
            if not version.isdigit() or int(version) < 1:
                raise ErrorAPI(422, "DATOS_INVALIDOS", "version debe ser un entero positivo.")
            version = int(version)
        datos = lectura.leer_escenario(scenario_id, version)
        if datos is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el escenario." if version is None
                           else "No existe esa versión del escenario.")
        try:
            cuerpo = mapeo.construir_documento(datos)
        except ValueError as exc:
            raise ErrorAPI(409, "CONFLICTO", "La versión no se puede exportar: %s" % exc) from exc
        fallas = fallas_xsd(XMLSeguro.fromstring(cuerpo))
        if fallas:
            current_app.logger.error("El export %d no valida contra el XSD: %s", scenario_id, fallas[:3])
            raise ErrorAPI(500, "ERROR_INTERNO", "Ocurrió un error interno.")
        numero = datos["version"]["version_number"]
        with get_conn() as conn:
            with conn.cursor() as cur:
                log_audit(g.contexto, "EXPORT", "scenarios", scenario_id,
                          data_after={"version_number": numero, "formato": "xml"}, cur=cur)
            conn.commit()
        return Response(cuerpo, content_type="application/xml; charset=utf-8", headers={
            "Content-Disposition": 'attachment; filename="escenario-%d-v%d.xml"' % (scenario_id, numero)})

    @app.post("/api/v1/scenarios/import")
    @requiere_token(roles=ROLES)
    def importar():
        raiz = _leer_xml_entrada()
        fallas = fallas_xsd(raiz)
        if fallas:
            raise ErrorValidacion(_detalle_fallas("El XML no cumple el esquema scenario.xsd", fallas), fallas)
        doc, fallas = mapeo.leer_documento(raiz)
        fallas += mapeo.reglas_documento(doc)
        if fallas:
            raise ErrorValidacion(_detalle_fallas("El XML tiene datos inconsistentes", fallas), fallas)
        ids, faltantes = lectura.resolver_ids(
            doc["enfermedad"], doc["region"], [i["tipo"] for i in doc["intervenciones"]],
            [i["region"] for i in doc["intervenciones"] if i["region"]])
        if faltantes:
            raise ErrorValidacion(_detalle_fallas("El XML usa códigos que no existen", faltantes), faltantes)

        avisos = mapeo.avisos_de_importacion(doc) + _validar_con_validacion(doc, ids)
        scenario_id, version_id = _crear_escenario(doc, ids)
        creadas = _crear_intervenciones(doc, ids, scenario_id, version_id)
        return responder({"scenario_id": scenario_id, "version_id": version_id, "version_number": 1,
                          "intervenciones_creadas": creadas, "avisos": avisos},
                         "importacion", estado=201)
