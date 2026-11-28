from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import xmlschema

from epidemia_comun import mongo
from microservicios.resultados import datos as consultas_sql, rutas, serie as series
from procesamiento.motor import AVISO_SIMULACION
from procesamiento.motores import IMPLEMENTADOS

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
            "disease_id": 1, "region_id": 39,
            "disease_name": "Influenza A", "region_name": "Monterrey", "region_population": 1142994,
            "seed": 982314,
            "population_size": 200000, "horizon_days": 120, "requested_by": 7,
            "finished_at": datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc)}


CORRIDAS = {42: corrida(42, "completado"), 43: corrida(43, "ejecutando"),
            44: corrida(44, "completado"), 45: corrida(45, "completado")}
GUARDADO = {"engine_version": "seir-ref-0.1", "scenario_checksum": "a" * 64,
            "resumen": RESUMEN, "trazabilidad": TRAZA}


def guarda_serie(run, motor, serie):
    # Lo que escribe el simulador, según docs/contratos/series_corridas/.
    mongo.coleccion("series_corridas").insert_many([
        dict(fila, run_id=run["id"], batch_id=run["batch_id"], scenario_id=run["scenario_id"],
             scenario_version_id=run["scenario_version_id"], motor=motor,
             engine_version="seir-ref-0.1", semilla=run["seed"], version_esquema=1)
        for fila in serie])


@pytest.fixture
def consultas(monkeypatch):
    registro = []

    def get_run(run_id):
        registro.append(run_id)
        return dict(CORRIDAS[run_id]) if run_id in CORRIDAS else None

    # 44 no tiene resumen; 45 tiene resumen pero su serie no llegó a MongoDB.
    def get_resultado_run(run_id):
        return dict(GUARDADO, run_id=run_id) if run_id in (42, 45) else None

    monkeypatch.setattr(consultas_sql, "get_run", get_run)
    monkeypatch.setattr(consultas_sql, "get_resultado_run", get_resultado_run)
    return registro


@pytest.fixture
def cliente(crear_cliente, consultas, mongo_falso):
    run = dict(CORRIDAS[42], batch_id=5)
    guarda_serie(run, "seir-ref", SERIE)
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
    # D39: sin calibración, la corrida es exploratoria aunque el modelo esté verificado.
    assert datos["categoria"]["categoria"] == "exploratoria"
    assert datos["categoria"]["modelo_verificado"] is True


@pytest.mark.parametrize("version, motor", [("abm-ref-0.1", "abm-ref"),
                                            ("python-ref-0.1", "seir-ref"),
                                            ("otro-9.9", None)])
def test_las_simplificaciones_son_las_del_motor_que_corrio(cliente, token, monkeypatch, version,
                                                           motor):
    guardado = dict(GUARDADO, run_id=42, engine_version=version)
    monkeypatch.setattr(consultas_sql, "get_resultado_run", lambda run_id: dict(guardado))
    datos = cliente.get("/api/v1/runs/42/results?format=json", headers=token()).get_json()
    esperado = list(IMPLEMENTADOS[motor].simplificaciones) if motor else []
    assert datos["engine_version"] == version and datos["simplificaciones"] == esperado


def test_la_escala_de_d6_lleva_los_conteos_a_habitantes(cliente, token):
    """200 000 agentes por los 1 142 994 habitantes de Monterrey: cada uno representa 5.71."""
    escala = cliente.get("/api/v1/runs/42/results?format=json", headers=token()).get_json()["escala"]
    assert (escala["agentes"], escala["habitantes"], escala["factor"]) == (200000, 1142994, 5.715)
    assert escala["avisos"] == []
    assert escala["representados"]["fallecimientos"] == round(RESUMEN["fallecimientos"] * 5.71497)
    assert "tasa_ataque" not in escala["representados"]


def test_curvas_e_indicadores_con_aviso(cliente, token):
    curvas = cliente.get("/api/v1/runs/42/curves?format=json", headers=token()).get_json()
    assert curvas.pop("categoria")["categoria"] == "exploratoria"
    assert curvas == {"aviso": AVISO_SIMULACION, "run_id": 42, "serie": SERIE}
    indicadores = cliente.get("/api/v1/runs/42/indicators?format=json", headers=token()).get_json()
    assert indicadores.pop("categoria")["categoria"] == "exploratoria"
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


def test_sin_serie_en_mongodb_es_404_pero_el_resumen_responde(cliente, token):
    for ruta in ("results", "curves"):
        r = cliente.get("/api/v1/runs/45/%s?format=json" % ruta, headers=token())
        assert r.status_code == 404 and "serie" in r.get_json()["detail"]
    assert cliente.get("/api/v1/runs/45/indicators", headers=token()).status_code == 200


def test_mongodb_caido_solo_tumba_lo_que_lleva_la_serie(cliente, token, apagar_mongo):
    apagar_mongo()
    for ruta in ("results", "curves"):
        r = cliente.get("/api/v1/runs/42/%s?format=json" % ruta, headers=token())
        assert r.status_code == 503 and r.get_json()["codigo"] == "SERVICIO_NO_DISPONIBLE"
    indicadores = cliente.get("/api/v1/runs/42/indicators?format=json", headers=token())
    assert indicadores.status_code == 200 and indicadores.get_json()["resumen"] == RESUMEN


def test_la_serie_no_se_cachea_vacia(cliente, token, mongo_falso):
    assert cliente.get("/api/v1/runs/45/curves", headers=token()).status_code == 404
    guarda_serie(dict(CORRIDAS[45], batch_id=6), "seir-ref", SERIE)
    curvas = cliente.get("/api/v1/runs/45/curves?format=json", headers=token()).get_json()
    assert curvas["serie"] == SERIE


