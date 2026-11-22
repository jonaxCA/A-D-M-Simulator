"""Agregación por día, semana epidemiológica o mes, grupos, paginación y Highcharts (F7)."""
from datetime import date, datetime, timezone

import pytest

from microservicios.series import consultas
from epidemia_comun.errores import ErrorAPI
from microservicios.series import agregadas

D = date.fromisoformat


@pytest.fixture
def base(monkeypatch):
    """base.filas: lo que regresa el conteo; base.pedidas: cada consulta (sql, params)."""
    class Base:
        filas = []
        pedidas = []
        hoy = D("2026-11-21")

    def query(sql, params=None, one=False):
        Base.pedidas.append((sql, params))
        if "current_date AS hoy" in sql:
            return {"hoy": Base.hoy}
        return [dict(f) for f in Base.filas]

    monkeypatch.setattr(agregadas, "query", query)
    Base.filas, Base.pedidas = [], []
    return Base


@pytest.mark.parametrize("domingo,semana", [
    ("2025-12-28", "2025-53"),  # 1 de enero de 2026 es jueves: esa semana es la 53 de 2025
    ("2026-01-04", "2026-01"),
    ("2026-11-15", "2026-46"),
    ("2020-12-27", "2020-53"),
    ("2021-12-26", "2021-52"),
    ("2022-01-02", "2022-01"),
])
def test_semana_epidemiologica(domingo, semana):
    assert agregadas.semana_epi(D(domingo)) == semana


def test_periodos_por_semana_de_domingo_a_sabado():
    assert agregadas.periodos(D("2026-11-18"), D("2026-11-30"), "semana") == [
        (D("2026-11-15"), D("2026-11-21")), (D("2026-11-22"), D("2026-11-28")),
        (D("2026-11-29"), D("2026-12-05"))]


def test_periodos_por_mes_y_por_dia():
    assert agregadas.periodos(D("2026-01-31"), D("2026-03-01"), "mes") == [
        (D("2026-01-01"), D("2026-01-31")), (D("2026-02-01"), D("2026-02-28")),
        (D("2026-03-01"), D("2026-03-31"))]
    assert [i for i, _ in agregadas.periodos(D("2026-11-19"), D("2026-11-21"), "dia")] == [
        D("2026-11-19"), D("2026-11-20"), D("2026-11-21")]


def test_por_semana_sin_huecos_con_acumulado_y_completo(base):
    base.filas = [{"inicio": D("2026-11-15"), "grupo": None, "casos": 4},
                  {"inicio": D("2026-11-29"), "grupo": None, "casos": 2}]
    datos = agregadas.calcular(D("2026-11-18"), D("2026-11-30"), "semana")
    assert [(p["inicio"], p["casos"], p["acumulado"]) for p in datos["periodos"]] == [
        ("2026-11-15", 4, 4), ("2026-11-22", 0, 4), ("2026-11-29", 2, 6)]
    assert [p["completo"] for p in datos["periodos"]] == [False, True, False]
    assert [p["semana_epi"] for p in datos["periodos"]] == ["2026-46", "2026-47", "2026-48"]
    assert datos["total_casos"] == 6 and datos["grupos"] == []
    assert datos["periodos"][0]["por_grupo"] == []


def test_por_sexo_con_etiquetas_y_ordenado_por_casos(base):
    base.filas = [{"inicio": D("2026-11-20"), "grupo": "F", "casos": 2},
                  {"inicio": D("2026-11-21"), "grupo": "M", "casos": 5},
                  {"inicio": D("2026-11-21"), "grupo": None, "casos": 1},
                  {"inicio": D("2026-11-21"), "grupo": "X", "casos": 1}]
    datos = agregadas.calcular(D("2026-11-20"), D("2026-11-21"), "dia", "sexo")
    assert datos["grupos"] == ["Masculino", "Femenino", "No especificado"]
    ultimo = datos["periodos"][1]
    assert ultimo["casos"] == 7
    assert ultimo["por_grupo"] == [{"grupo": "Masculino", "casos": 5},
                                   {"grupo": "Femenino", "casos": 0},
                                   {"grupo": "No especificado", "casos": 2}]
    assert ultimo["semana_epi"] is None


def test_por_edad_siempre_los_seis_grupos(base):
    base.filas = [{"inicio": D("2026-11-21"), "grupo": "25-44", "casos": 3}]
    assert agregadas.calcular(D("2026-11-21"), D("2026-11-21"), "dia", "edad")["grupos"] == \
        list(consultas.GRUPOS_EDAD)
    base.filas.append({"inicio": D("2026-11-21"), "grupo": None, "casos": 1})
    assert agregadas.calcular(D("2026-11-21"), D("2026-11-21"), "dia", "edad")["grupos"][-1] == \
        "No especificado"


