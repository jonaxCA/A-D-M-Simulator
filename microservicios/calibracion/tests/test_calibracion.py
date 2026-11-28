import copy
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import xmlschema

from epidemia_comun.redis_compartido import RedisNoDisponible
from microservicios.calibracion import datos, rutas
from procesamiento import contrato

XSD = xmlschema.XMLSchema(str(Path(__file__).resolve().parents[3]
                              / "docs/contratos/calibracion/calibracion.xsd"))
REGION = 1
SEMANAS = 9
JSON = {"Accept": "application/json"}
CREADA = datetime(2026, 11, 23, 18, 0, tzinfo=timezone.utc)


# Como diseases.default_params de COVID-19 (017 y 020), con las fuentes abreviadas.
ENFERMEDAD = {
    "r0": {"valor": 2.87, "fuente": "Billah et al. 2020", "supuesto": False},
    "incubacion_dias": {"valor": 5.1, "fuente": "Lauer et al. 2020", "supuesto": False},
    "infeccioso_dias": {"valor": 9.0, "fuente": "Supuesto del equipo", "supuesto": True},
    "dias_hospitalizacion": {"valor": 8.0, "fuente": "Supuesto del equipo", "supuesto": True},
    "tasa_hospitalizacion": {"valor": 0.029, "fuente": "Salje et al. 2020", "supuesto": False},
    "letalidad": {"valor": 0.005, "fuente": "Salje et al. 2020", "supuesto": False},
    "letalidad_por_edad": {"valor": {"0-19": 0.000043, "20-39": 0.00056, "40-59": 0.00346,
                                     "60-79": 0.0273, "80+": 0.078},
                           "fuente": "Derivado de Verity et al. 2020", "supuesto": True},
}


def enfermedad():
    return copy.deepcopy(ENFERMEDAD)


def conjunto(**cambios):
    fila = {"id": 1, "code": "COVID19_NL_2020_SINTOMAS", "version": 1, "name": "Serie",
            "disease_id": 1, "region_id": REGION, "metric": "casos_confirmados", "period": "semana",
            "source": "DGE", "license": "Datos abiertos", "cutoff_date": date(2021, 10, 31),
            "sha256": "6" * 64, "disease_code": "SARS_COV_2_ANCESTRAL", "disease_name": "COVID-19",
            "default_params": enfermedad(), "disease_active": True, "region_code": "19",
            "region_name": "Nuevo León"}
    fila.update(cambios)
    return fila


def puntos(n=SEMANAS):
    return [{"inicio": str(date(2020, 3, 1) + timedelta(weeks=w)), "valor": 7 * (w + 1)}
            for w in range(n)]


RESULTADO = {
    "metodo": "abc-rechazo", "version_metodo": "calibracion-0.1", "motor": "seir-ref",
    "engine_version": "seir-ref-0.1",
    "configuracion": {"muestras": 5000, "semillas": [1, 2, 3], "cuantil": 0.01, "semilla_muestreo": 1,
                      "rangos": {}, "desfase_dias": 5, "c0": 7.0, "dias": 63,
                      "ventanas": {"calibracion": {"desde": "2020-03-01", "hasta": "2020-04-12", "semanas": 6},
                                   "validacion": {"desde": "2020-04-19", "hasta": "2020-04-26", "semanas": 3}},
                      "intervenciones": [{"tipo": "CIERRE_ESCUELAS", "desde": "2020-03-23", "reduccion": 1.0,
                                          "fuente": "SEP", "dia_inicio": 22},
                                         {"tipo": "CIERRE_TRABAJO", "desde": "2020-03-30", "reduccion": "phi",
                                          "fuente": "Salud", "dia_inicio": 29}]},
    "parametros": [{"nombre": "r0", "mediana": 2.5, "p5": 2.1, "p95": 2.9, "minimo": 1.0, "maximo": 5.0},
                   {"nombre": "rho", "mediana": 0.2, "p5": 0.1, "p95": 0.4, "minimo": 0.01, "maximo": 1.0},
                   {"nombre": "phi", "mediana": 0.6, "p5": 0.4, "p95": 0.8, "minimo": 0.0, "maximo": 1.0}],
    "perdida": {"minima": 0.5, "umbral": 1.5, "aceptadas": 50, "corridas": 15000},
    "aceptadas": [],
    "semanas": [{"inicio": "2020-03-01", "observado": 7, "mediana": 7.0, "p5": 6.0, "p95": 8.0,
                 "ventana": "calibracion"}],
    "metricas": {"calibracion": {"semanas": 6, "rmse": 1.0, "r2": 0.9, "cobertura": 1.0},
                 "validacion": {"semanas": 3, "rmse": 2.0, "r2": 0.8, "cobertura": 0.67}},
    "huella_configuracion": "a" * 64,
}


