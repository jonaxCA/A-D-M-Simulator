import dataclasses
import functools
import importlib
import json
import logging
import threading
from pathlib import Path

import jwt
import psycopg2
import pytest

from epidemia_comun import llaves
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.redis_compartido import RedisNoDisponible
from microservicios.simulador import datos, ejecucion, rutas, trabajador
from procesamiento import motores
from procesamiento.motores import MotorNoDisponible

RAIZ = Path(__file__).resolve().parents[3]
AJUSTES = {"JWT_SECRET_KEY": "secreto-de-pruebas-del-simulador-0123456789",
           "JWT_ISSUER": "epidemia-auth", "JWT_AUDIENCE_INTERNA": "epidemia-interno"}


FILA = {"S": 990, "E": 0, "I": 10, "R": 0, "H": 0, "D": 0, "V": 0, "casos_activos": 10,
        "nuevos_casos": 0, "nuevas_hospitalizaciones": 0, "nuevas_defunciones": 0,
        "dosis_aplicadas": 0}
RESULTADO = {"engine_version": "seir-ref-0.1", "resumen": {},
             "serie": [dict(FILA, dia=0), dict(FILA, dia=1, casos_activos=12, E=2, S=988)]}
# La de verdad, antes de que el fixture mundo la cambie.
EJECUTAR_RUN = ejecucion.ejecutar_run


class Resp:
    def __init__(self, estado=201):
        self.status_code = estado


@pytest.fixture
def mundo(monkeypatch, redis_falso, mongo_falso):
    """ejecutar_run, get_run y llamar() simulados; el avance va al Redis falso."""
    m = {"ejecutadas": [], "llamadas": [], "final": "completado", "respuesta": Resp()}

    def ejecutar_run(run_id, forzar_error=False, al_avanzar=None, guardar_serie=None,
                     descartar_serie=None):
        m["ejecutadas"].append((run_id, forzar_error))
        for porcentaje in (10, 30, 90, 100):
            al_avanzar(porcentaje)
        return m["final"]

    def llamar(servicio, metodo, ruta, **kw):
        m["llamadas"].append((servicio, metodo, ruta, kw))
        if isinstance(m["respuesta"], Exception):
            raise m["respuesta"]
        return m["respuesta"]

    monkeypatch.setattr(ejecucion, "ejecutar_run", ejecutar_run)
    monkeypatch.setattr(datos, "get_run", lambda run_id: {
        "id": run_id, "batch_id": 8, "requested_by": 5, "scenario_id": 3,
        "scenario_version_id": 11, "seed": 7, "engine_version": "seir-ref-0.1",
        "scenario_name": "Ola Influenza ZMM", "version_number": 2,
        "error_message": "Error forzado de prueba."})
    monkeypatch.setattr(trabajador, "llamar", llamar)
    monkeypatch.setitem(trabajador.estado, "procesadas", 0)
    monkeypatch.setitem(trabajador.estado, "ultima", None)
    monkeypatch.setattr(trabajador, "series_pendientes", {})
    return m


def test_procesar_ejecuta_y_publica_el_avance(mundo, redis_falso):
    assert trabajador.procesar(json.dumps({"id": 42, "forzar_error": True}), AJUSTES) == "completado"
    assert mundo["ejecutadas"] == [(42, True)]
    assert redis_falso.get(llaves.progreso(42)) == "100"
    assert 0 < redis_falso.ttl(llaves.progreso(42)) <= trabajador.PROGRESO_TTL
    assert trabajador.estado["ultima"] == {"id": 42, "status": "completado"}
    assert trabajador.estado["corrida_actual"] is None


