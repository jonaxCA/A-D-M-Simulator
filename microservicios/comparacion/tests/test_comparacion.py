from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import xmlschema

from backend_web import queries
from microservicios.comparacion import rutas
from procesamiento.motor import AVISO_SIMULACION, simular
from procesamiento.tests.test_motor import escenario

RAIZ = Path(__file__).resolve().parents[3]


def corrida(id_, fallecimientos):
    return {"id": id_, "scenario_id": 3, "version_number": 1, "scenario_name": "Escenario %d" % id_,
            "serie": [{"dia": 0, "casos_activos": 100, "H": 0, "D": 0},
                      {"dia": 1, "casos_activos": 120, "H": 1, "D": 0}],
            "fallecimientos": fallecimientos, "pico_casos_activos": 500, "dia_pico": 40,
            "tasa_ataque": Decimal("0.425")}


# Las únicas corridas completadas de la base simulada.
COMPLETADAS = {12: corrida(12, 100), 15: corrida(15, 61)}


@pytest.fixture
def pedidas(monkeypatch):
    registro = []

    def corridas_para_comparar(run_ids):
        registro.append(list(run_ids))
        return [COMPLETADAS[i] for i in run_ids if i in COMPLETADAS]

    monkeypatch.setattr(queries, "get_corridas_para_comparar", corridas_para_comparar)
    return registro


@pytest.fixture
def cliente(crear_cliente, pedidas):
    return crear_cliente("comparacion")


def test_sin_token_es_401(cliente):
    assert cliente.get("/api/v1/comparisons?runs=12,15").status_code == 401


def test_capturista_no_compara(cliente, token):
    r = cliente.get("/api/v1/comparisons?runs=12,15&format=json", headers=token(("CAPTURISTA",)))
    assert r.status_code == 403


@pytest.mark.parametrize("rol", rutas.ROLES)
def test_compara_en_el_orden_pedido_sin_repetidas(cliente, token, pedidas, rol):
    r = cliente.get("/api/v1/comparisons?runs=15,12,15&format=json", headers=token((rol,)))
    assert r.status_code == 200
    datos = r.get_json()
    assert pedidas == [[15, 12]]
    assert [c["id"] for c in datos["corridas"]] == [15, 12]
    assert datos["aviso"] == AVISO_SIMULACION
    assert datos["corridas"][0]["tasa_ataque"] == 0.425
    assert datos["corridas"][0]["serie"][1] == {"dia": 1, "casos_activos": 120, "H": 1, "D": 0}


def test_xml_por_omision(cliente, token):
    r = cliente.get("/api/v1/comparisons?runs=12,15", headers=token())
    assert r.mimetype == "application/xml"
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "comparacion"
    corridas = raiz.findall("corridas/corrida")
    assert [c.findtext("id") for c in corridas] == ["12", "15"]
    assert [p.findtext("casos_activos") for p in corridas[0].findall("serie/punto")] == ["100", "120"]


def test_xml_con_la_serie_real_del_motor_valida_contra_el_xsd(cliente, token, monkeypatch):
    serie = simular(escenario(dias=5), 1)["serie"]
    for corrida_ in COMPLETADAS.values():
        monkeypatch.setitem(corrida_, "serie", serie)
    r = cliente.get("/api/v1/comparisons?runs=12,15", headers=token())
    assert r.status_code == 200
    xmlschema.XMLSchema(str(RAIZ / "docs/contratos/comparacion/comparacion.xsd")).validate(
        r.data.decode("utf-8"))


@pytest.mark.parametrize("runs", [None, "", "12", "12,12", "12,abc", "12,0", "12,-3", "12,,15",
                                  ",".join(str(i) for i in range(1, rutas.MAXIMO + 2))])
def test_runs_invalido_es_422_sin_consultar(cliente, token, pedidas, runs):
    ruta = "/api/v1/comparisons?format=json" + ("" if runs is None else "&runs=" + runs)
    r = cliente.get(ruta, headers=token())
    assert r.status_code == 422
    assert r.get_json()["codigo"] == "DATOS_INVALIDOS"
    assert pedidas == []


def test_inexistentes_o_sin_terminar_es_404_con_sus_ids(cliente, token):
    r = cliente.get("/api/v1/comparisons?runs=12,99,15,98&format=json", headers=token())
    assert r.status_code == 404
    assert r.get_json()["codigo"] == "NO_ENCONTRADO"
    assert "99, 98" in r.get_json()["detail"]


def test_acepta_hasta_el_maximo(cliente, token, pedidas):
    runs = ",".join(str(i) for i in range(1, rutas.MAXIMO + 1))
    cliente.get("/api/v1/comparisons?format=json&runs=" + runs, headers=token())
    assert len(pedidas[0]) == rutas.MAXIMO


def test_redis_caido_es_503(cliente, token, apagar_redis):
    encabezados = token()
    apagar_redis()
    assert cliente.get("/api/v1/comparisons?runs=12,15", headers=encabezados).status_code == 503


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (RAIZ / "docs/contratos/comparacion/openapi.json").read_bytes()
