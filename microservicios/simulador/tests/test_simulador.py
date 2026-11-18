import dataclasses
import importlib
import json
import logging
import threading
from pathlib import Path

import jwt
import psycopg2
import pytest

from backend_web import queries, simulaciones
from epidemia_comun import llaves
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.redis_compartido import RedisNoDisponible
from microservicios.simulador import rutas, trabajador
from procesamiento.motores import MotorNoDisponible

RAIZ = Path(__file__).resolve().parents[3]
AJUSTES = {"JWT_SECRET_KEY": "secreto-de-pruebas-del-simulador-0123456789",
           "JWT_ISSUER": "epidemia-auth", "JWT_AUDIENCE_INTERNA": "epidemia-interno"}


FILA = {"S": 990, "E": 0, "I": 10, "R": 0, "H": 0, "D": 0, "V": 0, "casos_activos": 10,
        "nuevos_casos": 0, "nuevas_hospitalizaciones": 0, "nuevas_defunciones": 0,
        "dosis_aplicadas": 0}
RESULTADO = {"engine_version": "seir-ref-0.1",
             "serie": [dict(FILA, dia=0), dict(FILA, dia=1, casos_activos=12, E=2, S=988)]}


class Resp:
    def __init__(self, estado=201):
        self.status_code = estado


@pytest.fixture
def mundo(monkeypatch, redis_falso, mongo_falso):
    """ejecutar_run, get_run y llamar() simulados; el avance va al Redis falso y la serie de
    una corrida completada, al MongoDB falso."""
    m = {"ejecutadas": [], "llamadas": [], "final": "completado", "respuesta": Resp()}

    def ejecutar_run(run_id, forzar_error=False, al_avanzar=None, al_guardar=None):
        m["ejecutadas"].append((run_id, forzar_error))
        for porcentaje in (10, 30, 90, 100):
            al_avanzar(porcentaje)
        if m["final"] == "completado":
            al_guardar({"id": run_id, "batch_id": 8, "scenario_version_id": 11, "seed": 7},
                       "seir-ref", RESULTADO)
        return m["final"]

    def llamar(servicio, metodo, ruta, **kw):
        m["llamadas"].append((servicio, metodo, ruta, kw))
        if isinstance(m["respuesta"], Exception):
            raise m["respuesta"]
        return m["respuesta"]

    monkeypatch.setattr(simulaciones, "ejecutar_run", ejecutar_run)
    monkeypatch.setattr(queries, "get_run", lambda run_id: {
        "id": run_id, "requested_by": 5, "scenario_id": 3, "scenario_version_id": 11,
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


def test_la_serie_va_a_series_corridas(mundo, mongo_falso):
    trabajador.procesar(json.dumps({"id": 42}), AJUSTES)
    docs = list(mongo_falso["series_corridas"].find({"run_id": 42}, {"_id": 0}).sort("dia", 1))
    assert [d["casos_activos"] for d in docs] == [10, 12]
    assert docs[0]["motor"] == "seir-ref" and docs[0]["scenario_version_id"] == 11
    assert docs[0]["semilla"] == 7 and docs[0]["batch_id"] == 8
    assert docs[0]["version_esquema"] == 1 and docs[0]["engine_version"] == "seir-ref-0.1"
    assert trabajador.series_pendientes == {}


def test_con_mongodb_caido_la_corrida_termina_y_la_serie_se_reintenta(mundo, mongo_falso,
                                                                      apagar_mongo, caplog):
    apagar_mongo()
    with caplog.at_level(logging.WARNING, logger="simulador"):
        assert trabajador.procesar(json.dumps({"id": 42}), AJUSTES) == "completado"
    assert mundo["llamadas"][0][3]["cuerpo"]["type"] == "RUN_FINISHED"
    assert list(trabajador.series_pendientes) == [42]
    assert any("se reintentará" in r.getMessage() for r in caplog.records)
    trabajador.reintentar_series()
    assert list(trabajador.series_pendientes) == [42]
    apagar_mongo.encender()
    trabajador.reintentar_series()
    assert trabajador.series_pendientes == {}
    assert mongo_falso["series_corridas"].count_documents({"run_id": 42}) == 2


def test_un_reintento_no_duplica_dias(mundo, mongo_falso):
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


def test_recuperar_solo_cierra_las_que_se_estaban_ejecutando_de_su_motor(monkeypatch,
                                                                         redis_falso):
    pedidos = []
    monkeypatch.setattr(simulaciones, "corridas_encoladas", lambda engine: [])
    monkeypatch.setattr(simulaciones, "recupera_corridas_interrumpidas",
                        lambda estados, engine: pedidos.append((estados, engine)) or 2)
    assert trabajador.recuperar() == 2
    assert pedidos == [(("ejecutando",), "seir-ref")]


def test_recuperar_reencola_en_orden_sin_duplicar(monkeypatch, redis_falso):
    pedidos = []
    monkeypatch.setattr(simulaciones, "recupera_corridas_interrumpidas", lambda **kw: 0)
    monkeypatch.setattr(simulaciones, "corridas_encoladas",
                        lambda engine: pedidos.append(engine) or [3, 5, 8])
    redis_falso.lpush(trabajador.COLA, json.dumps({"id": 5, "forzar_error": True}))
    trabajador.recuperar()
    assert pedidos == ["seir-ref"]
    tomadas = [json.loads(trabajador.cola.tomar(trabajador.COLA)) for _ in range(3)]
    assert [t["id"] for t in tomadas] == [5, 3, 8]
    assert tomadas[0]["forzar_error"] is True
    trabajador.recuperar()
    assert trabajador.cola.pendientes(trabajador.COLA) == 3


def test_recuperar_con_redis_caido_no_falla_y_el_ciclo_reintenta(monkeypatch, redis_falso,
                                                                  apagar_redis):
    monkeypatch.setattr(simulaciones, "recupera_corridas_interrumpidas", lambda **kw: 0)
    monkeypatch.setattr(simulaciones, "corridas_encoladas", lambda engine: [7])
    monkeypatch.setattr(trabajador, "pendiente", [])
    apagar_redis()
    assert trabajador.recuperar() == 0
    assert trabajador.pendiente


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
        assert llave == trabajador.COLA == "queue:simulaciones:seir-ref"
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