@pytest.fixture
def sin_base(mundo, monkeypatch, mongo_falso):
    """La ejecutar_run de verdad con la base simulada. `confirma` es lo que responde
    guardar_resultado_run, y `dias_al_confirmar`, los días de la corrida que ya estaban en
    MongoDB cuando se pidió confirmarla."""
    e = {"confirma": True, "dias_al_confirmar": None}

    def guardar_resultado_run(run_id, resultado):
        e["dias_al_confirmar"] = mongo_falso["series_corridas"].count_documents({"run_id": run_id})
        return e["confirma"]

    motor = motores.Motor("seir-ref", "seir-ref-0.1", lambda escenario, semilla: RESULTADO, ())
    monkeypatch.setattr(ejecucion, "ejecutar_run", functools.partial(EJECUTAR_RUN, demora_seg=0))
    monkeypatch.setattr(ejecucion, "escenario_de_version",
                        lambda version_id: ({}, None, []))
    monkeypatch.setattr(ejecucion, "del_nombre", lambda nombre: motor)
    monkeypatch.setattr(ejecucion, "log_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(datos, "marcar_run_ejecutando", lambda run_id: True)
    monkeypatch.setattr(datos, "get_motor_run", lambda run_id: "seir-ref")
    monkeypatch.setattr(datos, "guardar_resultado_run", guardar_resultado_run)
    return e


def test_la_serie_va_a_series_corridas_antes_de_confirmar(sin_base, mongo_falso):
    assert trabajador.procesar(json.dumps({"id": 42}), AJUSTES) == "completado"
    assert sin_base["dias_al_confirmar"] == 2
    docs = list(mongo_falso["series_corridas"].find({"run_id": 42}, {"_id": 0}).sort("dia", 1))
    assert [d["casos_activos"] for d in docs] == [10, 12]
    assert docs[0]["motor"] == "seir-ref" and docs[0]["scenario_version_id"] == 11
    assert docs[0]["scenario_id"] == 3
    assert docs[0]["semilla"] == 7 and docs[0]["batch_id"] == 8
    assert docs[0]["version_esquema"] == 1 and docs[0]["engine_version"] == "seir-ref-0.1"
    assert trabajador.series_pendientes == {}


def test_si_la_corrida_no_se_confirma_no_queda_su_serie(sin_base, mongo_falso, mundo):
    sin_base["confirma"] = False
    assert trabajador.procesar(json.dumps({"id": 42}), AJUSTES) is None
    assert sin_base["dias_al_confirmar"] == 2
    assert mongo_falso["series_corridas"].count_documents({"run_id": 42}) == 0
    assert mundo["llamadas"] == []


def test_si_no_se_confirma_con_mongodb_caido_tampoco_queda_pendiente(sin_base, apagar_mongo):
    sin_base["confirma"] = False
    apagar_mongo()
    assert trabajador.procesar(json.dumps({"id": 42}), AJUSTES) is None
    assert trabajador.series_pendientes == {}


def test_con_mongodb_caido_la_corrida_termina_y_la_serie_se_reintenta(sin_base, mundo, mongo_falso,
                                                                      apagar_mongo, caplog):
    apagar_mongo()
    with caplog.at_level(logging.WARNING, logger="simulador"):
        assert trabajador.procesar(json.dumps({"id": 42}), AJUSTES) == "completado"
    assert sin_base["dias_al_confirmar"] == 0
    assert mundo["llamadas"][0][3]["cuerpo"]["type"] == "RUN_FINISHED"
    assert list(trabajador.series_pendientes) == [42]
    assert any("se reintentará" in r.getMessage() for r in caplog.records)
    trabajador.reintentar_series()
    assert list(trabajador.series_pendientes) == [42]
    apagar_mongo.encender()
    trabajador.reintentar_series()
    assert trabajador.series_pendientes == {}
    assert mongo_falso["series_corridas"].count_documents({"run_id": 42}) == 2


def test_un_reintento_no_duplica_dias(sin_base, mongo_falso):
    trabajador.procesar(json.dumps({"id": 42}), AJUSTES)
    trabajador.procesar(json.dumps({"id": 42}), AJUSTES)
    assert mongo_falso["series_corridas"].count_documents({"run_id": 42}) == 2


def test_el_ciclo_reintenta_las_series_pendientes(mundo, mongo_falso, monkeypatch):
    detener = threading.Event()
    monkeypatch.setitem(trabajador.series_pendientes, 42, [dict(FILA, dia=0, run_id=42)])
    monkeypatch.setattr(trabajador.cola, "tomar", lambda llave: detener.set())
    trabajador.ciclo(AJUSTES, detener)
    assert trabajador.series_pendientes == {}
    assert mongo_falso["series_corridas"].count_documents({"run_id": 42}) == 1


def test_acepta_el_id_solo(mundo):
    trabajador.procesar("42", AJUSTES)
    assert mundo["ejecutadas"] == [(42, False)]


@pytest.mark.parametrize("final,tipo", [("completado", "RUN_FINISHED"), ("fallido", "RUN_FAILED")])
def test_avisa_a_quien_la_pidio_con_token_de_servicio(mundo, final, tipo):
    mundo["final"] = final
    trabajador.procesar(json.dumps({"id": 42}), AJUSTES)
    servicio, metodo, ruta, kw = mundo["llamadas"][0]
    assert (servicio, metodo, ruta) == ("notificaciones", "POST", "/api/v1/notifications")
    cuerpo = kw["cuerpo"]
    assert cuerpo["user_id"] == 5 and cuerpo["type"] == tipo
    assert "SIM-00042" in cuerpo["title"]
    assert cuerpo["payload"] == {"run_id": 42, "status": final, "scenario_id": 3,
                                 "scenario_version_id": 11}
    assert ("Error forzado" in cuerpo["body"]) is (final == "fallido")
    claims = jwt.decode(kw["token"], AJUSTES["JWT_SECRET_KEY"], algorithms=["HS256"],
                        audience="epidemia-interno")
    assert claims["sub"] == "simulador"


def test_no_avisa_si_no_cerro_la_corrida(mundo):
    mundo["final"] = None
    assert trabajador.procesar(json.dumps({"id": 42}), AJUSTES) is None
    assert mundo["llamadas"] == []


@pytest.mark.parametrize("falla", [ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "caído"), Resp(500),
                                   RuntimeError("boom")])
