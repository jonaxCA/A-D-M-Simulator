import json
import re
from datetime import date, datetime
from decimal import Decimal
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as XMLSeguro
from defusedxml.common import DefusedXmlException


def _normalizar(valor):
    if isinstance(valor, dict):
        return {str(k): _normalizar(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_normalizar(x) for x in valor]
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


SINGULARES = {"regiones": "region", "enfermedades": "enfermedad",
              "municipios": "municipio", "intervenciones": "intervencion",
              "escenarios": "escenario", "corridas": "corrida",
              "tipos": "tipo", "zonas": "zona", "puntos": "punto",
              "grupos": "grupo", "sexos": "sexo", "fechas": "fecha",
              "tendencia": "punto", "serie": "punto"}


# Un nombre de etiqueta XML no puede iniciar con numero ni contener "+".
# Las claves que no cumplen se escriben como <entrada clave="0-19">.
_NOMBRE_XML = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


def _elemento(padre, nombre, valor):
    nombre = str(nombre)
    if _NOMBRE_XML.fullmatch(nombre) and not nombre.lower().startswith("xml"):
        nodo = ET.SubElement(padre, nombre)
    else:
        nodo = ET.SubElement(padre, "entrada", {"clave": nombre})
    if isinstance(valor, dict):
        for clave, dato in valor.items():
            _elemento(nodo, clave, dato)
    elif isinstance(valor, (list, tuple)):
        singular = SINGULARES.get(str(nombre), "item")
        for dato in valor:
            _elemento(nodo, singular, dato)
    elif valor is None:
        nodo.set("nil", "true")
    elif isinstance(valor, bool):
        nodo.set("tipo", "booleano")
        nodo.text = "true" if valor else "false"
    elif isinstance(valor, (int, float)):
        nodo.set("tipo", "numero")
        nodo.text = str(valor)
    else:
        nodo.text = str(valor)
    return nodo


def a_xml(datos, raiz):
    """Construye XML escapado. Nunca concatena etiquetas con datos del usuario."""
    normal = _normalizar(datos)
    nodo = ET.Element(raiz)
    if isinstance(normal, dict):
        for clave, dato in normal.items():
            _elemento(nodo, clave, dato)
    elif isinstance(normal, list):
        for dato in normal:
            _elemento(nodo, "item", dato)
    else:
        nodo.text = "" if normal is None else str(normal)
    return ET.tostring(nodo, encoding="utf-8", xml_declaration=True)


def a_json(datos):
    return json.dumps(_normalizar(datos), ensure_ascii=False, allow_nan=False).encode("utf-8")


def de_xml(datos):
    nodo = XMLSeguro.fromstring(datos)
    def leer(actual):
        if len(actual) == 0:
            if actual.get("nil") == "true":
                return None
            texto = actual.text or ""
            if actual.get("tipo") == "booleano":
                if texto not in ("true", "false"):
                    raise ValueError("Valor booleano XML inválido")
                return texto == "true"
            if actual.get("tipo") == "numero":
                try:
                    valor = float(texto)
                    if valor.is_integer():
                        return int(valor)
                    return valor
                except (ValueError, OverflowError):
                    raise ValueError("Número XML inválido")
            return texto
        salida = {}
        for hijo in actual:
            valor = leer(hijo)
            clave = hijo.get("clave") if hijo.tag == "entrada" and "clave" in hijo.attrib else hijo.tag
            if clave in salida:
                if not isinstance(salida[clave], list):
                    salida[clave] = [salida[clave]]
                salida[clave].append(valor)
            else:
                salida[clave] = valor
        return salida
    return leer(nodo)


def formato_solicitado(formato=None, accept=""):
    if formato is not None:
        if formato not in ("json", "xml"):
            raise ValueError("El formato debe ser json o xml.")
        return formato
    if "application/json" in (accept or "").lower():
        return "json"
    return "xml"


def responder(datos, raiz="respuesta", estado=200):
    from flask import Response, request
    from .errores import ErrorAPI
    try:
        formato = formato_solicitado(request.args.get("format"), request.headers.get("Accept", ""))
    except ValueError as exc:
        raise ErrorAPI(400, "DATOS_INVALIDOS", str(exc)) from exc
    cuerpo, tipo = (a_json(datos), "application/json") if formato == "json" else (a_xml(datos, raiz), "application/xml")
    return Response(cuerpo, status=estado, content_type=tipo + "; charset=utf-8")


def leer_cuerpo(max_bytes=1024 * 1024):
    from flask import request
    from .errores import ErrorAPI
    if request.content_length is not None and request.content_length > max_bytes:
        raise ErrorAPI(413, "DATOS_INVALIDOS", "La solicitud excede el tamaño permitido.")
    datos = request.get_data(cache=True)
    if len(datos) > max_bytes:
        raise ErrorAPI(413, "DATOS_INVALIDOS", "La solicitud excede el tamaño permitido.")
    try:
        if request.mimetype == "application/json":
            return json.loads(datos)
        if request.mimetype in ("application/xml", "text/xml"):
            return de_xml(datos)
    except (ValueError, ET.ParseError, DefusedXmlException) as exc:
        raise ErrorAPI(400, "DATOS_INVALIDOS", "El cuerpo JSON o XML es inválido.") from exc
    raise ErrorAPI(415, "DATOS_INVALIDOS", "Usa Content-Type: application/json o application/xml.")
