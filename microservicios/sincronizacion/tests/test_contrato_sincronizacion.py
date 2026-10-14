import json
from pathlib import Path

import pytest
import xmlschema

from epidemia_comun.formatos import a_xml

RAIZ = Path(__file__).resolve().parents[3]
CARPETA = RAIZ / "docs/contratos/sincronizacion"
XSD = xmlschema.XMLSchema(str(CARPETA / "lote.xsd"))
CONTRATO = json.loads((CARPETA / "openapi.json").read_text(encoding="utf-8"))
LOTE = "0b6f5a53-1d1f-4f52-8a0a-5d0a4a0e9c11"
U1 = "11111111-1111-4111-8111-111111111111"


def test_openapi_servido_es_el_del_repo(crear_cliente):
    r = crear_cliente("sincronizacion").get("/openapi.json")
    assert r.status_code == 200 and r.data == (CARPETA / "openapi.json").read_bytes()


def test_cada_ejemplo_xml_es_el_json_generado_con_la_biblioteca():
    for archivo in sorted((CARPETA / "ejemplos").glob("*.json")):
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        xml = archivo.with_suffix(".xml").read_text(encoding="utf-8")
        raiz = xml.split("?>", 1)[1].strip().split(">", 1)[0].strip("<").split(" ")[0].strip("/")
        assert xml == (a_xml(datos, raiz) + b"\n").decode("utf-8"), archivo.name


def test_ejemplos_incrustados_estan_en_los_archivos():
    carpeta = CARPETA / "ejemplos"
    cuantos = 0
    for ruta, metodos in CONTRATO["paths"].items():
        for item in metodos.values():
            op = item["operationId"]
            for codigo, resp in item["responses"].items():
                for tipo, cont in resp.get("content", {}).items():
                    nombre = op if codigo == "200" else "%s_%s" % (op, codigo)
                    ext = "json" if tipo.endswith("json") else "xml"
                    leido = (carpeta / (nombre + "." + ext)).read_text(encoding="utf-8")
                    assert cont["example"] == (json.loads(leido) if ext == "json" else leido)
                    cuantos += 1
            if "requestBody" in item:
                cuerpo = item["requestBody"]["content"]
                assert cuerpo["application/json"]["example"] == json.loads(
                    (carpeta / (op + "_solicitud.json")).read_text(encoding="utf-8"))
                assert cuerpo["application/xml"]["example"] == (
                    carpeta / (op + "_solicitud.xml")).read_text(encoding="utf-8")
    assert cuantos > 10


@pytest.mark.parametrize("nombre", ["enviar_lote_solicitud", "enviar_lote", "enviar_lote_repetido",
                                    "consultar_lote"])
def test_ejemplo_xml_valida_contra_el_xsd(nombre):
    XSD.validate(str(CARPETA / "ejemplos" / (nombre + ".xml")))


def test_documentacion_del_contrato():
    post = CONTRATO["paths"]["/api/v1/sync/cases"]["post"]
    assert {"200", "401", "403", "409", "422", "503"} <= set(post["responses"])
    assert "CAPTURISTA" in post["description"] and "sync:lote" in CONTRATO["info"]["description"]
    assert CONTRATO["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"
    assert "/api/v1/sync/batches/{batch_id}" in CONTRATO["paths"]


def _lote(extra="", cuerpo_caso="<local_uuid>%s</local_uuid><disease_id>1</disease_id>"
          "<region_id>10</region_id><report_date>2026-10-01</report_date>" % U1):
    return "<lote><batch_id>%s</batch_id>%s<cases><item>%s</item></cases></lote>" % (LOTE, extra, cuerpo_caso)


def test_xsd_acepta_lote_minimo_sin_atributos():
    XSD.validate(_lote())
    XSD.validate(_lote("<device_id>3</device_id>"))


@pytest.mark.parametrize("xml", [
    "<lote><cases><item><local_uuid>%s</local_uuid><disease_id>1</disease_id><region_id>1</region_id>"
    "<report_date>2026-10-01</report_date></item></cases></lote>" % U1,           # sin batch_id
    "<lote><batch_id>%s</batch_id><cases/></lote>" % LOTE,                          # sin casos
    "<lote><batch_id>x</batch_id><cases><item><local_uuid>%s</local_uuid><disease_id>1</disease_id>"
    "<region_id>1</region_id><report_date>2026-10-01</report_date></item></cases></lote>" % U1,
])
def test_xsd_rechaza_lotes_incompletos(xml):
    assert not XSD.is_valid(xml)


@pytest.mark.parametrize("cuerpo", [
    "<disease_id>1</disease_id><region_id>10</region_id><report_date>2026-10-01</report_date>",   # sin local_uuid
    "<local_uuid>%s</local_uuid><disease_id>1</disease_id><region_id>10</region_id>"
    "<report_date>2026-10-01</report_date><sex>X</sex>" % U1,
    "<local_uuid>%s</local_uuid><disease_id>1</disease_id><region_id>10</region_id>"
    "<report_date>01/10/2026</report_date>" % U1,
])
def test_xsd_rechaza_casos_invalidos(cuerpo):
    assert not XSD.is_valid(_lote(cuerpo_caso=cuerpo))


def test_xsd_resultado_rechaza_resultado_desconocido():
    xml = open(str(CARPETA / "ejemplos/enviar_lote.xml"), encoding="utf-8").read()
    assert XSD.is_valid(xml)
    assert not XSD.is_valid(xml.replace("<resultado>creado", "<resultado>quizas"))


def test_la_respuesta_real_valida_contra_el_xsd(crear_cliente, token, monkeypatch):
    from microservicios.sincronizacion import rutas
    from microservicios.sincronizacion.tests.test_sincronizacion import CasosFalso
    monkeypatch.setattr(rutas, "llamar", CasosFalso())
    monkeypatch.setattr(rutas, "log_audit", lambda *a, **k: None)
    c = crear_cliente("sincronizacion")
    h = token(roles=("CAPTURISTA",))
    r = c.post("/api/v1/sync/cases", data=_lote(extra="<device_id>3</device_id>"),
               headers=dict(h, **{"Content-Type": "application/xml"}))
    assert r.status_code == 200
    XSD.validate(r.data.decode("utf-8"))
    r = c.get("/api/v1/sync/batches/" + LOTE, headers=h)
    XSD.validate(r.data.decode("utf-8"))
