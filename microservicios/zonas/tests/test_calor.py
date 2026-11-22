"""Puntos agregados para el mapa de calor (F7)."""
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from microservicios.zonas import consultas
from microservicios.zonas import calor


@pytest.fixture
def base(monkeypatch):
    """base.filas: lo que regresa el conteo por celda; base.pedidas: (sql, params)."""
    estado = SimpleNamespace(pedidas=[], filas=[
        {"fila": 2567, "columna": -10032, "casos": 12},   # Monterrey centro
        {"fila": 2574, "columna": -10022, "casos": 4},
        {"fila": 2580, "columna": -10030, "casos": 2},    # menos de 3: no se publica
        {"fila": None, "columna": None, "casos": 5},      # sin coordenadas
    ])

    def query(sql, params=None, one=False):
        estado.pedidas.append((sql, params))
        return [dict(f) for f in estado.filas]

    monkeypatch.setattr(calor, "query", query)
    return estado


def test_celdas_con_su_centro_peso_y_supresion(base):
    datos = calor.calcular("0.01", 30)
    assert datos["puntos"] == [
        {"lat": 25.675, "lon": -100.315, "casos": 12, "peso": 1.0},
        {"lat": 25.745, "lon": -100.215, "casos": 4, "peso": 0.3333}]
    assert (datos["total_casos"], datos["casos_en_puntos"]) == (23, 16)
    assert (datos["casos_sin_coordenadas"], datos["casos_suprimidos"], datos["celdas_suprimidas"]) == (5, 2, 1)
    assert (datos["celda_grados"], datos["minimo_por_celda"]) == (0.01, 3)


def test_la_consulta_filtra_como_siempre(base):
    calor.calcular("0.05", 7, disease_id=3, region_id=39)
    ((sql, params),) = base.pedidas
    assert "c.status IN ('pendiente', 'validado')" in sql
    assert "c.region_id = %(region_id)s" in sql and "c.disease_id = %(disease_id)s" in sql
    assert params["celda"] == "0.05" and params["dias"] == 6 and params["region_id"] == 39


def test_sin_municipio_todo_nuevo_leon(base):
    calor.calcular("0.01", 30)
    ((sql, params),) = base.pedidas
    assert "parent_region_id" in sql and params["estado"] == "19" and "c.disease_id" not in sql


def test_sin_casos(base):
    base.filas = []
    datos = calor.calcular("0.01", 30)
    assert datos["puntos"] == [] and datos["total_casos"] == 0


def test_la_celda_mas_fina_es_de_un_kilometro():
    assert min(float(c) for c in calor.CELDAS) >= 0.01


# --------------------------------------------------------------------------- la ruta

@pytest.fixture
def cliente(crear_cliente, base, monkeypatch):
    monkeypatch.setattr(consultas, "get_enfermedad", lambda i: {"id": i} if i == 1 else None)
    monkeypatch.setattr(consultas, "get_region_municipio", lambda i: {"id": i} if i == 39 else None)
    return crear_cliente("zonas")


def test_pide_sesion(cliente):
    assert cliente.get("/api/v1/zones/heatmap?format=json").status_code == 401


def test_mapa_de_calor_en_json(cliente, token, base):
    r = cliente.get("/api/v1/zones/heatmap?days=90&cell=0.02&disease_id=1&format=json",
                    headers=token())
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["filtros"] == {"disease_id": 1, "region_id": None, "days": 90, "cell": 0.02}
    assert len(datos["puntos"]) == 2 and base.pedidas[0][1]["dias"] == 89


def test_mapa_de_calor_en_xml(cliente, token):
    raiz = ET.fromstring(cliente.get("/api/v1/zones/heatmap", headers=token()).data)
    assert raiz.tag == "mapa_calor"
    assert raiz.find("puntos/punto").findtext("lat") == "25.675"
    assert raiz.find("filtros").findtext("days") == "30"


@pytest.mark.parametrize("consulta,estado", [("cell=0.001", 422), ("days=14", 422),
                                             ("disease_id=99", 404), ("region_id=1", 404)])
def test_filtros_invalidos(cliente, token, consulta, estado):
    assert cliente.get("/api/v1/zones/heatmap?%s&format=json" % consulta,
                       headers=token()).status_code == estado


def test_sale_de_cache(cliente, token, base):
    cabeceras = token()
    for _ in range(2):
        cliente.get("/api/v1/zones/heatmap?days=7", headers=cabeceras)
    cliente.get("/api/v1/zones/heatmap?days=7&cell=0.05", headers=cabeceras)
    assert len(base.pedidas) == 2
