from pathlib import Path
import sys
from xml.etree import ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from epidemia_comun.formatos import a_xml, de_xml


@pytest.mark.parametrize("clave", ["0-19", "20-39", "40-59", "60-79", "80+", "no válido", "a:b", "", "xmlClave"])
def test_clave_no_admitida_se_escribe_como_entrada(clave):
    contenido = {"bandas": {clave: 120}}
    xml = a_xml(contenido, "poblacion")
    raiz = ET.fromstring(xml)
    elemento = raiz.find(".//entrada")
    assert elemento is not None
    assert elemento.get("clave") == clave
    assert elemento.text == "120"
    assert de_xml(xml) == contenido


def test_claves_normales_siguen_siendo_etiquetas():
    xml = a_xml({"region_id": 39, "activo": True, "nombre": "Monterrey"}, "region")
    raiz = ET.fromstring(xml)
    assert raiz.findtext("region_id") == "39"
    assert raiz.findtext("activo") == "true"
    assert de_xml(xml) == {"region_id": 39, "activo": True, "nombre": "Monterrey"}


def test_grupos_de_edad_son_xml_valido_y_recuperable():
    datos = {"grupos": {"0-19": 100, "20-39": 200, "40-59": 300, "60-79": 80, "80+": 10},
             "edad_no_especificada": 7}
    xml = a_xml(datos, "grupos_edad")
    raiz = ET.fromstring(xml)
    assert raiz.find("grupos/entrada[@clave='0-19']").text == "100"
    assert raiz.find("grupos/entrada[@clave='80+']").text == "10"
    assert de_xml(xml) == datos


def test_letalidad_por_edad_conserva_decimales():
    datos = {"letalidad_por_edad": {"0-19": 0.0001, "80+": 0.08}}
    assert de_xml(a_xml(datos, "parametros")) == datos


def test_clave_se_escapa_en_el_atributo():
    datos = {"0-19 & < > \"": "A & B < C"}
    xml = a_xml(datos, "resultado")
    assert de_xml(xml) == datos