class Base:
    def __init__(self):
        self.filas, self.canceladas = {}, []

    def crear(self, dataset_id, motor, engine_version, metodo, version_metodo, config, user_id, *, contexto):
        cal_id = len(self.filas) + 1
        self.filas[cal_id] = {
            "id": cal_id, "dataset_id": dataset_id, "engine": motor, "engine_version": engine_version,
            "method": metodo, "method_version": version_metodo, "config": config, "status": "encolado",
            "attempts": 0, "progress": 0, "error": None, "requested_by": user_id, "created_at": CREADA,
            "started_at": None, "finished_at": None, "dataset_code": "COVID19_NL_2020_SINTOMAS",
            "dataset_version": 1, "disease_id": 1, "region_id": REGION, "requested_by_username": "ana",
            "result": None}
        return cal_id

    def get(self, cal_id, con_resultado=False):
        fila = self.filas.get(cal_id)
        return dict(fila) if fila else None

    def listar(self, limite, estado=None, dataset_id=None, regiones=None):
        self.filtros = (limite, estado, dataset_id, regiones)
        return [dict(f) for f in self.filas.values() if regiones is None or f["region_id"] in regiones]

    def cancelar(self, cal_id, *, contexto):
        self.canceladas.append(cal_id)
        fila = self.filas[cal_id]
        if fila["status"] not in ("encolado", "ejecutando"):
            return False
        fila["status"] = "cancelado"
        return True

    def estado(self, cal_id):
        return self.filas[cal_id]["status"]

    def completa(self, cal_id):
        self.filas[cal_id].update(status="completado", progress=100, result=copy.deepcopy(RESULTADO),
                                  finished_at=CREADA)


@pytest.fixture
def base(monkeypatch):
    falsa = Base()
    for nombre in ("crear", "get", "listar", "cancelar", "estado"):
        monkeypatch.setattr(datos, nombre, getattr(falsa, nombre))
    falsa.conjuntos = {1: conjunto()}
    falsa.series = {1: puntos()}
    monkeypatch.setattr(datos, "conjunto", lambda i: copy.deepcopy(falsa.conjuntos.get(i)))
    monkeypatch.setattr(datos, "puntos", lambda i: list(falsa.series[i]))
    monkeypatch.setattr(datos, "poblacion", lambda r: (
        {g: n * 100 for g, n in contrato.ESCENARIO_EJEMPLO["poblacion"].items()}, 0))
    return falsa


@pytest.fixture
def cliente(crear_cliente, base):
    return crear_cliente("calibracion")


def lanzar(cliente, cabeceras, **cuerpo):
    return cliente.post("/api/v1/calibrations?format=json", json=dict({"dataset_id": 1}, **cuerpo),
                        headers=cabeceras)


def test_sin_token_es_401(cliente):
    assert lanzar(cliente, {}).status_code == 401
    assert cliente.get("/api/v1/calibrations/state").status_code == 401


@pytest.mark.parametrize("rol", ["ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR"])
def test_lanzan_los_roles_de_calibrations_run(cliente, token, redis_falso, rol):
    r = lanzar(cliente, token((rol,)), samples=200, seeds=1, quantile=0.05)
    assert r.status_code == 202
    cuerpo = r.get_json()
    assert cuerpo["status"] == "encolado"
    assert cuerpo["config"] == {"muestras": 200, "semillas": 1, "cuantil": 0.05, "semilla_muestreo": 1}
    assert (cuerpo["engine"], cuerpo["method"], cuerpo["method_version"]) == (
        "seir-ref", "abc-rechazo", "calibracion-0.1")
    assert json.loads(redis_falso.lrange("queue:calibraciones", 0, -1)[0]) == {"id": cuerpo["id"]}


