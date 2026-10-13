import json
from xml.etree import ElementTree as ET

import pytest

from backend_web import queries

TIPOS = [
    {"id": 1, "code": "CIERRE_ESCUELAS", "name": "Cierre de escuelas",
     "description": "Desactiva la capa escuela.", "target_layer": "escuela",
     "primitive": "edge_modifier",
     "param_schema": {"type": "object", "required": ["reduccion"],
                      "properties": {"reduccion": {"type": "number", "minimum": 0, "maximum": 1}}},
     "unit_cost": None, "cost_unit": None, "cost_source": None, "cost_is_assumption": False},
    {"id": 2, "code": "CUBREBOCAS", "name": "Uso de cubrebocas", "description": None,
     "target_layer": "todas", "primitive": "edge_modifier", "param_schema": {},
     "unit_cost": 12.5, "cost_unit": "persona", "cost_source": "Supuesto", "cost_is_assumption": True},
]


@pytest.fixture
def cliente(crear_cliente, monkeypatch):
    monkeypatch.setattr(queries, "get_tipos_intervencion", lambda: [dict(t) for t in TIPOS])
    return crear_cliente("tipos_intervencion")


def test_lista_en_json_sin_token(cliente):
    r = cliente.get("/api/v1/intervention-types?format=json")
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["total"] == 2
    assert datos["tipos"][0]["param_schema"]["required"] == ["reduccion"]


def test_lista_en_xml_por_omision(cliente):
    r = cliente.get("/api/v1/intervention-types")
    assert r.status_code == 200
    assert r.content_type.startswith("application/xml")
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "catalogo_tipos_intervencion"
    assert [t.findtext("code") for t in raiz.find("tipos").findall("tipo")] == \
        ["CIERRE_ESCUELAS", "CUBREBOCAS"]


def test_detalle_por_codigo_sin_importar_mayusculas(cliente):
    r = cliente.get("/api/v1/intervention-types/cubrebocas",
                    headers={"Accept": "application/json"})
    assert r.status_code == 200
    assert r.get_json()["unit_cost"] == 12.5


@pytest.mark.parametrize("codigo", ["NO_EXISTE", "1ABC", "a-b", "X" * 60])
def test_codigo_desconocido_o_invalido_es_404(cliente, codigo):
    r = cliente.get("/api/v1/intervention-types/%s?format=json" % codigo)
    assert r.status_code == 404
    assert r.content_type.startswith("application/problem+json")
    assert json.loads(r.data)["codigo"] == "NO_ENCONTRADO"


def test_formato_desconocido_es_400(cliente):
    assert cliente.get("/api/v1/intervention-types?format=csv").status_code == 400
