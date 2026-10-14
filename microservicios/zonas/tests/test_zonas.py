from xml.etree import ElementTree as ET

import pytest

from backend_web import queries
from microservicios.zonas.rutas import mayor_cambio


def zona(id_, nombre, casos, variacion):
    return {"id": id_, "zona": nombre, "casos": casos, "incidencia": 1.0,
            "variacion": variacion, "graves": 0, "estado": "estable"}


TODAS = [zona(1, "Monterrey", 50, 20.0), zona(2, "Apodaca", 30, 80.0),
         zona(3, "Escobedo", 10, 80.0), zona(4, "Juárez", 0, 0.0)]


def test_mayor_cambio_empate_gana_la_primera():
    assert mayor_cambio(TODAS) == {"estado": "con_aumento",
                                   "zona": {"id": 2, "zona": "Apodaca", "variacion": 80.0}}


def test_mayor_cambio_sin_aumento_no_nombra_zona():
    assert mayor_cambio([zona(1, "Monterrey", 5, 0.0), zona(2, "Apodaca", 3, -10.0)]) == \
        {"estado": "sin_aumento", "zona": None}


def test_mayor_cambio_sin_casos():
    assert mayor_cambio([zona(4, "Juárez", 0, 100.0)]) == {"estado": "sin_casos", "zona": None}


@pytest.fixture
def llamadas(monkeypatch):
    registro = []

    def monitoreo_zonas(disease_id=None, region_id=None, dias=30, busqueda=None,
                        orden="casos", pagina=1, por_pagina=10):
        registro.append({"busqueda": busqueda, "orden": orden, "pagina": pagina,
                         "por_pagina": por_pagina, "dias": dias})
        inicio = (pagina - 1) * por_pagina
        filas = TODAS[inicio:inicio + por_pagina]
        return {"zonas": filas, "total": len(TODAS), "pagina": pagina, "paginas": 1,
                "desde": inicio + 1, "hasta": inicio + len(filas)}

    monkeypatch.setattr(queries, "get_monitoreo_zonas", monitoreo_zonas)
    monkeypatch.setattr(queries, "get_mapa_municipios", lambda disease_id=None, dias=30: [
        {"id": 1, "region_code": "19039", "nombre": "Monterrey", "casos": 50,
         "incidencia": 4.4, "variacion": 20.0, "lat": 25.67, "lon": -100.31, "nivel": "baja"}])
    monkeypatch.setattr(queries, "get_tendencia_zona", lambda region_id, disease_id=None, dias=14: [
        {"fecha": "2026-10-11", "total": 2}])
    monkeypatch.setattr(queries, "get_mapa_serie_temporal", lambda disease_id=None, dias=30: {
        "fechas": ["2026-10-11", "2026-10-12"], "dias_periodo": 2,
        "series": {"19039": {"casos": [1, 3], "incidencia": [0.1, 0.3], "variacion": [0.0, 50.0]},
                   "19006": {"casos": [0, 0], "incidencia": [0.0, 0.0], "variacion": [0.0, 0.0]}}})
    monkeypatch.setattr(queries, "get_enfermedad", lambda i: {"id": i})
    monkeypatch.setattr(queries, "get_region_municipio", lambda i: {"id": i})
    return registro


@pytest.fixture
def cliente(crear_cliente, llamadas):
    return crear_cliente("zonas")


@pytest.mark.parametrize("ruta", ["/api/v1/zones", "/api/v1/zones/map"])
def test_sin_token_es_401(cliente, ruta):
    assert cliente.get(ruta + "?format=json").status_code == 401


def test_mayor_cambio_usa_todas_las_zonas_no_la_pagina(cliente, token, llamadas):
    r = cliente.get("/api/v1/zones?size=1&page=1&q=monte&format=json", headers=token())
    assert r.status_code == 200
    datos = r.get_json()
    assert [z["zona"] for z in datos["zonas"]] == ["Monterrey"]
    assert datos["mayor_cambio"]["zona"]["zona"] == "Apodaca"
    assert datos["filtros"] == {"disease_id": None, "region_id": None, "days": 30,
                                "q": "monte", "order": "incidencia"}
    pagina, todas = llamadas
    assert (pagina["busqueda"], pagina["orden"], pagina["por_pagina"]) == ("monte", "incidencia", 1)
    assert (todas["busqueda"], todas["orden"], todas["pagina"]) == (None, "casos", 1)
    assert todas["por_pagina"] >= 51


@pytest.mark.parametrize("consulta", ["order=nombre", "size=101", "page=0", "days=60"])
def test_parametros_invalidos_de_la_tabla(cliente, token, consulta):
    r = cliente.get("/api/v1/zones?%s&format=json" % consulta, headers=token())
    assert r.status_code == 422


def test_zonas_en_xml(cliente, token):
    raiz = ET.fromstring(cliente.get("/api/v1/zones", headers=token()).data)
    assert raiz.tag == "zonas_detalle"
    assert len(raiz.find("zonas").findall("zona")) == 4
    assert raiz.find("mayor_cambio").findtext("estado") == "con_aumento"


def test_mapa_serie_como_lista_y_xml_valido(cliente, token):
    r = cliente.get("/api/v1/zones/map?days=60&format=json", headers=token())
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["municipios"][0]["tendencia"] == [{"fecha": "2026-10-11", "total": 2}]
    assert [m["region_code"] for m in datos["serie"]["municipios"]] == ["19006", "19039"]
    assert "series" not in datos["serie"]
    raiz = ET.fromstring(cliente.get("/api/v1/zones/map", headers=token()).data)
    assert raiz.find("serie").find("fechas").findtext("fecha") == "2026-10-11"


def test_mapa_rechaza_periodo_de_monitoreo(cliente, token):
    assert cliente.get("/api/v1/zones/map?days=90&format=json", headers=token()).status_code == 422


def test_mapa_desde_cache(cliente, token, redis_falso, monkeypatch):
    cabeceras = token()
    cliente.get("/api/v1/zones/map?format=json", headers=cabeceras)
    monkeypatch.setattr(queries, "get_mapa_municipios",
                        lambda **_: pytest.fail("debió salir de la caché"))
    assert cliente.get("/api/v1/zones/map?format=json", headers=cabeceras).status_code == 200