@pytest.mark.parametrize("rol", ["INVESTIGADOR", "AUTORIDAD_SANITARIA", "CAPTURISTA"])
def test_los_demas_no_lanzan(cliente, token, rol):
    assert lanzar(cliente, token((rol,))).status_code == 403


def test_lanzar_revisa_el_cuerpo(cliente, token, base):
    cabeceras = token()
    assert lanzar(cliente, cabeceras, engine="abm-ref").status_code == 422
    assert lanzar(cliente, cabeceras, samples=20000).status_code == 422
    assert lanzar(cliente, cabeceras, samples=100, quantile=0.05).status_code == 422
    assert lanzar(cliente, cabeceras, seeds="dos").status_code == 422
    assert lanzar(cliente, cabeceras, otro=1).status_code == 422
    assert lanzar(cliente, cabeceras, dataset_id=9).status_code == 404
    base.conjuntos[2] = conjunto(id=2, period="dia")
    base.series[2] = puntos()
    r = lanzar(cliente, cabeceras, dataset_id=2)
    assert r.status_code == 422 and "semanales" in r.get_json()["detail"]
    base.conjuntos[3] = conjunto(id=3)
    base.series[3] = puntos(4)
    assert lanzar(cliente, cabeceras, dataset_id=3).status_code == 422
    assert base.filas == {}


def test_lanzar_acepta_xml(cliente, token):
    r = cliente.post("/api/v1/calibrations", headers=token(), content_type="application/xml",
                     data="<solicitud><dataset_id>1</dataset_id><samples>300</samples>"
                          "<quantile>0.05</quantile></solicitud>")
    assert r.status_code == 202
    XSD.validate(r.data.decode("utf-8"))


def test_fuera_del_alcance_es_403(cliente, token, alcance_falso, base):
    alcance_falso["regiones"] = [99]
    assert lanzar(cliente, token()).status_code == 403
    assert base.filas == {}


def test_sin_redis_la_calibracion_se_cancela(cliente, token, base, monkeypatch):
    def sin_redis(*_):
        raise RedisNoDisponible("cola_encolar")
    monkeypatch.setattr(rutas.cola, "encolar", sin_redis)
    assert lanzar(cliente, token()).status_code == 503
    assert base.canceladas == [1]
    assert base.filas[1]["status"] == "cancelado"


def test_listar_filtra_por_alcance(cliente, token, base, alcance_falso):
    lanzar(cliente, token())
    alcance_falso["regiones"] = [REGION]
    r = cliente.get("/api/v1/calibrations?format=json&status=encolado&dataset=1",
                    headers=token(("INVESTIGADOR",)))
    assert r.status_code == 200
    assert r.get_json()["total"] == 1
    assert base.filtros == (20, "encolado", 1, {REGION})
    assert cliente.get("/api/v1/calibrations?status=otro", headers=token()).status_code == 422
    assert cliente.get("/api/v1/calibrations", headers=token(("CAPTURISTA",))).status_code == 403
    XSD.validate(cliente.get("/api/v1/calibrations", headers=token()).data.decode("utf-8"))


def test_el_detalle_trae_el_avance_en_vivo(cliente, token, base, redis_falso):
    cal_id = lanzar(cliente, token()).get_json()["id"]
    redis_falso.set("calibration:%d:progress" % cal_id, 40)
    r = cliente.get("/api/v1/calibrations/%d?format=json" % cal_id, headers=token(("AUTORIDAD_SANITARIA",)))
    assert r.status_code == 200
    assert (r.get_json()["progress"], r.get_json()["terminal"]) == (40, False)
    assert "estimados" not in r.get_json()
    assert cliente.get("/api/v1/calibrations/99", headers=token()).status_code == 404


def test_el_detalle_de_una_completada(cliente, token, base):
    cal_id = lanzar(cliente, token()).get_json()["id"]
    base.completa(cal_id)
    r = cliente.get("/api/v1/calibrations/%d" % cal_id, headers=token())
    XSD.validate(r.data.decode("utf-8"))
    cuerpo = cliente.get("/api/v1/calibrations/%d" % cal_id, headers=dict(token(), **JSON)).get_json()
    assert cuerpo["terminal"] is True
    assert cuerpo["estimados"][0]["nombre"] == "r0"
    assert cuerpo["metricas"]["validacion"]["cobertura"] == 0.67


