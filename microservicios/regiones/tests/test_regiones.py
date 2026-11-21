from xml.etree import ElementTree as ET

import pytest

from backend_web import queries

MONTERREY = {"id": 39, "code": "19039", "name": "Monterrey", "level": "municipio",
             "parent_region_id": 1, "population": 1142994, "population_60plus": 158771}
CATALOGO = {
    "municipios": [{"id": 39, "code": "19039", "nombre": "Monterrey", "poblacion": 1142994,
                    "poblacion_60": 158771,
                    "fuente_poblacion": {"tipo": "censal", "fuente": "INEGI, Censo 2020"},
                    "fuente_poblacion_60": {"tipo": "derivado",
                                            "fuente": "Grupos 60-79 y 80+ del Censo 2020"}}],
    "total": 1, "busqueda": "", "orden": "nombre", "direccion": "asc",
}


@pytest.fixture
def cliente(crear_cliente, monkeypatch):
    pedidos = []
    monkeypatch.setattr(queries, "get_regiones_catalogo", lambda **f: pedidos.append(f) or CATALOGO)
    monkeypatch.setattr(queries, "get_region_municipio",
                        lambda i: dict(MONTERREY) if i == 39 else None)
    c = crear_cliente("regiones")
    c.pedidos = pedidos
    return c


def test_lista_xml_por_omision(cliente):
    r = cliente.get("/api/v1/regions")
    assert r.status_code == 200 and r.content_type.startswith("application/xml")
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "catalogo_regiones"
    municipio = raiz.find("municipios").find("municipio")
    assert municipio.findtext("nombre") == "Monterrey"
    assert municipio.find("fuente_poblacion").findtext("tipo") == "censal"


def test_lista_json_con_format_y_con_accept(cliente):
    assert cliente.get("/api/v1/regions?format=json").get_json()["total"] == 1
    r = cliente.get("/api/v1/regions", headers={"Accept": "application/json"})
    assert r.content_type.startswith("application/json")


def test_navegador_recibe_xml(cliente):
    r = cliente.get("/api/v1/regions", headers={"Accept": "text/html"})
    assert r.content_type.startswith("application/xml")


def test_format_invalido_es_400(cliente):
    r = cliente.get("/api/v1/regions?format=html")
    assert r.status_code == 400 and r.content_type.startswith("application/problem")


def test_lista_pasa_busqueda_y_orden(cliente):
    cliente.get("/api/v1/regions?q= monte &order=poblacion&direction=desc&format=json")
    assert cliente.pedidos == [{"busqueda": "monte", "orden": "poblacion", "direccion": "desc"}]


@pytest.mark.parametrize("consulta", ["order=habitantes", "direction=arriba"])
def test_orden_invalido_es_422(cliente, consulta):
    r = cliente.get("/api/v1/regions?format=json&" + consulta)
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"


def test_municipio_y_no_encontrado(cliente):
    assert cliente.get("/api/v1/regions/39?format=json").get_json()["population"] == 1142994
    r = cliente.get("/api/v1/regions/1?format=json")
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"


def test_es_publico_y_de_solo_lectura(cliente):
    assert cliente.get("/api/v1/regions?format=json").status_code == 200
    assert cliente.put("/api/v1/regions/39?format=json", json={"name": "X"}).status_code == 405
    assert cliente.post("/api/v1/regions?format=json", json={}).status_code == 405


def test_responde_aunque_redis_este_caido(cliente, apagar_redis):
    apagar_redis()
    assert cliente.get("/api/v1/regions?format=json").status_code == 200
    assert cliente.get("/api/v1/regions/39").status_code == 200


ESTADO = {"id": 1, "code": "19", "name": "Nuevo Leon", "population": 5784442,
          "population_60plus": 654050}


@pytest.fixture
def base_estado(monkeypatch):
    from microservicios.regiones import rutas
    base = {"estado": dict(ESTADO), "correccion": None, "consultas": []}

    def query(sql, params=(), one=False):
        base["consultas"].append((" ".join(sql.split()), params))
        return base["estado"] if "FROM regions" in sql else base["correccion"]
    monkeypatch.setattr(rutas, "query", query)
    return base


def test_estado_con_su_fuente_derivada(cliente, base_estado):
    r = cliente.get("/api/v1/regions/state?format=json")
    assert r.status_code == 200
    assert r.get_json() == {"id": 1, "code": "19", "nombre": "Nuevo Leon", "poblacion": 5784442,
                            "poblacion_60": 654050, "fuente_poblacion": {"tipo": "agregado"},
                            "fuente_poblacion_60": {"tipo": "derivado",
                                                    "fuente": "Grupos 60-79 y 80+ del Censo 2020"}}
    assert base_estado["consultas"][0][1] == ("19",) and base_estado["consultas"][1][1] == ("1",)
    assert ET.fromstring(cliente.get("/api/v1/regions/state").data).tag == "estado"


def test_estado_con_una_correccion_manual_del_60(cliente, base_estado):
    base_estado["correccion"] = {"motivo": "Conteo rápido 2025", "fecha": "2026-11-10T10:00:00+00:00",
                                 "por": "Admin"}
    fuente = cliente.get("/api/v1/regions/state?format=json").get_json()["fuente_poblacion_60"]
    assert fuente == {"tipo": "manual", "motivo": "Conteo rápido 2025",
                      "fecha": "2026-11-10T10:00:00+00:00", "por": "Admin"}
    base_estado["correccion"] = {"motivo": None, "fecha": "2026-11-10T10:00:00+00:00", "por": "Admin"}
    fuente = cliente.get("/api/v1/regions/state?format=json").get_json()["fuente_poblacion_60"]
    assert fuente["tipo"] == "censal"


def test_estado_inexistente_es_404_y_no_choca_con_el_municipio(cliente, base_estado):
    assert cliente.get("/api/v1/regions/39?format=json").get_json()["population"] == 1142994
    base_estado["estado"] = None
    r = cliente.get("/api/v1/regions/state?format=json")
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"


def test_estado_publico_aunque_redis_este_caido(cliente, base_estado, apagar_redis):
    apagar_redis()
    assert cliente.get("/api/v1/regions/state?format=json").status_code == 200
    assert cliente.post("/api/v1/regions/state?format=json", json={}).status_code == 405


def test_el_catalogo_publico_limita_por_ip(cliente, monkeypatch):
    monkeypatch.setenv("LIMITE_NORMAL", "2/60")
    estados = [cliente.get("/api/v1/regions").status_code for _ in range(3)]
    assert estados[:2] == [200, 200] and estados[2] == 429
    assert [cliente.get("/api/v1/regions/39").status_code for _ in range(3)] == [200, 200, 429]