def test_un_aviso_fallido_no_afecta_la_corrida(mundo, caplog, falla):
    mundo["respuesta"] = falla
    with caplog.at_level(logging.WARNING, logger="simulador"):
        assert trabajador.procesar(json.dumps({"id": 42}), AJUSTES) == "completado"
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_recuperar_reencola_las_de_su_motor_y_borra_la_serie_de_las_cerradas(monkeypatch,
                                                                             redis_falso,
                                                                             mongo_falso):
    pedidos = []
    monkeypatch.setattr(datos, "corridas_encoladas", lambda engine: [])
    monkeypatch.setattr(ejecucion, "reencola_corridas_interrumpidas",
                        lambda engine, version: pedidos.append((engine, version)) or ([4], [6]))
    mongo_falso["series_corridas"].insert_many([{"run_id": 6, "dia": 0}, {"run_id": 4, "dia": 0}])
    assert trabajador.recuperar() == ([4], [6])
    assert pedidos == [("seir-ref", "seir-ref-0.1")]
    assert mongo_falso["series_corridas"].count_documents({"run_id": 6}) == 0
    assert mongo_falso["series_corridas"].count_documents({"run_id": 4}) == 1


def test_recuperar_reencola_en_orden_sin_duplicar(monkeypatch, redis_falso):
    pedidos = []
    monkeypatch.setattr(ejecucion, "reencola_corridas_interrumpidas", lambda *a: ([], []))
    monkeypatch.setattr(datos, "corridas_encoladas",
                        lambda engine: pedidos.append(engine) or [3, 5, 8])
    redis_falso.lpush(trabajador.COLA, json.dumps({"id": 5, "forzar_error": True}))
    trabajador.recuperar()
    assert pedidos == ["seir-ref"]
    tomadas = [json.loads(trabajador.cola.tomar(trabajador.COLA)) for _ in range(3)]
    assert [t["id"] for t in tomadas] == [5, 3, 8]
    assert tomadas[0]["forzar_error"] is True
    trabajador.recuperar()
    assert trabajador.cola.pendientes(trabajador.COLA) == 3


@pytest.fixture(autouse=True)
def _sin_prioridades(monkeypatch):
    monkeypatch.setattr(datos, "prioridades", lambda ids: {})


