"""Llamadas entre servicios en XML: escenarios-xml le manda el escenario en XML a escenarios, y
estado-servicios lee en XML el /health de los 26."""
import re

from .conftest import INTERVENCIONES


def test_importar_crea_el_escenario_en_escenarios(api, analista, crea_escenario):
    escenario, _, _ = crea_escenario("Exportado", INTERVENCIONES)
    exportado = api("escenarios-xml", "GET", "/api/v1/scenarios/%d/export" % escenario, analista["access"], formato=None)
    assert exportado.status_code == 200 and exportado.headers["Content-Type"].startswith("application/xml")
    # El nombre es único por autor: la copia lleva otro.
    copia = re.sub(r"<nombre>([^<]*)</nombre>", r"<nombre>\1 (importado)</nombre>", exportado.text, count=1)
    r = api("escenarios-xml", "POST", "/api/v1/scenarios/import", analista["access"], data=copia.encode("utf-8"),
            headers={"Content-Type": "application/xml"})
    assert r.status_code == 201, r.text
    assert r.json()["intervenciones_creadas"] == len(INTERVENCIONES)
    importado = api("escenarios", "GET", "/api/v1/scenarios/%d" % r.json()["scenario_id"], analista["access"]).json()
    assert importado["name"].endswith("(importado)")


def test_importar_un_xml_que_no_cumple_el_xsd_es_422(api, analista):
    r = api("escenarios-xml", "POST", "/api/v1/scenarios/import", analista["access"],
            data=b"<escenario esquema='1.0'><campo_que_no_existe/></escenario>",
            headers={"Content-Type": "application/xml"})
    assert r.status_code == 422 and r.json()["errores"]


def test_estado_servicios_lee_la_salud_de_los_26(api):
    datos = api("estado-servicios", "GET", "/api/v1/services/health").json()
    assert datos["resumen"] == {"ok": 26, "degradado": 0, "caido": 0}
    assert all(s["version"] for s in datos["servicios"])
