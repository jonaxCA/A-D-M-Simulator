import json
import logging
import threading
from pathlib import Path

import jwt
import pytest

from backend_web import queries, simulaciones
from epidemia_comun import llaves
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.redis_compartido import RedisNoDisponible
from microservicios.simulador import rutas, trabajador

RAIZ = Path(__file__).resolve().parents[3]
AJUSTES = {"JWT_SECRET_KEY": "secreto-de-pruebas-del-simulador-0123456789",
           "JWT_ISSUER": "epidemia-auth", "JWT_AUDIENCE_INTERNA": "epidemia-interno"}


class Resp:
    def __init__(self, estado=201):
        self.status_code = estado


@pytest.fixture
def mundo(monkeypatch, redis_falso):
    """ejecutar_run, get_run y llamar() simulados; el avance va al Redis falso."""
    m = {"ejecutadas": [], "llamadas": [], "final": "completado", "respuesta": Resp()}

    def ejecutar_run(run_id, forzar_error=False, al_avanzar=None):
        m["ejecutadas"].append((run_id, forzar_error))
        for porcentaje in (10, 30, 90, 100):
            al_avanzar(porcentaje)
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
    return m


def test_procesar_ejecuta_y_publica_el_avance(mundo, redis_falso):
    assert trabajador.procesar(json.dumps({"id": 42, "forzar_error": True}), AJUSTES) == "completado"
    assert mundo["ejecutadas"] == [(42, True)]
    assert redis_falso.get(llaves.progreso(42)) == "100"
    assert 0 < redis_falso.ttl(llaves.progreso(42)) <= trabajador.PROGRESO_TTL
    assert trabajador.estado["ultima"] == {"id": 42, "status": "completado"}
    assert trabajador.estado["corrida_actual"] is None


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


def test_recuperar_solo_cierra_las_que_se_estaban_ejecutando(monkeypatch):
    pedidos = []
    monkeypatch.setattr(simulaciones, "recupera_corridas_interrumpidas",
                        lambda estados: pedidos.append(estados) or 2)
    assert trabajador.recuperar() == 2
    assert pedidos == [("ejecutando",)]


def test_el_ciclo_sobrevive_a_redis_caido_y_a_un_pedido_ilegible(mundo, monkeypatch, caplog):
    detener = threading.Event()
    entregas = [RedisNoDisponible("caído"), "no es json", json.dumps({"id": 42}), None]

    def tomar(llave):
        assert llave == llaves.COLA_SIMULACIONES
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
    redis_falso.lpush(llaves.COLA_SIMULACIONES, json.dumps({"id": 1}), json.dumps({"id": 2}))
    datos = cliente.get("/api/v1/worker/status?format=json", headers=token((rol,))).get_json()
    assert datos["pendientes"] == 2
    assert set(datos) == {"trabajador", "activo", "corrida_actual", "procesadas", "ultima",
                          "pendientes"}


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