def test_reencolar_manda_cada_corrida_a_la_cola_de_su_prioridad(monkeypatch, redis_falso):
    monkeypatch.setattr(datos, "corridas_encoladas", lambda engine: [3, 5, 8])
    monkeypatch.setattr(datos, "prioridades", lambda ids: {5: "alta", 8: "baja"})
    trabajador.reencolar()
    tomadas = [json.loads(trabajador.cola.tomar(trabajador.COLAS))["id"] for _ in range(3)]
    assert tomadas == [5, 3, 8]
    assert trabajador.reencolar() == 0 or trabajador.cola.pendientes(trabajador.COLAS) == 3


def test_recuperar_con_redis_caido_no_falla_y_el_ciclo_reintenta(monkeypatch, redis_falso,
                                                                  apagar_redis):
    monkeypatch.setattr(ejecucion, "reencola_corridas_interrumpidas", lambda *a: ([], []))
    monkeypatch.setattr(datos, "corridas_encoladas", lambda engine: [7])
    monkeypatch.setattr(trabajador, "pendiente", [])
    apagar_redis()
    assert trabajador.recuperar() == ([], [])
    assert trabajador.pendiente


class Corridas:
    """simulation_runs en memoria, con las transiciones de queries que usa el trabajador."""

    def __init__(self):
        self.filas = {42: {"status": "encolado", "attempts": 0}}

    def marcar(self, run_id):
        f = self.filas[run_id]
        if f["status"] != "encolado" or f["attempts"] >= 3:
            return False
        f.update(status="ejecutando", attempts=f["attempts"] + 1)
        return True

    def confirmar(self, run_id, resultado):
        f = self.filas[run_id]
        if f["status"] != "ejecutando":
            return False
        f["status"] = "completado"
        return True

    def reencolar(self, engine, version, max_intentos=3):
        filas = []
        for run_id, f in self.filas.items():
            if f["status"] == "ejecutando" and f["attempts"] < max_intentos:
                f["status"] = "encolado"
                filas.append({"id": run_id, "requested_by": 5, "seed": 7, "attempts": f["attempts"]})
        return filas

    def cerrar(self, mensaje, estados, engine):
        filas = []
        for run_id, f in self.filas.items():
            if f["status"] in estados:
                f["status"] = "fallido"
                filas.append({"id": run_id, "requested_by": 5, "seed": 7})
        return filas


class TrabajadorMuerto(BaseException):
    """El proceso muere: no lo atrapa ningún except Exception."""


def test_f5_el_trabajador_muere_entre_guardar_la_serie_y_confirmar(sin_base, mundo, mongo_falso,
                                                                    redis_falso, monkeypatch):
    # [Retro: «Fallo de worker»] y D38: después de guardar la serie y antes de confirmar.
    corridas = Corridas()
    monkeypatch.setattr(datos, "marcar_run_ejecutando", corridas.marcar)
    monkeypatch.setattr(datos, "reencola_corridas_interrumpidas", corridas.reencolar)
    monkeypatch.setattr(datos, "marca_corridas_interrumpidas", corridas.cerrar)
    monkeypatch.setattr(datos, "guardar_resultado_run", corridas.confirmar)
    monkeypatch.setattr(datos, "corridas_encoladas",
                        lambda engine: [i for i, f in corridas.filas.items() if f["status"] == "encolado"])

    def muere(run_id, resultado):
        raise TrabajadorMuerto()
    monkeypatch.setattr(datos, "guardar_resultado_run", muere)
    with pytest.raises(TrabajadorMuerto):
        trabajador.procesar(json.dumps({"id": 42}), AJUSTES)
    assert corridas.filas[42] == {"status": "ejecutando", "attempts": 1}
    assert mongo_falso["series_corridas"].count_documents({"run_id": 42}) == 2

    # Arranca otro trabajador: la corrida vuelve a la cola, no se cierra como fallida.
    monkeypatch.setattr(datos, "guardar_resultado_run", corridas.confirmar)
    assert trabajador.recuperar() == ([42], [])
    assert corridas.filas[42]["status"] == "encolado"
    assert trabajador.cola.pendientes(trabajador.COLA) == 1

    # La repite con la misma semilla: queda una sola corrida, completada, con su serie entera.
    assert trabajador.procesar(trabajador.cola.tomar(trabajador.COLA), AJUSTES) == "completado"
    assert corridas.filas == {42: {"status": "completado", "attempts": 2}}
    assert mongo_falso["series_corridas"].count_documents({"run_id": 42}) == 2
    assert trabajador.cola.pendientes(trabajador.COLA) == 0


