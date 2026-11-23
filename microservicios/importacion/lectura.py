# Lectura y revisión de una serie observada (D53, RF-B08): CSV, JSON o XML, siempre con solo dos
# campos por punto, periodo_inicio y valor. Nada por persona entra al sistema (RNF-I05, D50).
import csv
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

import xmlschema
from defusedxml import ElementTree as XMLSeguro
from defusedxml.common import DefusedXmlException

from epidemia_comun.errores import ErrorAPI

XSD = Path(__file__).resolve().parents[2] / "docs/contratos/importacion/serie_observada.xsd"
TIPOS = {"text/csv": "csv", "application/json": "json", "application/xml": "xml", "text/xml": "xml"}
CAMPOS = ["periodo_inicio", "valor"]
METRICAS = ("casos_confirmados", "hospitalizaciones", "defunciones")
PERIODOS = {"semana": 7, "dia": 1}
MIN_PUNTOS, MAX_PUNTOS = 4, 5000
MAX_BYTES = 2 * 1024 * 1024
MAX_FALLAS = 50
SOLO_AGREGADOS = "Solo se importan series agregadas: cada punto lleva periodo_inicio y valor, y nada más (RNF-I05)."
_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CODIGO = re.compile(r"^[A-Z0-9_]{3,60}$")
_ENTERO = re.compile(r"^\d+$")


@lru_cache(maxsize=1)
def esquema():
    return xmlschema.XMLSchema(str(XSD))


def _csv(texto):
    filas, fallas, cabecera = [], [], None
    for numero, linea in enumerate(texto.splitlines(), 1):
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        celdas = [c.strip() for c in next(csv.reader([linea]))]
        if cabecera is None:
            cabecera = celdas
            if cabecera != CAMPOS:
                return [], [SOLO_AGREGADOS if set(cabecera) - set(CAMPOS) else
                            "La primera línea sin # debe ser el encabezado periodo_inicio,valor."]
        elif len(celdas) != 2:
            fallas.append("Línea %d: lleva %d columnas y deben ser 2." % (numero, len(celdas)))
        else:
            filas.append(("Línea %d" % numero, celdas[0], celdas[1]))
    return filas, fallas


def _json(texto):
    datos = json.loads(texto)
    if not isinstance(datos, dict) or set(datos) != {"puntos"} or not isinstance(datos["puntos"], list):
        return [], ['El JSON debe ser {"puntos": [{"periodo_inicio": ..., "valor": ...}, ...]}.']
    filas = []
    for i, punto in enumerate(datos["puntos"], 1):
        if not isinstance(punto, dict) or set(punto) != set(CAMPOS):
            return [], [SOLO_AGREGADOS if isinstance(punto, dict) and set(punto) - set(CAMPOS) else
                        "Punto %d: debe traer periodo_inicio y valor." % i]
        filas.append(("Punto %d" % i, punto["periodo_inicio"], punto["valor"]))
    return filas, []


def _xml(datos):
    raiz = XMLSeguro.fromstring(datos, forbid_dtd=True)
    fallas = ["%s: %s" % (e.path or "/", (e.reason or str(e.message)).strip())
              for e in esquema().iter_errors(raiz)]
    if fallas:
        return [], fallas
    return [("Punto %d" % i, p.findtext("periodo_inicio"), p.findtext("valor"))
            for i, p in enumerate(raiz.iter("punto"), 1)], []


# (filas, fallas): cada fila es (dónde, periodo_inicio, valor) tal como venía. Un archivo que no
# se puede leer es 400, como un cuerpo mal formado en leer_cuerpo().
def lee(datos, mimetype):
    formato = TIPOS[mimetype]
    try:
        if formato == "xml":
            return _xml(datos)
        texto = datos.decode("utf-8-sig")
        return _csv(texto) if formato == "csv" else _json(texto)
    except UnicodeDecodeError as exc:
        raise ErrorAPI(400, "DATOS_INVALIDOS", "El archivo debe venir en UTF-8.") from exc
    except (ValueError, ET.ParseError, DefusedXmlException, csv.Error) as exc:
        raise ErrorAPI(400, "DATOS_INVALIDOS", "El archivo %s está mal formado." % formato.upper()) from exc


