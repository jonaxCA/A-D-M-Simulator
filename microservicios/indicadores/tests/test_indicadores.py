from xml.etree import ElementTree as ET

import pytest

from microservicios.indicadores import consultas
from microservicios.indicadores import definidos

DEFINIDOS = [{"clave": "zonas_en_riesgo", "nombre": "Zonas en riesgo", "valor": 3,
              "unidad": "municipios", "numerador": {"valor": 3, "descripcion": "Municipios"},
              "denominador": {"valor": 51, "descripcion": "Municipios de Nuevo León"},
              "factor": None, "periodo": {"desde": "2026-11-15", "hasta": "2026-11-21", "dias": 7},
              "previo": None, "variacion_pct": None}]
INDICADORES = {"casos_activos": 120, "casos_pct": 15.4, "tasa_incidencia": 2.1,
               "tasa_pct": 15.4, "zonas_en_riesgo": 3, "simulaciones_activas": 1,
               "indicadores": DEFINIDOS}


@pytest.fixture
def llamadas(monkeypatch):
    conteo = {"indicadores": 0, "situacion": []}

    def indicadores():
        conteo["indicadores"] += 1
        return {k: v for k, v in INDICADORES.items() if k != "indicadores"}

    def situacion(limit=5):
        conteo["situacion"].append(limit)
        return [{"enfermedad": "Dengue", "estado": "alerta", "incidencia": 40}][:limit]

    monkeypatch.setattr(consultas, "get_resumen_indicadores", indicadores)
    monkeypatch.setattr(consultas, "get_resumen_situacion", situacion)
    monkeypatch.setattr(definidos, "calcular", lambda: [dict(d) for d in DEFINIDOS])
    return conteo


@pytest.fixture
def cliente(crear_cliente, llamadas):
    return crear_cliente("indicadores")


def test_indicadores_publicos_en_json(cliente):
    r = cliente.get("/api/v1/dashboard/indicators?format=json")
    assert r.status_code == 200
    assert r.get_json() == INDICADORES


def test_indicadores_en_xml(cliente):
    raiz = ET.fromstring(cliente.get("/api/v1/dashboard/indicators").data)
    assert raiz.tag == "indicadores"
    assert raiz.findtext("zonas_en_riesgo") == "3"
    zonas = raiz.find("indicadores/indicador")
    assert zonas.findtext("clave") == "zonas_en_riesgo"
    assert zonas.findtext("denominador/valor") == "51"
    assert zonas.find("factor").get("nil") == "true"


def test_segunda_consulta_sale_de_cache(cliente, llamadas, redis_falso):
    cliente.get("/api/v1/dashboard/indicators?format=json")
    r = cliente.get("/api/v1/dashboard/indicators?format=json")
    assert r.get_json() == INDICADORES
    assert llamadas["indicadores"] == 1
    assert 0 < redis_falso.ttl("cache:indicadores:indicators") <= 60


def test_con_redis_caido_responde_desde_la_base(cliente, llamadas, apagar_redis):
    apagar_redis()
    r = cliente.get("/api/v1/dashboard/indicators?format=json")
    assert r.status_code == 200
    assert r.get_json() == INDICADORES
    cliente.get("/api/v1/dashboard/indicators?format=json")
    assert llamadas["indicadores"] == 2


def test_situacion_con_limite(cliente, llamadas):
    r = cliente.get("/api/v1/dashboard/situation?limit=3&format=json")
    assert r.status_code == 200
    assert r.get_json()["enfermedades"][0]["estado"] == "alerta"
    assert llamadas["situacion"] == [3]
    raiz = ET.fromstring(cliente.get("/api/v1/dashboard/situation").data)
    assert raiz.find("enfermedades").find("enfermedad").findtext("enfermedad") == "Dengue"


@pytest.mark.parametrize("limite", ["0", "21", "x", "-1"])
def test_situacion_limite_invalido(cliente, limite):
    r = cliente.get("/api/v1/dashboard/situation?limit=%s&format=json" % limite)
    assert r.status_code == 422