def test_f5_sin_intentos_se_cierra_como_fallida_sin_serie(sin_base, mundo, mongo_falso, redis_falso,
                                                         monkeypatch):
    corridas = Corridas()
    corridas.filas[42] = {"status": "ejecutando", "attempts": 3}
    monkeypatch.setattr(datos, "reencola_corridas_interrumpidas", corridas.reencolar)
    monkeypatch.setattr(datos, "marca_corridas_interrumpidas", corridas.cerrar)
    monkeypatch.setattr(datos, "corridas_encoladas", lambda engine: [])
    mongo_falso["series_corridas"].insert_one({"run_id": 42, "dia": 0})
    assert trabajador.recuperar() == ([], [42])
    assert corridas.filas[42]["status"] == "fallido"
    assert mongo_falso["series_corridas"].count_documents({"run_id": 42}) == 0


def test_un_error_de_base_al_reintentar_no_mata_al_ciclo(mundo, monkeypatch):
    detener = threading.Event()
    intentos = []

    def reencolar():
        intentos.append(1)
        if len(intentos) == 1:
            raise psycopg2.OperationalError("sin base")
        detener.set()

    monkeypatch.setattr(trabajador, "PAUSA_SIN_REDIS", 0)
    monkeypatch.setattr(trabajador, "pendiente", [True])
    monkeypatch.setattr(trabajador, "reencolar", reencolar)
    monkeypatch.setattr(trabajador.cola, "tomar", lambda llave: None)
    trabajador.ciclo(AJUSTES, detener)
    assert len(intentos) == 2 and trabajador.pendiente == []


def test_el_ciclo_reintenta_el_reencolado_pendiente(mundo, monkeypatch):
    detener = threading.Event()
    intentos = []

    def reencolar():
        intentos.append(1)
        if len(intentos) == 1:
            raise RedisNoDisponible("caído")

    def tomar(llave):
        if len(intentos) == 2:
            detener.set()
        return None

    monkeypatch.setattr(trabajador, "PAUSA_SIN_REDIS", 0)
    monkeypatch.setattr(trabajador, "pendiente", [True])
    monkeypatch.setattr(trabajador, "reencolar", reencolar)
    monkeypatch.setattr(trabajador.cola, "tomar", tomar)
    trabajador.ciclo(AJUSTES, detener)
    assert len(intentos) == 2 and trabajador.pendiente == []


@pytest.fixture
def otro_motor(monkeypatch):
    """Vuelve a cargar el trabajador con SIMULADOR_MOTOR, y al final con el de omisión."""
    def cargar(valor):
        if valor is None:
            monkeypatch.delenv("SIMULADOR_MOTOR", raising=False)
        else:
            monkeypatch.setenv("SIMULADOR_MOTOR", valor)
        return importlib.reload(trabajador)

    yield cargar
    monkeypatch.delenv("SIMULADOR_MOTOR", raising=False)
    importlib.reload(trabajador)


def test_el_motor_y_su_cola_salen_de_simulador_motor(otro_motor):
    seir = otro_motor(None)
    assert (seir.MOTOR, seir.COLA) == ("seir-ref", "queue:simulaciones:seir-ref")
    abm = otro_motor(" abm-ref ")
    assert (abm.MOTOR, abm.COLA, abm.estado["motor"]) == ("abm-ref", "queue:simulaciones:abm-ref",
                                                         "abm-ref")


@pytest.mark.parametrize("valor", ["numba", "otro"])
def test_un_motor_que_no_esta_implementado_no_arranca(otro_motor, valor):
    with pytest.raises(MotorNoDisponible):
        otro_motor(valor)


def test_abm_gpu_sin_flame_gpu_no_arranca(otro_motor, monkeypatch):
    """Un simulador de abm-gpu sin pyflamegpu o sin GPU tomaría corridas que no puede correr."""
    from procesamiento import motores
    sin_gpu = dataclasses.replace(motores.IMPLEMENTADOS["abm-gpu"],
                                  disponible=lambda: (False, "no hay GPU"))
    monkeypatch.setitem(motores.IMPLEMENTADOS, "abm-gpu", sin_gpu)
    with pytest.raises(MotorNoDisponible, match="no hay GPU"):
        otro_motor("abm-gpu")


