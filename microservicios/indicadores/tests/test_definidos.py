"""Numerador, denominador y periodo de cada indicador del tablero (F7)."""
from datetime import date
from types import SimpleNamespace

import pytest

from microservicios.indicadores import consultas
from microservicios.indicadores import definidos

FILA = {"hoy": date(2026, 11, 21), "poblacion": 5784442, "municipios": 51, "casos": 120,
        "casos_previos": 104, "fallecidos": 3, "fallecidos_previos": 1, "graves": 12,
        "graves_previos": 9, "zonas": 3, "simulaciones": 1}


@pytest.fixture
def consulta(monkeypatch):
    """consulta.fila es lo que regresa la base; consulta.pedidas, cada consulta."""
    estado = SimpleNamespace(fila=dict(FILA), pedidas=[])

    def query(sql, params=None, one=False):
        estado.pedidas.append((sql, params, one))
        return dict(estado.fila)

    monkeypatch.setattr(definidos, "query", query)
    return estado


def por_clave(consulta):
    return {i["clave"]: i for i in definidos.calcular()}


def test_una_sola_consulta_con_los_filtros_de_siempre(consulta):
    definidos.calcular()
    ((sql, params, one),) = consulta.pedidas
    assert one is True
    assert params == {"estado": "19", "por_100k": 100000, "umbral": 10}
    assert "c.status IN ('pendiente', 'validado')" in sql
    assert "current_date - 6" in sql and "current_date - 13" in sql


def test_los_siete_indicadores_en_orden(consulta):
    assert [i["clave"] for i in definidos.calcular()] == [
        "casos_activos", "tasa_incidencia", "tasa_mortalidad", "letalidad", "casos_graves",
        "zonas_en_riesgo", "simulaciones_activas"]


def test_tasa_de_incidencia_con_numerador_denominador_y_periodo(consulta):
    tasa = por_clave(consulta)["tasa_incidencia"]
    assert tasa["valor"] == 2.1 and tasa["factor"] == 100000
    assert tasa["numerador"]["valor"] == 120 and tasa["denominador"]["valor"] == 5784442
    assert tasa["periodo"] == {"desde": "2026-11-15", "hasta": "2026-11-21", "dias": 7}
    assert tasa["previo"] == {"desde": "2026-11-08", "hasta": "2026-11-14", "dias": 7,
                              "valor": 1.8, "numerador": 104}
    assert tasa["unidad"] == "casos por 100 000 habitantes"


def test_las_variaciones_coinciden_con_los_campos_de_siempre(consulta):
    """casos_pct y tasa_pct salen de consultas.py: la misma cuenta da lo mismo."""
    ind = por_clave(consulta)
    assert ind["casos_activos"]["valor"] == 120
    assert ind["casos_activos"]["variacion_pct"] == consultas._pct_change(120, 104) == 15.4
    assert ind["tasa_incidencia"]["variacion_pct"] == consultas._pct_change(2.1, 1.8) == 16.7


def test_mortalidad_letalidad_y_graves(consulta):
    ind = por_clave(consulta)
    mortalidad = ind["tasa_mortalidad"]
    assert (mortalidad["valor"], mortalidad["previo"]["valor"]) == (0.05, 0.02)
    assert mortalidad["numerador"]["valor"] == 3 and mortalidad["variacion_pct"] == 150.0
    letalidad = ind["letalidad"]
    assert (letalidad["valor"], letalidad["factor"]) == (2.5, 100)
    assert letalidad["denominador"]["valor"] == 120 and letalidad["previo"] is None
    graves = ind["casos_graves"]
    assert (graves["valor"], graves["numerador"]["valor"], graves["unidad"]) == (10.0, 12, "% de los casos")


def test_conteos_sin_factor(consulta):
    ind = por_clave(consulta)
    zonas = ind["zonas_en_riesgo"]
    assert (zonas["valor"], zonas["factor"], zonas["denominador"]["valor"]) == (3, None, 51)
    simulaciones = ind["simulaciones_activas"]
    assert (simulaciones["valor"], simulaciones["denominador"]) == (1, None)
    assert simulaciones["periodo"] == {"desde": None, "hasta": None, "dias": None}
    assert simulaciones["previo"] is None and simulaciones["variacion_pct"] is None


def test_sin_casos_ni_poblacion_no_divide_entre_cero(consulta):
    consulta.fila.update(casos=0, casos_previos=0, fallecidos=0, fallecidos_previos=0, graves=0,
                         graves_previos=0, poblacion=None)
    ind = por_clave(consulta)
    assert ind["tasa_incidencia"]["valor"] is None
    assert ind["tasa_incidencia"]["variacion_pct"] is None
    assert ind["letalidad"]["valor"] is None
    assert (ind["casos_activos"]["valor"], ind["casos_activos"]["variacion_pct"]) == (0, 0.0)
