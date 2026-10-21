from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import xmlschema

from backend_web import queries
from microservicios.resultados import rutas
from procesamiento.motor import AVISO_SIMULACION

RAIZ = Path(__file__).resolve().parents[3]
XSD = RAIZ / "docs/contratos/resultados/resultado.xsd"

RESUMEN = {"casos_acumulados": 88, "casos_activos_final": 61, "pico_casos_activos": 61,
           "dia_pico": 3, "pico_nuevos_casos": 14, "dia_pico_nuevos_casos": 1,
           "hospitalizaciones": 0, "pico_hospitalizados": 0, "dia_pico_hospitalizados": 0,
           "fallecimientos": 0, "tasa_ataque": 0.00044, "vacunados_protegidos": 0,
           "dosis_aplicadas": 0,
           "desglose_por_grupo": [{"grupo": "0-19", "poblacion": 60000, "casos": 30,
                                   "fallecimientos": 0, "vacunados_protegidos": 0,
                                   "dosis_aplicadas": 0}]}
SERIE = [{"dia": 0, "S": 199900, "E": 0, "I": 100, "R": 0, "H": 0, "D": 0, "V": 0,
          "casos_activos": 100, "nuevos_casos": 0, "nuevas_hospitalizaciones": 0,
          "nuevas_defunciones": 0, "dosis_aplicadas": 0}]
TRAZA = [{"parametro": "r0", "valor": 1.8, "fuente": "Biggerstaff et al. 2014", "estado": "con_fuente"},
         {"parametro": "letalidad_por_edad", "valor": {"0-19": 3.1e-05, "60+": 0.004},
          "fuente": None, "estado": "supuesto"}]


def corrida(run_id, status):
    return {"id": run_id, "status": status, "scenario_version_id": 11, "scenario_id": 3,
            "version_number": 2, "scenario_name": "Ola Influenza ZMM",
            "disease_name": "Influenza A", "region_name": "Monterrey", "seed": 982314,
            "population_size": 200000, "horizon_days": 120, "requested_by": 7,
            "finished_at": datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc)}


CORRIDAS = {42: corrida(42, "completado"), 43: corrida(43, "ejecutando"),
            44: corrida(44, "completado")}


@pytest.fixture
def consultas(monkeypatch):
    registro = []

    def get_run(run_id):
        registro.append(run_id)
        return dict(CORRIDAS[run_id]) if run_id in CORRIDAS else None

    def get_resultado_run(run_id):
        if run_id != 42:
            return None
        return {"run_id": 42, "engine_version": "python-ref-0.1", "scenario_checksum": "a" * 64,
                "resumen": RESUMEN, "serie": SERIE, "trazabilidad": TRAZA}

    monkeypatch.setattr(queries, "get_run", get_run)
    monkeypatch.setattr(queries, "get_resultado_run", get_resultado_run)
    return registro


@pytest.fixture
def cliente(crear_cliente, consultas):
    return crear_cliente("resultados")


def test_sin_token_es_401(cliente):
    assert cliente.get("/api/v1/runs/42/results").status_code == 401


def test_capturista_no_ve_resultados(cliente, token):
    assert cliente.get("/api/v1/runs/42/results", headers=token(("CAPTURISTA",))).status_code == 403


@pytest.mark.parametrize("rol", rutas.ROLES)
def test_resultado_completo_con_aviso(cliente, token, rol):
    datos = cliente.get("/api/v1/runs/42/results?format=json", headers=token((rol,))).get_json()
    assert datos["aviso"] == AVISO_SIMULACION
    assert datos["simplificaciones"]
    assert datos["corrida"]["id"] == 42 and datos["corrida"]["finished_at"].startswith("2026-10-20")
    assert "requested_by" not in datos["corrida"]
    assert datos["resumen"] == RESUMEN and datos["serie"] == SERIE and datos["trazabilidad"] == TRAZA


def test_curvas_e_indicadores_con_aviso(cliente, token):
    curvas = cliente.get("/api/v1/runs/42/curves?format=json", headers=token()).get_json()
    assert curvas == {"aviso": AVISO_SIMULACION, "run_id": 42, "serie": SERIE}
    indicadores = cliente.get("/api/v1/runs/42/indicators?format=json", headers=token()).get_json()
    assert indicadores == {"aviso": AVISO_SIMULACION, "run_id": 42, "resumen": RESUMEN}


def test_la_segunda_vez_sale_de_la_cache(cliente, token, consultas):
    for ruta in ("results", "curves", "indicators"):
        assert cliente.get("/api/v1/runs/42/%s" % ruta, headers=token()).status_code == 200
    assert consultas == [42]


def test_sin_terminar_es_409_y_no_entra_a_la_cache(cliente, token, consultas):
    for _ in range(2):
        r = cliente.get("/api/v1/runs/43/results?format=json", headers=token())
        assert r.status_code == 409 and "ejecutando" in r.get_json()["detail"]
    assert consultas == [43, 43]


def test_inexistente_o_sin_resultado_es_404(cliente, token):
    assert cliente.get("/api/v1/runs/99/results", headers=token()).status_code == 404
    assert cliente.get("/api/v1/runs/44/curves", headers=token()).status_code == 404


def test_id_invalido_es_422(cliente, token):
    assert cliente.get("/api/v1/runs/abc/indicators", headers=token()).status_code == 422


def test_xml_valida_contra_el_xsd(cliente, token):
    r = cliente.get("/api/v1/runs/42/results", headers=token())
    assert r.mimetype == "application/xml"
    xmlschema.XMLSchema(str(XSD)).validate(r.data.decode("utf-8"))
    raiz = ET.fromstring(r.data)
    assert [p.findtext("casos_activos") for p in raiz.findall("serie/punto")] == ["100"]
    assert raiz.find("resumen/desglose_por_grupo/grupo_edad/grupo").text == "0-19"


def test_redis_caido_es_503(cliente, token, apagar_redis):
    cabeceras = token()
    apagar_redis()
    assert cliente.get("/api/v1/runs/42/results", headers=cabeceras).status_code == 503


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (RAIZ / "docs/contratos/resultados/openapi.json").read_bytes()