def _valor(crudo):
    if isinstance(crudo, bool):
        return None
    if isinstance(crudo, int):
        return crudo if crudo >= 0 else None
    if isinstance(crudo, str) and _ENTERO.match(crudo.strip()):
        return int(crudo)
    return None


# (puntos ordenados, fallas, resumen). Un punto es (date, int).
def revisa(filas, periodo):
    fallas, puntos, vistos = [], [], set()
    for donde, inicio, crudo in filas:
        dia = None
        if isinstance(inicio, str) and _FECHA.match(inicio.strip()):
            try:
                dia = date.fromisoformat(inicio.strip())
            except ValueError:
                pass
        valor = _valor(crudo)
        if dia is None:
            fallas.append("%s: periodo_inicio debe ser una fecha AAAA-MM-DD." % donde)
        if valor is None:
            fallas.append("%s: valor debe ser un entero no negativo." % donde)
        if dia is None or valor is None:
            continue
        if dia in vistos:
            fallas.append("%s: el periodo %s está repetido." % (donde, dia))
            continue
        vistos.add(dia)
        puntos.append((dia, valor))
    # Con un punto malo, los huecos y la cuenta saldrían falsos: se revisan después.
    if fallas:
        return [], fallas[:MAX_FALLAS], None
    if not MIN_PUNTOS <= len(puntos) <= MAX_PUNTOS:
        fallas.append("La serie debe tener de %d a %d puntos; trae %d." % (MIN_PUNTOS, MAX_PUNTOS, len(puntos)))
    puntos.sort()
    paso = PERIODOS[periodo]
    for (antes, _), (dia, _) in zip(puntos, puntos[1:]):
        dias = (dia - antes).days
        if dias % paso:
            fallas.append("El periodo %s no está a %d días de los demás: los periodos de una serie por %s "
                          "empiezan el mismo día de la semana." % (dia, paso, periodo)
                          if paso == 7 else "El periodo %s no cae en el paso de la serie." % dia)
        elif dias > paso:
            fallas.append("Faltan %d periodos entre %s y %s: un periodo sin casos se escribe con 0."
                          % (dias // paso - 1, antes, dia))
    if fallas:
        return [], fallas[:MAX_FALLAS], None
    valores = [v for _, v in puntos]
    return puntos, [], {"puntos": len(puntos), "inicio": puntos[0][0], "fin": puntos[-1][0],
                        "total": sum(valores), "maximo": max(valores),
                        "periodos_en_cero": valores.count(0)}


def _texto(args, campo, maximo, obligatorio=True):
    valor = (args.get(campo) or "").strip()
    if not valor:
        return None, ["Falta %s." % campo] if obligatorio else []
    if len(valor) > maximo:
        return None, ["%s tiene a lo más %d caracteres." % (campo, maximo)]
    return valor, []


# (metadatos, fallas) de los parámetros de la consulta.
def revisa_metadatos(args, hoy):
    meta, fallas = {}, []
    for campo, maximo, obligatorio in (("code", 60, True), ("name", 200, True), ("disease", 40, True),
                                       ("region", 10, True), ("source", 500, True),
                                       ("license", 200, True), ("url", 500, False)):
        meta[campo], error = _texto(args, campo, maximo, obligatorio)
        fallas += error
    if meta["code"] and not _CODIGO.match(meta["code"]):
        fallas.append("code va en mayúsculas, dígitos y guion bajo (3 a 60).")
    if meta["url"] and not meta["url"].startswith(("http://", "https://")):
        fallas.append("url debe empezar con http:// o https://.")
    meta["metric"] = args.get("metric")
    if meta["metric"] not in METRICAS:
        fallas.append("metric debe ser %s." % ", ".join(METRICAS))
        meta["metric"] = None
    meta["period"] = args.get("period")
    if meta["period"] not in PERIODOS:
        fallas.append("period debe ser semana o dia.")
        meta["period"] = None
    corte = (args.get("cutoff") or "").strip()
    meta["cutoff"] = None
    if _FECHA.match(corte):
        try:
            meta["cutoff"] = date.fromisoformat(corte)
        except ValueError:
            pass
    if meta["cutoff"] is None:
        fallas.append("cutoff, la fecha del corte de la fuente, debe ser AAAA-MM-DD.")
    elif meta["cutoff"] > hoy:
        fallas.append("cutoff no puede ser una fecha futura.")
    return meta, fallas
