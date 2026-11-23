import json

import pytest

from epidemia_comun.redis_compartido import RedisNoDisponible
from microservicios.calibracion import datos, trabajador
from microservicios.calibracion.tests.test_calibracion import conjunto, puntos
from procesamiento import contrato

CONFIG = {"muestras": 100, "semillas": 1, "cuantil": 0.1, "semilla_muestreo": 1}


class Base:
    def __init__(self):
        self.filas, self.bitacora = {}, []

    def agrega(self, cal_id, **cambios):
        self.filas[cal_id] = dict({"id": cal_id, "dataset_id": 1, "engine_version": "seir-ref-0.1",
                                   "config": dict(CONFIG), "status": "encolado", "attempts": 0,
                                   "requested_by": 5, "dataset_code": "COVID19_NL_2020_SINTOMAS",
                                   "dataset_version": 1, "result": None, "error": None}, **cambios)

    def get(self, cal_id, con_resultado=False):
        return dict(self.filas[cal_id]) if cal_id in self.filas else None

    def marcar_ejecutando(self, cal_id, *, contexto):
        fila = self.filas[cal_id]
        if fila["status"] != "encolado" or fila["attempts"] >= 3:
            return False
        fila.update(status="ejecutando", attempts=fila["attempts"] + 1)
        self.bitacora.append((contexto.user_id, cal_id, "ejecutando"))
        return True

    def completar(self, cal_id, resultado, *, contexto):
        if self.filas[cal_id]["status"] != "ejecutando":
            return False
        self.filas[cal_id].update(status="completado", result=resultado)
        return True

    def fallar(self, cal_id, error, *, contexto):
        self.filas[cal_id].update(status="fallido", error=error)
        return True

    def estado(self, cal_id):
        return self.filas[cal_id]["status"]

    def encoladas(self):
        return [i for i, f in self.filas.items() if f["status"] == "encolado"]

    def reencola_interrumpidas(self, engine_version, contexto_de):
        reencoladas, cerradas = [], []
        for cal_id, fila in self.filas.items():
            if fila["status"] != "ejecutando":
                continue
            if fila["attempts"] < 3 and fila["engine_version"] == engine_version:
                fila["status"] = "encolado"
                reencoladas.append(cal_id)
            else:
                fila["status"] = "fallido"
                cerradas.append(cal_id)
        return reencoladas, cerradas


@pytest.fixture
def base(monkeypatch, redis_falso):
    falsa = Base()
    for nombre in ("get", "marcar_ejecutando", "completar", "fallar", "estado", "encoladas",
                   "reencola_interrumpidas"):
        monkeypatch.setattr(datos, nombre, getattr(falsa, nombre))
    monkeypatch.setattr(datos, "conjunto", lambda i: conjunto())
    monkeypatch.setattr(datos, "puntos", lambda i: puntos())
    monkeypatch.setattr(datos, "poblacion", lambda r: (
        {g: n * 100 for g, n in contrato.ESCENARIO_EJEMPLO["poblacion"].items()}, 0))
    trabajador.pendiente.clear()
    return falsa


def test_corre_y_guarda_el_resultado(base, redis_falso):
    base.agrega(1)
    assert trabajador.procesar(json.dumps({"id": 1})) == "completado"
    resultado = base.filas[1]["result"]
    assert resultado["perdida"]["aceptadas"] == 10
    assert resultado["conjunto"] == {"id": 1, "code": "COVID19_NL_2020_SINTOMAS", "version": 1}
    assert redis_falso.get("calibration:1:progress") == "100"
    assert base.bitacora == [(5, 1, "ejecutando")]
    assert trabajador.estado["ultima"] == {"id": 1, "status": "completado"}


def test_la_misma_configuracion_reencolada_da_lo_mismo(base):
    base.agrega(1)
    base.agrega(2)
    trabajador.procesar(json.dumps({"id": 1}))
    trabajador.procesar("2")
    primero, segundo = (base.filas[i]["result"] for i in (1, 2))
    assert primero == segundo


def test_no_toma_la_que_ya_no_esta_encolada(base):
    base.agrega(1, status="cancelado")
    assert trabajador.procesar(json.dumps({"id": 1})) is None
    assert trabajador.procesar(json.dumps({"id": 9})) is None
    assert trabajador.procesar("basura") is None


def test_cancelar_a_media_corrida_la_detiene(base, monkeypatch):
    base.agrega(1, config=dict(CONFIG, muestras=600, cuantil=0.02))
    estado = base.estado
    llamadas = []

    def cancelada(cal_id):
        llamadas.append(cal_id)
        if len(llamadas) == 1:
            base.filas[cal_id]["status"] = "cancelado"
        return estado(cal_id)
    monkeypatch.setattr(datos, "estado", cancelada)
    assert trabajador.procesar(json.dumps({"id": 1})) == "cancelado"
    assert base.filas[1]["result"] is None


def test_otra_version_del_motor_falla(base):
    base.agrega(1, engine_version="seir-ref-0.0")
    assert trabajador.procesar(json.dumps({"id": 1})) == "fallido"
    assert "seir-ref-0.0" in base.filas[1]["error"]


def test_un_conjunto_que_no_sirve_falla(base, monkeypatch):
    monkeypatch.setattr(datos, "conjunto", lambda i: conjunto(period="dia"))
    base.agrega(1)
    assert trabajador.procesar(json.dumps({"id": 1})) == "fallido"
    assert "semanales" in base.filas[1]["error"]


def test_al_arrancar_reencola_lo_interrumpido(base, redis_falso):
    base.agrega(1, status="ejecutando", attempts=1)
    base.agrega(2, status="ejecutando", attempts=3)
    base.agrega(3)
    redis_falso.lpush("queue:calibraciones", json.dumps({"id": 3}))
    assert trabajador.recuperar() == ([1], [2])
    en_cola = [json.loads(x)["id"] for x in redis_falso.lrange("queue:calibraciones", 0, -1)]
    assert sorted(en_cola) == [1, 3]


def test_sin_redis_al_arrancar_reencola_despues(base, monkeypatch):
    def caido(*_):
        raise RedisNoDisponible("cola_contenidos")
    monkeypatch.setattr(trabajador.cola, "contenidos", caido)
    base.agrega(1, status="ejecutando", attempts=1)
    trabajador.recuperar()
    assert trabajador.pendiente == [True]
