from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import xmlschema

from epidemia_comun.errores import ErrorAPI
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


class Respuesta:
    def __init__(self, estado, datos=None):
        self.status_code, self.datos = estado, datos

    def json(self):
        return self.datos


def resultado(c):
    return {"corrida": {k: c[k] for k in ("scenario_id", "version_number", "scenario_name")},
            "serie": c["serie"],
            "resumen": {k: c[k] for k in ("fallecimientos", "pico_casos_activos", "dia_pico",
                                          "tasa_ataque")}}


@pytest.fixture
def pedidas(monkeypatch):
    registro = []

    def llamar(servicio, metodo, ruta, **kw):
        registro.append((servicio, metodo, ruta, kw["token"], kw["correlation_id"]))
        run_id = int(ruta.split("/")[4])
        if run_id in COMPLETADAS:
            return Respuesta(200, resultado(COMPLETADAS[run_id]))
        return Respuesta(409 if run_id == 98 else 404)

    monkeypatch.setattr(rutas, "llamar", llamar)
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
    assert sorted(p[:3] for p in pedidas) == [("resultados", "GET", "/api/v1/runs/12/results"),
                                              ("resultados", "GET", "/api/v1/runs/15/results")]
    assert [c["id"] for c in datos["corridas"]] == [15, 12]
    assert datos["aviso"] == AVISO_SIMULACION
    assert datos["corridas"][0]["tasa_ataque"] == 0.425
    assert datos["corridas"][0]["scenario_name"] == "Escenario 15"
    assert datos["corridas"][0]["serie"][1] == {"dia": 1, "casos_activos": 120, "H": 1, "D": 0}


def test_xml_por_omision(cliente, token):
    r = cliente.get("/api/v1/comparisons?runs=12,15", headers=token())
    assert r.mimetype == "application/xml"
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "comparacion"
    corridas = raiz.findall("corridas/corrida")
    assert [c.findtext("id") for c in corridas] == ["12", "15"]
    assert [p.findtext("casos_activos") for p in corridas[0].findall("serie/punto")] == ["100", "120"]


def test_xml_con_la_serie_real_del_motor_valida_contra_el_xsd(cliente, token, monkeypatch, pedidas):
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
    assert len(pedidas) == rutas.MAXIMO


def test_reenvia_el_token_y_la_correlacion_a_resultados(cliente, token, pedidas):
    encabezados = dict(token(), **{"X-Correlation-ID": "abc-123"})
    cliente.get("/api/v1/comparisons?runs=12,15&format=json", headers=encabezados)
    tokens = {p[3] for p in pedidas}
    assert tokens == {encabezados["Authorization"][7:]}
    assert {p[4] for p in pedidas} == {"abc-123"}


@pytest.mark.parametrize("fallo", [ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio no respondió."),
                                   Respuesta(500), Respuesta(200, {"raro": 1})])
def test_resultados_caido_o_ilegible_es_503(cliente, token, monkeypatch, fallo):
    def llamar(*a, **kw):
        if isinstance(fallo, Exception):
            raise fallo
        return fallo

    monkeypatch.setattr(rutas, "llamar", llamar)
    r = cliente.get("/api/v1/comparisons?runs=12,15&format=json", headers=token())
    assert r.status_code == 503 and r.get_json()["codigo"] == "SERVICIO_NO_DISPONIBLE"


def test_resultados_que_rechaza_la_identidad_se_propaga(cliente, token, monkeypatch):
    monkeypatch.setattr(rutas, "llamar", lambda *a, **kw: Respuesta(403))
    r = cliente.get("/api/v1/comparisons?runs=12,15&format=json", headers=token())
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"


def test_resultados_con_429_se_propaga_con_su_retry_after(cliente, token, monkeypatch):
    class Limitada(Respuesta):
        headers = {"Retry-After": "17"}

    monkeypatch.setattr(rutas, "llamar", lambda *a, **kw: Limitada(429))
    r = cliente.get("/api/v1/comparisons?runs=12,15&format=json", headers=token())
    assert r.status_code == 429 and r.get_json()["codigo"] == "LIMITE_EXCEDIDO"
    assert r.headers["Retry-After"] == "17"


def test_redis_caido_es_503(cliente, token, apagar_redis):
    encabezados = token()
    apagar_redis()
    assert cliente.get("/api/v1/comparisons?runs=12,15", headers=encabezados).status_code == 503


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (RAIZ / "docs/contratos/comparacion/openapi.json").read_bytes()
