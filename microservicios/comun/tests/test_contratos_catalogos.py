import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from epidemia_comun.formatos import a_xml

RAIZ = Path(__file__).resolve().parents[3]
SERVICIOS = ["enfermedades", "parametros", "regiones", "poblacion"]
# a_xml usa "0-19" como etiqueta; este ejemplo muestra la forma válida (ver MANUAL_TECNICO §12).
NO_GENERABLES = {"consultar_grupos_de_edad"}


def operaciones(servicio):
    contrato = json.loads((RAIZ / "docs/contratos" / servicio / "openapi.json").read_text(encoding="utf-8"))
    for metodos in contrato["paths"].values():
        for item in metodos.values():
            codigo = next(c for c in item["responses"] if c.startswith("2"))
            yield item["operationId"], item["responses"][codigo]["content"]


@pytest.mark.parametrize("servicio", SERVICIOS)
def test_ejemplos_por_ruta_iguales_al_contrato(servicio):
    carpeta = RAIZ / "docs/contratos" / servicio / "ejemplos"
    for op, contenido in operaciones(servicio):
        en_json = json.loads((carpeta / (op + ".json")).read_text(encoding="utf-8"))
        en_xml = (carpeta / (op + ".xml")).read_text(encoding="utf-8")
        ET.fromstring(en_xml.encode("utf-8"))
        assert contenido["application/json"]["example"] == en_json
        assert contenido["application/xml"]["example"] == en_xml
        if op not in NO_GENERABLES:
            raiz = contenido["application/xml"]["schema"]["xml"]["name"]
            assert en_xml == (a_xml(en_json, raiz) + b"\n").decode("utf-8"), op


@pytest.mark.parametrize("servicio", SERVICIOS)
def test_openapi_servido_es_el_del_repo(crear_cliente, servicio):
    r = crear_cliente(servicio).get("/openapi.json")
    assert r.status_code == 200
    assert r.data == (RAIZ / "docs/contratos" / servicio / "openapi.json").read_bytes()