def test_grupos_y_sexos_como_en_monitoreo():
    assert list(agregadas.GRUPOS_EDAD) == consultas.GRUPOS_EDAD
    assert agregadas.SEXOS == consultas.SEXOS


@pytest.mark.parametrize("agrupar,union", [("enfermedad", "JOIN diseases"), ("municipio", "JOIN regions r")])
def test_la_consulta_filtra_como_siempre(base, agrupar, union):
    agregadas.calcular(D("2026-11-01"), D("2026-11-21"), "mes", agrupar, disease_id=3, region_id=39)
    ((sql, params),) = base.pedidas
    assert "c.status IN ('pendiente', 'validado')" in sql and union in sql
    assert "c.region_id = %(region_id)s" in sql and "c.disease_id = %(disease_id)s" in sql
    assert "date_trunc('month', c.report_date)" in sql
    assert params["desde"] == D("2026-11-01") and params["region_id"] == 39


def test_sin_municipio_todo_nuevo_leon(base):
    agregadas.calcular(D("2026-11-01"), D("2026-11-21"), "dia")
    ((sql, params),) = base.pedidas
    assert "parent_region_id" in sql and params["estado"] == "19"
    assert "c.disease_id" not in sql


def test_pagina_de_periodos(base):
    datos = agregadas.calcular(D("2026-11-01"), D("2026-11-21"), "dia")
    hoja = agregadas.pagina(datos, 2, 10)
    assert (hoja["total"], hoja["pagina"], hoja["paginas"]) == (21, 2, 3)
    assert [p["inicio"] for p in hoja["periodos"]][:1] == ["2026-11-11"] and len(hoja["periodos"]) == 10
    assert agregadas.pagina(datos, 5, 10)["periodos"] == []


def test_highcharts_una_serie_por_grupo(base):
    base.filas = [{"inicio": D("2026-11-15"), "grupo": "F", "casos": 2},
                  {"inicio": D("2026-11-22"), "grupo": "M", "casos": 1}]
    opciones = agregadas.highcharts(agregadas.calcular(D("2026-11-15"), D("2026-11-28"), "semana", "sexo"))
    assert opciones["xAxis"] == {"type": "datetime"}
    x0 = int(datetime(2026, 11, 15, tzinfo=timezone.utc).timestamp() * 1000)
    assert opciones["series"] == [
        {"name": "Femenino", "data": [{"x": x0, "y": 2}, {"x": x0 + 7 * 86400000, "y": 0}]},
        {"name": "Masculino", "data": [{"x": x0, "y": 0}, {"x": x0 + 7 * 86400000, "y": 1}]}]


def test_highcharts_sin_grupo_es_una_serie_de_casos(base):
    base.filas = [{"inicio": D("2026-11-21"), "grupo": None, "casos": 3}]
    opciones = agregadas.highcharts(agregadas.calcular(D("2026-11-21"), D("2026-11-21"), "dia"))
    assert [s["name"] for s in opciones["series"]] == ["Casos"]
    assert opciones["series"][0]["data"][0]["y"] == 3


def test_rango_por_omision_90_dias_hasta_hoy_de_la_base(base):
    assert agregadas.rango({}, None) == (D("2026-08-24"), D("2026-11-21"))
    assert agregadas.rango({}, 7) == (D("2026-11-15"), D("2026-11-21"))
    assert agregadas.rango({"from": "2026-01-01", "to": "2026-03-31"}, None) == (
        D("2026-01-01"), D("2026-03-31"))
    assert agregadas.rango({"from": "2026-11-01"}, None) == (D("2026-11-01"), D("2026-11-21"))


@pytest.mark.parametrize("args,dias,mensaje", [
    ({"from": "2026-01-01"}, 30, "days o from"),
    ({"from": "01/11/2026"}, None, "from debe ser una fecha"),
    ({"to": "ayer"}, None, "to debe ser una fecha"),
    ({"from": "2026-11-10", "to": "2026-11-01"}, None, "posterior"),
    ({"from": "2024-01-01", "to": "2026-01-01"}, None, "731"),
])
def test_rango_invalido_es_422(base, args, dias, mensaje):
    with pytest.raises(ErrorAPI) as error:
        agregadas.rango(args, dias)
    assert error.value.estado == 422 and mensaje in error.value.detalle
