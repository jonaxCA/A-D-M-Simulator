from xml.etree import ElementTree as ET

import pytest

from backend_web import queries

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

    monkeypatch.setattr(queries, "get_monitoreo_serie", falsa(
        "serie", [{"fecha": "2026-10-01", "casos": 4, "incidencia_acum": 0.07}]))
    monkeypatch.setattr(queries, "get_monitoreo_edad", falsa(
        "edad", [{"grupo": g, "casos": 0} for g in queries.GRUPOS_EDAD]))
    monkeypatch.setattr(queries, "get_monitoreo_sexo", falsa(
        "sexo", [{"label": "Femenino", "casos": 3, "pct": 75.0}]))
    monkeypatch.setattr(queries, "get_monitoreo_totales", falsa(
        "totales", {"casos": 4, "casos_previo": 2, "casos_pct": 100.0,
                    "incidencia": 0.1, "incidencia_previa": 0.0}))
    monkeypatch.setattr(queries, "get_enfermedad", lambda i: {"id": i} if i == 1 else None)
    monkeypatch.setattr(queries, "get_region_municipio", lambda i: {"id": i} if i == 39 else None)
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
    assert [g.findtext("grupo") for g in raiz.find("grupos").findall("grupo")] == queries.GRUPOS_EDAD
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