def test_cancelar(cliente, token, base):
    cal_id = lanzar(cliente, token()).get_json()["id"]
    assert cliente.post("/api/v1/calibrations/%d/cancel" % cal_id,
                        headers=token(("INVESTIGADOR",))).status_code == 403
    r = cliente.post("/api/v1/calibrations/%d/cancel?format=json" % cal_id, headers=token())
    assert r.status_code == 200 and r.get_json()["status"] == "cancelado"
    assert cliente.post("/api/v1/calibrations/%d/cancel" % cal_id, headers=token()).status_code == 409


def test_el_ajuste_y_el_escenario_esperan_a_que_termine(cliente, token, base):
    cal_id = lanzar(cliente, token()).get_json()["id"]
    assert cliente.get("/api/v1/calibrations/%d/fit" % cal_id, headers=token()).status_code == 409
    assert cliente.get("/api/v1/calibrations/%d/scenario" % cal_id, headers=token()).status_code == 409
    base.completa(cal_id)
    ajuste = cliente.get("/api/v1/calibrations/%d/fit" % cal_id, headers=token())
    assert ajuste.status_code == 200
    XSD.validate(ajuste.data.decode("utf-8"))
    escenario = cliente.get("/api/v1/calibrations/%d/scenario" % cal_id, headers=token())
    XSD.validate(escenario.data.decode("utf-8"))
    cuerpo = cliente.get("/api/v1/calibrations/%d/scenario" % cal_id,
                         headers=dict(token(), **JSON)).get_json()
    r0 = cuerpo["param_overrides"]["r0"]
    assert (r0["valor"], r0["supuesto"], r0["intervalo"]) == (
        2.5, False, {"min": 2.1, "max": 2.9, "tipo": "rango"})
    assert "Calibración n.º %d" % cal_id in r0["fuente"]
    assert cuerpo["escenario"]["initial_infected"] == 35
    assert cuerpo["escenario"]["stratify"] is True
    assert [iv["params"]["reduccion"] for iv in cuerpo["intervenciones"]] == [1.0, 0.6]


def test_evaluar_un_juego_de_parametros(cliente, token):
    r = cliente.get("/api/v1/calibrations/evaluate?format=json&dataset=1&r0=2.5&rho=0.3&phi=0.5",
                    headers=token(("INVESTIGADOR",)))
    assert r.status_code == 200
    cuerpo = r.get_json()
    assert cuerpo["semillas"] == [1, 2, 3, 4, 5]
    assert len(cuerpo["semanas"]) == SEMANAS
    assert cuerpo["ventanas"]["validacion"]["semanas"] == 3
    XSD.validate(cliente.get("/api/v1/calibrations/evaluate?dataset=1&r0=2.5&rho=0.3&phi=0.5",
                             headers=token()).data.decode("utf-8"))
    assert cliente.get("/api/v1/calibrations/evaluate?dataset=1&r0=7&rho=0.3&phi=0.5",
                       headers=token()).status_code == 422
    assert cliente.get("/api/v1/calibrations/evaluate?dataset=1&r0=2&rho=x&phi=0.5",
                       headers=token()).status_code == 422
    assert cliente.get("/api/v1/calibrations/evaluate?dataset=1&r0=2.5&rho=0.3&phi=0.5",
                       headers=token(("CAPTURISTA",))).status_code == 403


def test_el_estado_de_los_modelos(cliente, token):
    r = cliente.get("/api/v1/calibrations/state?format=json&engine=seir-ref-0.1&disease=1&region=1",
                    headers=token(("INVESTIGADOR",)))
    assert r.status_code == 200
    cuerpo = r.get_json()
    assert cuerpo["disponible"] is True
    assert [m["engine_version"] for m in cuerpo["modelos"]] == ["seir-ref-0.1"]
    assert cuerpo["modelos"][0]["categoria"] == "exploratoria"
    XSD.validate(cliente.get("/api/v1/calibrations/state", headers=token()).data.decode("utf-8"))
    assert cliente.get("/api/v1/calibrations/state?engine=otro", headers=token()).status_code == 422
    assert cliente.get("/api/v1/calibrations/state", headers=token(("CAPTURISTA",))).status_code == 403
