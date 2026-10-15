import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epidemia_comun.ajustes import cargar_ajustes
from epidemia_comun.formatos import a_json, a_xml, de_xml, formato_solicitado


def test_config_falla_sin_secreto():
    try:
        cargar_ajustes("regiones", {"REDIS_URL": "redis://redis:6379"})
        assert False, "No rechazó la falta de JWT_SECRET_KEY"
    except RuntimeError:
        pass


def test_config_falla_sin_redis():
    try:
        cargar_ajustes("regiones", {"JWT_SECRET_KEY": "test-secreto-muy-largo"})
        assert False, "No rechazó la falta de REDIS_URL"
    except RuntimeError:
        pass


def test_config_acepta_ajustes():
    datos = cargar_ajustes("regiones", {"JWT_SECRET_KEY": "clave-segura", "REDIS_URL": "redis://redis:6379"})
    assert datos["JWT_AUDIENCE"] == "epidemia-api"


def test_xml_escapa_y_conserva_numeros():
    salida = a_xml({"nombre": "A & B <C>", "poblacion": 15, "activo": True}, "region")
    raiz = ET.fromstring(salida)
    assert raiz.findtext("nombre") == "A & B <C>"
    assert raiz.findtext("poblacion") == "15"
    assert raiz.findtext("activo") == "true"


def test_json_normaliza_fechas_y_decimales():
    salida = a_json({"fecha": datetime(2026, 10, 12, tzinfo=timezone.utc), "costo": Decimal("2.50")})
    assert b'"costo": 2.5' in salida
    assert b"2026-10-12" in salida


def test_lectura_xml_segura():
    assert de_xml(b"<region><id>4</id><nombre>Monterrey</nombre></region>") == {"id": "4", "nombre": "Monterrey"}


def test_defusedxml_rechaza_entidades():
    from defusedxml.common import EntitiesForbidden
    xml = b'<!DOCTYPE foo [<!ENTITY entidad "texto">]><foo>&entidad;</foo>'
    try:
        de_xml(xml)
        assert False
    except EntitiesForbidden:
        pass


def test_formatos():
    assert formato_solicitado() == "xml"
    assert formato_solicitado(accept="application/json") == "json"
    assert formato_solicitado("xml", "application/json") == "xml"
    try:
        formato_solicitado("csv")
        assert False
    except ValueError:
        pass


def test_plural_regiones_es_singular_region():
    xml = a_xml({"regiones": [{"id": 1}, {"id": 2}]}, "respuesta")
    raiz = ET.fromstring(xml)
    assert len(raiz.findall("regiones/region")) == 2


def test_plantilla_no_sobrescribe(tmp_path):
    import importlib.util
    ruta = Path(__file__).resolve().parents[1] / "scripts" / "nuevo_servicio.py"
    spec = importlib.util.spec_from_file_location("nuevo_servicio", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    carpeta = modulo.crear_archivos(tmp_path, "ejemplo", 5299)
    assert (carpeta / "app.py").is_file()
    assert (carpeta / "Dockerfile").is_file()
    import pytest
    with pytest.raises(FileExistsError):
        modulo.crear_archivos(tmp_path, "ejemplo", 5299)