BANDA = [{"dia": 0, "corridas": 3, "p5": 100, "p50": 100, "p95": 100},
         {"dia": 1, "corridas": 3, "p5": 90.0, "p50": 107.0, "p95": 125.0}]


@pytest.fixture
def banda(monkeypatch):
    llamadas = []

    def calcular(version, motor, campo="casos_activos", run_ids=None):
        llamadas.append((version, motor, campo, run_ids))
        return list(BANDA)

    monkeypatch.setattr(series, "banda", calcular)
    monkeypatch.setattr(series, "con_serie", lambda v, m, ids: sorted(ids))
    monkeypatch.setattr(consultas_sql, "get_run_ids_completados", lambda v, e: [40, 41, 42])
    return llamadas


@pytest.mark.parametrize("rol", rutas.ROLES)
def test_banda_de_las_replicas_de_la_version(cliente, token, banda, rol):
    datos = cliente.get("/api/v1/runs/42/band?format=json", headers=token((rol,))).get_json()
    assert datos["aviso"] == AVISO_SIMULACION and datos["categoria"]["categoria"] == "exploratoria"
    assert (datos["run_id"], datos["scenario_version_id"], datos["motor"], datos["campo"],
            datos["replicas"]) == (42, 11, "seir-ref", "casos_activos", 3)
    assert datos["banda"] == BANDA
    assert banda == [(11, "seir-ref", "casos_activos", [40, 41, 42])]


def test_replicas_son_solo_las_corridas_con_serie_en_mongodb(cliente, token, monkeypatch):
    run = dict(CORRIDAS[42], batch_id=5)
    guarda_serie(dict(run, id=40), "seir-ref", SERIE)
    guarda_serie(dict(run, id=99), "abm-ref", SERIE)
    usadas = []
    monkeypatch.setattr(series, "banda", lambda v, m, campo, ids: usadas.append(ids) or list(BANDA))
    monkeypatch.setattr(consultas_sql, "get_run_ids_completados", lambda v, e: [40, 41, 42, 43, 44])
    datos = cliente.get("/api/v1/runs/42/band?format=json", headers=token()).get_json()
    assert datos["replicas"] == 2 and usadas == [[40, 42]]


def test_banda_de_otro_compartimento_y_campo_invalido(cliente, token, banda):
    assert cliente.get("/api/v1/runs/42/band?campo=H&format=json", headers=token()).get_json()["campo"] == "H"
    r = cliente.get("/api/v1/runs/42/band?campo=dia", headers=token())
    assert r.status_code == 422 and r.mimetype == "application/problem+xml"
    assert cliente.get("/api/v1/runs/42/band?campo=x", headers=token()).status_code == 422


def test_banda_sale_de_la_cache_y_se_recalcula_con_otra_replica(cliente, token, banda, monkeypatch):
    for _ in range(2):
        assert cliente.get("/api/v1/runs/42/band", headers=token()).status_code == 200
    assert len(banda) == 1
    monkeypatch.setattr(consultas_sql, "get_run_ids_completados", lambda v, e: [40, 41, 42, 46])
    cliente.get("/api/v1/runs/42/band", headers=token())
    assert len(banda) == 2


def test_banda_sin_series_es_404_y_sin_completar_es_409(cliente, token, banda, monkeypatch):
    assert cliente.get("/api/v1/runs/43/band", headers=token()).status_code == 409
    monkeypatch.setattr(series, "banda", lambda *a, **k: [])
    assert cliente.get("/api/v1/runs/42/band", headers=token()).status_code == 404


def test_banda_con_mongodb_caido_es_503(cliente, token, banda, monkeypatch):
    def cae(*a, **k):
        from pymongo.errors import ServerSelectionTimeoutError
        raise ServerSelectionTimeoutError("apagado")

    monkeypatch.setattr(series, "banda", cae)
    r = cliente.get("/api/v1/runs/42/band?format=json", headers=token())
    assert r.status_code == 503 and r.get_json()["codigo"] == "SERVICIO_NO_DISPONIBLE"


def test_banda_sin_token_o_con_capturista(cliente, token):
    assert cliente.get("/api/v1/runs/42/band").status_code == 401
    assert cliente.get("/api/v1/runs/42/band", headers=token(("CAPTURISTA",))).status_code == 403


def test_banda_en_xml(cliente, token, banda):
    raiz = ET.fromstring(cliente.get("/api/v1/runs/42/band", headers=token()).data)
    assert raiz.tag == "banda"
    assert [p.findtext("p95") for p in raiz.findall("banda/punto")] == ["100", "125.0"]


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


@pytest.mark.parametrize("rol", ["INVESTIGADOR", "AUTORIDAD_SANITARIA"])
def test_los_perfiles_de_lectura_ven_resultados(cliente, token, rol):
    assert cliente.get("/api/v1/runs/42/indicators?format=json", headers=token((rol,))).status_code == 200


def test_el_alcance_se_revisa_aunque_la_corrida_este_en_cache(cliente, token, alcance_falso):
    # La región de la corrida de las pruebas es 39.
    ruta = "/api/v1/runs/42/%s?format=json"
    assert cliente.get(ruta % "results", headers=token()).status_code == 200
    alcance_falso["regiones"] = [10]
    for parte in ("results", "curves", "indicators", "band"):
        r = cliente.get(ruta % parte, headers=token())
        assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE", parte
    alcance_falso["regiones"] = [39]
    assert cliente.get(ruta % "results", headers=token()).status_code == 200
    assert "region_id" not in cliente.get(ruta % "results", headers=token()).get_json()
