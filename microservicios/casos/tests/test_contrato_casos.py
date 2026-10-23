import json
from pathlib import Path

import pytest
import xmlschema

from epidemia_comun.formatos import a_xml

RAIZ = Path(__file__).resolve().parents[3]
CARPETA = RAIZ / "docs/contratos/casos"
XSD = xmlschema.XMLSchema(str(CARPETA / "caso.xsd"))
CONTRATO = json.loads((CARPETA / "openapi.json").read_text(encoding="utf-8"))
UUID_A = "6f1f4f0e-3c6b-4f4c-9d9e-1a2b3c4d5e6f"


def ejemplos_de_respuesta():
    for ruta, metodos in CONTRATO["paths"].items():
        for item in metodos.values():
            for codigo, resp in item["responses"].items():
                for tipo, cont in resp.get("content", {}).items():
                    yield item["operationId"], codigo, tipo, cont


def test_openapi_servido_es_el_del_repo(crear_cliente):
    r = crear_cliente("casos").get("/openapi.json")
    assert r.status_code == 200 and r.data == (CARPETA / "openapi.json").read_bytes()


def test_cada_ejemplo_xml_es_el_json_generado_con_la_biblioteca():
    for archivo in sorted((CARPETA / "ejemplos").glob("*.json")):
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        xml = archivo.with_suffix(".xml").read_text(encoding="utf-8")
        raiz = xml.split("?>", 1)[1].strip().split(">", 1)[0].strip("<").split(" ")[0].strip("/")
        assert xml == (a_xml(datos, raiz) + b"\n").decode("utf-8"), archivo.name


def test_ejemplos_incrustados_estan_en_los_archivos():
    carpeta = CARPETA / "ejemplos"
    for op, codigo, tipo, cont in ejemplos_de_respuesta():
        if "example" not in cont:
            continue
        if codigo == "200" and op == "crear_caso":
            nombre = "crear_caso_duplicado"
        elif codigo in ("200", "201"):
            nombre = op
        else:
            nombre = "%s_%s" % (op, codigo)
        if tipo.endswith("json"):
            assert cont["example"] == json.loads((carpeta / (nombre + ".json")).read_text(encoding="utf-8"))
        else:
            assert cont["example"] == (carpeta / (nombre + ".xml")).read_text(encoding="utf-8")
    cuerpo = CONTRATO["paths"]["/api/v1/cases"]["post"]["requestBody"]["content"]
    assert cuerpo["application/json"]["example"] == json.loads(
        (carpeta / "crear_caso_solicitud.json").read_text(encoding="utf-8"))
    assert cuerpo["application/xml"]["example"] == (carpeta / "crear_caso_solicitud.xml").read_text(encoding="utf-8")


@pytest.mark.parametrize("nombre", ["crear_caso_solicitud", "crear_caso", "crear_caso_duplicado",
                                    "consultar_caso", "listar_casos"])
def test_ejemplo_xml_valida_contra_el_xsd(nombre):
    XSD.validate(str(CARPETA / "ejemplos" / (nombre + ".xml")))


def test_documentacion_del_contrato():
    ruta = CONTRATO["paths"]["/api/v1/cases"]
    assert CONTRATO["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"
    nombres = {p["name"] for p in ruta["get"]["parameters"]}
    assert {"disease_id", "region_id", "status", "sex", "from", "to", "page", "per_page", "format"} <= nombres
    assert {"200", "201", "401", "403", "422", "503"} <= set(ruta["post"]["responses"])
    assert "application/problem+json" in ruta["post"]["responses"]["422"]["content"]


def test_xsd_acepta_xml_minimo_sin_atributos_y_con_nulos():
    XSD.validate("<caso><disease_id>1</disease_id><region_id>10</region_id>"
                 "<report_date>2026-10-01</report_date></caso>")
    XSD.validate('<caso><disease_id>1</disease_id><region_id>10</region_id>'
                 '<report_date>2026-10-01</report_date><age nil="true"/><sex/></caso>')


@pytest.mark.parametrize("cambio", [
    "<sex>X</sex>", "<test_result>quizas</test_result>", "<severity>mortal</severity>",
    "<age>500</age>", "<latitude>95</latitude>", "<onset_date>ayer</onset_date>",
    "<local_uuid>123</local_uuid>", "<desconocido>1</desconocido>",
])
def test_xsd_rechaza_valores_fuera_de_dominio(cambio):
    xml = ("<caso><disease_id>1</disease_id><region_id>10</region_id>"
           "<report_date>2026-10-01</report_date>%s</caso>" % cambio)
    assert not XSD.is_valid(xml)


@pytest.mark.parametrize("falta", ["disease_id", "region_id", "report_date"])
def test_xsd_exige_los_obligatorios(falta):
    campos = {"disease_id": "1", "region_id": "10", "report_date": "2026-10-01"}
    del campos[falta]
    xml = "<caso>%s</caso>" % "".join("<%s>%s</%s>" % (k, v, k) for k, v in campos.items())
    assert not XSD.is_valid(xml)


def test_la_respuesta_real_valida_contra_el_xsd(crear_cliente, token, monkeypatch):
    # El XML que arma el servicio (no solo el ejemplo) cumple el XSD.
    from microservicios.casos.tests.test_casos import BaseFalsa, Conexion, ENFERMEDADES, MUNICIPIOS
    from contextlib import contextmanager
    from backend_web import queries
    from microservicios.casos import rutas
    base = BaseFalsa()

    @contextmanager
    def get_conn():
        yield Conexion(base)
    monkeypatch.setattr(rutas, "get_conn", get_conn)
    monkeypatch.setattr(rutas, "log_audit", lambda *a, **k: None)
    monkeypatch.setattr(queries, "get_enfermedades_para_captura", lambda: ENFERMEDADES)
    monkeypatch.setattr(queries, "get_municipios_catalogo", lambda: MUNICIPIOS)
    c = crear_cliente("casos")
    h = token(roles=("CAPTURISTA",))
    r = c.post("/api/v1/cases", json={"local_uuid": UUID_A, "device_id": 3, "disease_id": 1,
                                      "region_id": 10, "report_date": "2026-10-01", "sex": "F",
                                      "age": 30, "latitude": 25.68, "longitude": -100.3}, headers=h)
    assert r.status_code == 201
    XSD.validate(r.data.decode("utf-8"))
    r = c.get("/api/v1/cases", headers=h)
    XSD.validate(r.data.decode("utf-8"))
