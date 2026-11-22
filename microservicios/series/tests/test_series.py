from xml.etree import ElementTree as ET

import pytest

from microservicios.series import consultas

RUTAS = ["/api/v1/series/cases", "/api/v1/series/cases/by-age",
         "/api/v1/series/cases/by-sex", "/api/v1/series/cases/totals"]


@pytest.fixture
def llamadas(monkeypatch):
    registro = []

    def falsa(nombre, salida):
        def consulta(disease_id=None, region_id=None, dias=30):
            registro.append((nombre, disease_id, region_id, dias))
            return salida
        return consulta

    monkeypatch.setattr(consultas, "get_monitoreo_serie", falsa(
        "serie", [{"fecha": "2026-10-01", "casos": 4, "incidencia_acum": 0.07}]))
    monkeypatch.setattr(consultas, "get_monitoreo_edad", falsa(
        "edad", [{"grupo": g, "casos": 0} for g in consultas.GRUPOS_EDAD]))
    monkeypatch.setattr(consultas, "get_monitoreo_sexo", falsa(
        "sexo", [{"label": "Femenino", "casos": 3, "pct": 75.0}]))
    monkeypatch.setattr(consultas, "get_monitoreo_totales", falsa(
        "totales", {"casos": 4, "casos_previo": 2, "casos_pct": 100.0,
                    "incidencia": 0.1, "incidencia_previa": 0.0}))
    monkeypatch.setattr(consultas, "get_enfermedad", lambda i: {"id": i} if i == 1 else None)
    monkeypatch.setattr(consultas, "get_region_municipio", lambda i: {"id": i} if i == 39 else None)
    return registro


@pytest.fixture
def cliente(crear_cliente, llamadas):
    return crear_cliente("series")


@pytest.mark.parametrize("ruta", RUTAS)
def test_sin_token_es_401(cliente, ruta):
    r = cliente.get(ruta + "?format=json")
    assert r.status_code == 401
    assert r.get_json()["codigo"] == "TOKEN_AUSENTE"


@pytest.mark.parametrize("ruta", RUTAS)
def test_cualquier_rol_con_sesion_puede_consultar(cliente, token, ruta):
    for rol in ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR"):
        assert cliente.get(ruta + "?format=json", headers=token((rol,))).status_code == 200


def test_sesion_cerrada_es_rechazada(cliente, token):
    r = cliente.get(RUTAS[0] + "?format=json", headers=token(sesion_activa=False))
    assert r.status_code == 401
    assert r.get_json()["codigo"] == "TOKEN_REVOCADO"


def test_filtros_llegan_a_la_consulta(cliente, token, llamadas):
    r = cliente.get("/api/v1/series/cases?disease_id=1&region_id=39&days=7&format=json",
                    headers=token())
    assert r.status_code == 200
    assert r.get_json()["filtros"] == {"disease_id": 1, "region_id": 39, "days": 7}
    assert llamadas == [("serie", 1, 39, 7)]


def test_por_omision_todo_nuevo_leon_30_dias(cliente, token, llamadas):
    cliente.get("/api/v1/series/cases/totals?format=json", headers=token())
    assert llamadas == [("totales", None, None, 30)]


@pytest.mark.parametrize("consulta", ["days=15", "days=abc", "disease_id=0", "region_id=x"])
def test_filtro_invalido_es_422(cliente, token, consulta):
    r = cliente.get("/api/v1/series/cases?%s&format=json" % consulta, headers=token())
    assert r.status_code == 422


@pytest.mark.parametrize("consulta", ["disease_id=99", "region_id=1"])
def test_enfermedad_o_municipio_inexistente_es_404(cliente, token, consulta):
    r = cliente.get("/api/v1/series/cases?%s&format=json" % consulta, headers=token())
    assert r.status_code == 404


def test_por_edad_en_xml(cliente, token):
    raiz = ET.fromstring(cliente.get("/api/v1/series/cases/by-age", headers=token()).data)
    assert raiz.tag == "casos_por_edad"
    assert [g.findtext("grupo") for g in raiz.find("grupos").findall("grupo")] == consultas.GRUPOS_EDAD
    assert raiz.find("filtros").find("disease_id").get("nil") == "true"


def test_cache_por_ambito(cliente, token, llamadas):
    cabeceras = token()
    cliente.get("/api/v1/series/cases/by-sex?days=7", headers=cabeceras)
    cliente.get("/api/v1/series/cases/by-sex?days=7", headers=cabeceras)
    cliente.get("/api/v1/series/cases/by-sex?days=30", headers=cabeceras)
    assert [l[3] for l in llamadas] == [7, 30]


def test_redis_caido_es_503_en_ruta_protegida(cliente, token, apagar_redis):
    cabeceras = token()
    apagar_redis()
    r = cliente.get("/api/v1/series/cases?format=json", headers=cabeceras)
    assert r.status_code == 503
    assert r.get_json()["codigo"] == "SERVICIO_NO_DISPONIBLE"


