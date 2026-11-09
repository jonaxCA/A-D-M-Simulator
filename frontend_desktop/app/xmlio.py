import re
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as XMLSeguro

# Mismo mapa que microservicios/comun/epidemia_comun/formatos.py: una etiqueta plural
# siempre es lista, aunque traiga un solo elemento o ninguno.
SINGULARES = {"regiones": "region", "enfermedades": "enfermedad",
              "municipios": "municipio", "intervenciones": "intervencion",
              "escenarios": "escenario", "corridas": "corrida",
              "tipos": "tipo", "zonas": "zona", "puntos": "punto",
              "grupos": "grupo", "sexos": "sexo", "fechas": "fecha",
              "tendencia": "punto", "serie": "punto",
              "filas": "fila", "frontera": "corrida", "dominado_por": "corrida",
              "desglose_costo": "intervencion", "trazabilidad_costos": "costo",
              "avisos": "aviso", "notificaciones": "notificacion", "dispositivos": "dispositivo",
              "evidencias": "evidencia", "lotes": "lote",
              "desglose_por_grupo": "grupo_edad", "trazabilidad": "parametro",
              "simplificaciones": "simplificacion", "servicios": "servicio",
              "causas": "causa", "sondeos": "sondeo"}

# Listas que el servidor escribe con <item>; vacías llegan como <errores />.
LISTAS_DE_ITEM = {"errores", "roles", "versiones", "pendientes", "required", "enum", "grupos_edad"}

_NOMBRE_XML = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


def _valor(nodo):
    if nodo.get("nil") == "true":
        return None
    texto = nodo.text or ""
    if nodo.get("tipo") == "booleano":
        return texto == "true"
    if nodo.get("tipo") == "numero":
        numero = float(texto)
        return int(numero) if numero.is_integer() else numero
    return texto


def _es_lista(nodo, hijos):
    return nodo.tag in SINGULARES or nodo.tag in LISTAS_DE_ITEM or (hijos and all(h.tag == "item" for h in hijos))


def _leer(nodo, es_raiz=False):
    hijos = list(nodo)
    if not es_raiz and _es_lista(nodo, hijos):
        return [_leer(h) for h in hijos]
    if not hijos:
        return {} if es_raiz else _valor(nodo)
    salida = {}
    for hijo in hijos:
        clave = hijo.get("clave", hijo.tag) if hijo.tag == "entrada" else hijo.tag
        valor = _leer(hijo)
        if clave in salida:
            if not isinstance(salida[clave], list):
                salida[clave] = [salida[clave]]
            salida[clave].append(valor)
        else:
            salida[clave] = valor
    return salida


def raiz(datos):
    return XMLSeguro.fromstring(datos).tag


def leer(datos):
    return _leer(XMLSeguro.fromstring(datos), es_raiz=True)


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
        singular = SINGULARES.get(nombre, "item")
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


def escribir(datos, raiz_xml):
    nodo = ET.Element(raiz_xml)
    for clave, dato in datos.items():
        _elemento(nodo, clave, dato)
    return ET.tostring(nodo, encoding="utf-8", xml_declaration=True)