def test_el_ciclo_sobrevive_a_redis_caido_y_a_un_pedido_ilegible(mundo, monkeypatch, caplog):
    detener = threading.Event()
    entregas = [RedisNoDisponible("caído"), "no es json", json.dumps({"id": 42}), None]

    def tomar(llave):
        assert llave == trabajador.COLAS and trabajador.COLA == "queue:simulaciones:seir-ref"
        entrega = entregas.pop(0)
        if not entregas:
            detener.set()
        if isinstance(entrega, Exception):
            raise entrega
        return entrega

    monkeypatch.setattr(trabajador.cola, "tomar", tomar)
    monkeypatch.setattr(trabajador, "PAUSA_SIN_REDIS", 0)
    with caplog.at_level(logging.ERROR, logger="simulador"):
        trabajador.ciclo(AJUSTES, detener)
    assert mundo["ejecutadas"] == [(42, False)]
    assert trabajador.estado["activo"] is False
    assert any("no es json" in r.getMessage() for r in caplog.records)


# ---- ruta de estado -------------------------------------------------------------------

@pytest.fixture
def cliente(crear_cliente, redis_falso):
    return crear_cliente("simulador")


def test_estado_sin_token_es_401(cliente):
    assert cliente.get("/api/v1/worker/status").status_code == 401


def test_capturista_no_ve_el_estado(cliente, token):
    assert cliente.get("/api/v1/worker/status", headers=token(("CAPTURISTA",))).status_code == 403


@pytest.mark.parametrize("rol", rutas.ROLES)
def test_estado_con_pendientes(cliente, token, redis_falso, rol):
    redis_falso.lpush(trabajador.COLA, json.dumps({"id": 1}), json.dumps({"id": 2}))
    # Lo que espera en la cola de otro motor no es de este simulador.
    redis_falso.lpush(llaves.cola_simulaciones("abm-gpu"), json.dumps({"id": 3}))
    datos = cliente.get("/api/v1/worker/status?format=json", headers=token((rol,))).get_json()
    assert datos["pendientes"] == 2 and datos["motor"] == "seir-ref"
    assert set(datos) == {"trabajador", "motor", "activo", "corrida_actual", "procesadas",
                          "ultima", "pendientes"}


def test_estado_en_xml(cliente, token):
    r = cliente.get("/api/v1/worker/status", headers=token())
    assert r.mimetype == "application/xml" and b"<pendientes" in r.data


def test_redis_caido_es_503(cliente, token, apagar_redis):
    cabeceras = token()
    apagar_redis()
    assert cliente.get("/api/v1/worker/status", headers=cabeceras).status_code == 503


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (RAIZ / "docs/contratos/simulador/openapi.json").read_bytes()


def test_dockerfile_arranca_el_trabajador():
    docker = (RAIZ / "microservicios/simulador/Dockerfile").read_text(encoding="utf-8")
    assert '"-m", "microservicios.simulador"' in docker
    assert "COPY docs/contratos/simulador/" in docker
    assert "HEALTHCHECK" in docker and "USER epidemia" in docker


def test_ejemplos_iguales_al_contrato():
    carpeta = RAIZ / "docs/contratos/simulador"
    contrato = json.loads((carpeta / "openapi.json").read_text(encoding="utf-8"))
    assert contrato["servers"][0]["url"].endswith(":5242")
    item = contrato["paths"]["/api/v1/worker/status"]["get"]
    assert item["security"] == [{"bearerAuth": []}]
    contenido = item["responses"]["200"]["content"]
    ejemplo = carpeta / "ejemplos" / item["operationId"]
    assert contenido["application/json"]["example"] == json.loads(
        ejemplo.with_suffix(".json").read_text(encoding="utf-8"))
    assert contenido["application/xml"]["examples"]["respuesta"]["value"] == \
        ejemplo.with_suffix(".xml").read_text(encoding="utf-8")