# ------------------------------------- rango libre, agregación, paginación y Highcharts (F7)

NUEVAS = ["/api/v1/series/cases/aggregate", "/api/v1/series/cases/highcharts"]


@pytest.fixture
def conteo(monkeypatch):
    """Lo que regresa la base a agregadas: hoy es 2026-11-21 y hay casos el 20 y el 21."""
    from datetime import date
    from microservicios.series import agregadas
    pedidas = []

    def query(sql, params=None, one=False):
        if "current_date AS hoy" in sql:
            return {"hoy": date(2026, 11, 21)}
        pedidas.append(params)
        return [{"inicio": date(2026, 11, 20), "grupo": "F", "casos": 2},
                {"inicio": date(2026, 11, 21), "grupo": "M", "casos": 3}]

    monkeypatch.setattr(agregadas, "query", query)
    return pedidas


@pytest.mark.parametrize("ruta", NUEVAS)
def test_las_nuevas_piden_sesion(cliente, conteo, ruta):
    assert cliente.get(ruta + "?format=json").status_code == 401


def test_agregada_paginada_con_sus_filtros(cliente, token, conteo):
    r = cliente.get("/api/v1/series/cases/aggregate?from=2026-11-15&to=2026-11-21&group_by=sexo"
                    "&page=2&size=5&disease_id=1&format=json", headers=token())
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["filtros"] == {"disease_id": 1, "region_id": None, "desde": "2026-11-15",
                                "hasta": "2026-11-21", "intervalo": "dia", "agrupar": "sexo"}
    assert (datos["total"], datos["pagina"], datos["paginas"]) == (7, 2, 2)
    assert [p["inicio"] for p in datos["periodos"]] == ["2026-11-20", "2026-11-21"]
    assert datos["grupos"] == ["Masculino", "Femenino"] and datos["total_casos"] == 5
    assert conteo[0]["disease_id"] == 1


def test_agregada_por_omision_90_dias_por_dia(cliente, token, conteo):
    datos = cliente.get("/api/v1/series/cases/aggregate?format=json", headers=token()).get_json()
    assert (datos["filtros"]["desde"], datos["filtros"]["hasta"]) == ("2026-08-24", "2026-11-21")
    assert datos["total"] == 90 and datos["paginas"] == 2 and len(datos["periodos"]) == 52


def test_agregada_con_days_y_por_semana_en_xml(cliente, token, conteo):
    raiz = ET.fromstring(cliente.get("/api/v1/series/cases/aggregate?days=7&interval=semana",
                                     headers=token()).data)
    assert raiz.tag == "serie_agregada"
    periodos = raiz.find("periodos").findall("periodo")
    assert [p.findtext("semana_epi") for p in periodos] == ["2026-46"]
    assert periodos[0].findtext("completo") == "true"


def test_highcharts_en_json_y_xml(cliente, token, conteo):
    datos = cliente.get("/api/v1/series/cases/highcharts?days=7&group_by=sexo&format=json",
                        headers=token()).get_json()
    assert datos["xAxis"] == {"type": "datetime"}
    assert [s["name"] for s in datos["series"]] == ["Masculino", "Femenino"]
    assert [p["y"] for p in datos["series"][0]["data"]] == [0, 0, 0, 0, 0, 0, 3]
    raiz = ET.fromstring(cliente.get("/api/v1/series/cases/highcharts?days=7", headers=token()).data)
    assert raiz.tag == "highcharts"
    assert raiz.find("series/serie").findtext("name") == "Casos"
    assert len(raiz.find("series/serie/data").findall("punto")) == 7


@pytest.mark.parametrize("consulta", ["size=367", "size=0", "page=0", "interval=anio",
                                      "group_by=edad_y_sexo", "days=7&from=2026-11-01",
                                      "from=2026-11-21&to=2026-11-01", "from=21-11-2026"])
def test_agregada_invalida_es_422(cliente, token, conteo, consulta):
    r = cliente.get("/api/v1/series/cases/aggregate?%s&format=json" % consulta, headers=token())
    assert r.status_code == 422, consulta


def test_agregada_con_enfermedad_inexistente_es_404(cliente, token, conteo):
    r = cliente.get("/api/v1/series/cases/highcharts?disease_id=99&format=json", headers=token())
    assert r.status_code == 404


def test_agregada_sale_de_cache_por_filtros(cliente, token, conteo):
    cabeceras = token()
    for _ in range(2):
        cliente.get("/api/v1/series/cases/aggregate?days=7&page=1", headers=cabeceras)
    cliente.get("/api/v1/series/cases/highcharts?days=7", headers=cabeceras)
    assert len(conteo) == 1
    cliente.get("/api/v1/series/cases/aggregate?days=7&interval=mes", headers=cabeceras)
    assert len(conteo) == 2
