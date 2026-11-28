import json
from datetime import date, datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import xmlschema

from epidemia_comun import llaves
from epidemia_comun.redis_compartido import RedisNoDisponible
from microservicios.corridas import datos, rutas

RAIZ = Path(__file__).resolve().parents[3]
VERSION_APROBADA, VERSION_BORRADOR = 11, 12
REGION = 9


class Base:
    """Las corridas de una base simulada, con las reglas de crear_corrida y cancelar_run.
    `motores` guarda el motor y la versión con que se creó cada corrida."""

    def __init__(self):
        self.corridas, self.creadas, self.canceladas, self.motores = {}, [], [], {}
        self.prioridades, self.reintentadas, self.estimacion = {}, [], None

    def crear_corrida(self, version_id, seed, user_id, engine_version, *, engine="seir-ref",
                      contexto=None, forzar_error=False, prioridad="normal"):
        if version_id not in (VERSION_APROBADA, VERSION_BORRADOR):
            return None, None, "La versión de escenario no existe."
        if version_id == VERSION_BORRADOR:
            return None, None, ("Esta versión no está aprobada (estado: borrador); solo se pueden "
                                "ejecutar simulaciones sobre versiones aprobadas.")
        run_id = 40 + len(self.creadas)
        self.creadas.append((version_id, seed, user_id, contexto.user_id, forzar_error))
        self.motores[run_id] = (engine, engine_version)
        self.prioridades[run_id] = prioridad
        self.corridas[run_id] = corrida(run_id, "encolado")
        return run_id, 90 + len(self.creadas), None

    def region_de_version(self, version_id):
        return REGION if version_id in (VERSION_APROBADA, VERSION_BORRADOR) else None

    def get_run(self, run_id):
        return dict(self.corridas[run_id]) if run_id in self.corridas else None

    def get_motor_run(self, run_id):
        if run_id not in self.corridas:
            return None
        return self.motores.get(run_id, ("seir-ref",))[0]

    def reintentar_run(self, run_id, *, contexto, puede_alta=False):
        if self.corridas.get(run_id, {}).get("status") != "fallido":
            return None
        self.corridas[run_id]["status"] = "encolado"
        if self.prioridades.get(run_id) == "alta" and not puede_alta:
            self.prioridades[run_id] = "normal"
        self.reintentadas.append((run_id, contexto.user_id))
        return self.prioridades.get(run_id, "normal")

    def estimar_corrida(self, run_id):
        return self.estimacion or {"priority": "normal", "queue_position": 1,
                                   "estimated_seconds": None, "estimate_samples": 0,
                                   "estimate_reason": "Aún no hay corridas completadas."}

    def cancelar_run(self, run_id, *, contexto):
        if self.corridas.get(run_id, {}).get("status") != "encolado":
            return False
        self.corridas[run_id]["status"] = "cancelado"
        self.canceladas.append((run_id, contexto.user_id))
        return True


def corrida(run_id, status, progress=0):
    return {"id": run_id, "batch_id": 90, "scenario_version_id": VERSION_APROBADA, "seed": 982314,
            "status": status, "progress": progress, "engine_version": "seir-ref-0.1",
            "queued_at": datetime(2026, 10, 20, 15, tzinfo=timezone.utc), "started_at": None,
            "finished_at": None, "error_message": None, "requested_by": 7, "version_number": 2,
            "scenario_id": 3, "version_status": "aprobado", "population_size": 500000,
            "horizon_days": 120, "initial_infected": 100, "scenario_name": "Ola Influenza ZMM",
            "disease_id": 1, "disease_name": "Influenza A", "region_id": REGION,
            "region_name": "Monterrey", "requested_by_username": "alex.cavazos",
            "requested_by_nombre": "Alex Cavazos"}


@pytest.fixture
def base(monkeypatch):
    b = Base()
    for nombre in ("crear_corrida", "get_run", "cancelar_run", "get_motor_run",
                   "reintentar_run", "estimar_corrida", "region_de_version"):
        monkeypatch.setattr(datos, nombre, getattr(b, nombre))
    b.filtros = []

    def recientes(limit=20, **filtros):
        b.filtros.append(filtros)
        return [{"id": i, "status": "completado"} for i in range(limit)]

    monkeypatch.setattr(datos, "get_runs_recientes", recientes)
    return b


@pytest.fixture
def cliente(crear_cliente, base):
    return crear_cliente("corridas")


def lanzar(cliente, cabeceras, cuerpo):
    return cliente.post("/api/v1/runs?format=json", json=cuerpo, headers=cabeceras)


def en_cola(redis_falso, motor="seir-ref", prioridad="normal"):
    # LPUSH y BRPOP: el que se toma primero está al final de la lista.
    llave = llaves.cola_con_prioridad(motor, prioridad)
    return [json.loads(x) for x in reversed(redis_falso.lrange(llave, 0, -1))]


# ---- lanzar --------------------------------------------------------------------------

def test_sin_token_es_401(cliente):
    assert cliente.post("/api/v1/runs", json={"scenario_version_id": 11}).status_code == 401


@pytest.mark.parametrize("rol", ["EPIDEMIOLOGO", "CAPTURISTA"])
def test_quien_no_ejecuta_recibe_403(cliente, token, base, rol):
    r = lanzar(cliente, token((rol,)), {"scenario_version_id": VERSION_APROBADA})
    assert r.status_code == 403 and base.creadas == []


@pytest.mark.parametrize("rol", rutas.ROLES_EJECUTAN)
def test_lanzar_responde_202_y_encola(cliente, token, base, redis_falso, rol):
    r = lanzar(cliente, token((rol,)), {"scenario_version_id": VERSION_APROBADA, "seed": 0})
    assert r.status_code == 202
    assert r.get_json() == {"id": 40, "batch_id": 91, "scenario_version_id": 11, "seed": 0,
                            "engine": "seir-ref", "forzar_error": False, "priority": "normal",
                            "status": "encolado"}
    assert base.creadas == [(11, 0, 7, 7, False)]
    assert base.motores == {40: ("seir-ref", "seir-ref-0.1")}
    assert en_cola(redis_falso) == [{"id": 40, "forzar_error": False}]
    # El candado se suelta al terminar.
    assert redis_falso.get(llaves.candado_corrida(11)) is None


@pytest.mark.parametrize("replicas", [30, 100, "50"])
def test_replicas_hasta_el_tope_se_aceptan(cliente, token, base, redis_falso, replicas):
    r = lanzar(cliente, token(), {"scenario_version_id": 11, "replicas": replicas})
    assert r.status_code == 202


@pytest.mark.parametrize("replicas, detalle", [
    (101, "replicas no puede pasar de 100."), (200, "replicas no puede pasar de 100."),
    (0, "El campo replicas debe ser entero positivo."),
    ("x", "El campo replicas debe ser entero positivo.")])
def test_replicas_mas_del_tope_es_422(cliente, token, base, redis_falso, replicas, detalle):
    r = lanzar(cliente, token(), {"scenario_version_id": 11, "replicas": replicas})
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"
    assert r.get_json()["detail"] == detalle
    assert base.creadas == [] and en_cola(redis_falso) == []


def test_un_motor_no_habilitado_es_422(cliente, token, base, redis_falso, monkeypatch):
    monkeypatch.delenv("MOTORES_HABILITADOS", raising=False)
    r = lanzar(cliente, token(), {"scenario_version_id": 11, "engine": "abm-gpu"})
    assert r.status_code == 422 and r.get_json()["detail"] == "engine debe ser uno de: seir-ref."
    assert base.creadas == [] and en_cola(redis_falso, "abm-gpu") == []


def test_un_motor_habilitado_va_a_su_propia_cola(cliente, token, base, redis_falso, monkeypatch):
    monkeypatch.setenv("MOTORES_HABILITADOS", " abm-gpu ,gpu")
    r = lanzar(cliente, token(), {"scenario_version_id": 11, "engine": "abm-gpu"})
    assert r.status_code == 202 and r.get_json()["engine"] == "abm-gpu"
    # La versión sale del registro, aunque corridas no tenga GPU.
    assert base.motores == {40: ("abm-gpu", "abm-gpu-0.1")}
    assert en_cola(redis_falso, "abm-gpu") == [{"id": 40, "forzar_error": False}]
    assert en_cola(redis_falso) == []
    # Un nombre que la base no acepta no se habilita aunque venga en la variable.
    assert rutas.motores_habilitados() == ["seir-ref", "abm-gpu"]
    assert lanzar(cliente, token(), {"scenario_version_id": 11, "engine": "gpu"}).status_code == 422


def test_abm_ref_va_a_su_cola_con_su_version(cliente, token, base, redis_falso, monkeypatch):
    """corridas conoce la versión de los motores implementados (procesamiento/motores.py)."""
    monkeypatch.setenv("MOTORES_HABILITADOS", "abm-ref")
    r = lanzar(cliente, token(), {"scenario_version_id": 11, "engine": "abm-ref"})
    assert r.status_code == 202 and r.get_json()["engine"] == "abm-ref"
    assert base.motores == {40: ("abm-ref", "abm-ref-0.1")}
    assert en_cola(redis_falso, "abm-ref") == [{"id": 40, "forzar_error": False}]
    assert en_cola(redis_falso) == []


@pytest.mark.parametrize("anterior, actual", [("python-ref", "seir-ref"), ("cuda", "abm-gpu")])
def test_los_nombres_anteriores_a_d2_se_traducen(cliente, token, base, redis_falso, monkeypatch,
                                                anterior, actual):
    """Un cliente de la v1 que todavía manda los nombres viejos no se rompe (D2): se traducen,
    también en MOTORES_HABILITADOS, y la respuesta lleva el nombre nuevo."""
    monkeypatch.setenv("MOTORES_HABILITADOS", "cuda")
    assert rutas.motores_habilitados() == ["seir-ref", "abm-gpu"]
    r = lanzar(cliente, token(), {"scenario_version_id": 11, "engine": anterior})
    assert r.status_code == 202 and r.get_json()["engine"] == actual
    assert base.motores[40][0] == actual
    assert en_cola(redis_falso, actual) == [{"id": 40, "forzar_error": False}]


def test_un_motor_que_no_es_texto_es_422(cliente, token, base):
    r = lanzar(cliente, token(), {"scenario_version_id": 11, "engine": ["seir-ref"]})
    assert r.status_code == 422 and base.creadas == []


def test_semilla_aleatoria_si_no_llega(cliente, token, base):
    r = lanzar(cliente, token(), {"scenario_version_id": VERSION_APROBADA})
    assert 0 <= r.get_json()["seed"] <= rutas.SEMILLA_MAX


def test_forzar_error_solo_para_administrador(cliente, token, base, redis_falso):
    lanzar(cliente, token(("ANALISTA",)), {"scenario_version_id": 11, "forzar_error": True})
    lanzar(cliente, token(("ADMINISTRADOR",)), {"scenario_version_id": 11, "forzar_error": True})
    assert [c[4] for c in base.creadas] == [False, True]
    assert [p["forzar_error"] for p in en_cola(redis_falso)] == [False, True]


def test_la_prioridad_va_a_su_cola(cliente, token, base, redis_falso):
    assert lanzar(cliente, token(("ADMINISTRADOR",)),
                  {"scenario_version_id": 11, "priority": "alta"}).get_json()["priority"] == "alta"
    lanzar(cliente, token(), {"scenario_version_id": 11, "priority": "baja"})
    lanzar(cliente, token(), {"scenario_version_id": 11})
    assert base.prioridades == {40: "alta", 41: "baja", 42: "normal"}
    assert [p["id"] for p in en_cola(redis_falso, prioridad="alta")] == [40]
    assert [p["id"] for p in en_cola(redis_falso, prioridad="baja")] == [41]
    assert [p["id"] for p in en_cola(redis_falso)] == [42]


def test_prioridad_alta_solo_para_administrador(cliente, token, base, redis_falso):
    r = lanzar(cliente, token(("ANALISTA",)), {"scenario_version_id": 11, "priority": "alta"})
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"
    assert base.creadas == []


def test_prioridad_desconocida_es_422(cliente, token, base):
    r = lanzar(cliente, token(), {"scenario_version_id": 11, "priority": "urgente"})
    assert r.status_code == 422 and base.creadas == []


def test_acepta_xml(cliente, token, base):
    r = cliente.post("/api/v1/runs", headers={**token(), "Content-Type": "application/xml"},
                     data=b"<solicitud><scenario_version_id>11</scenario_version_id>"
                          b"<seed>5</seed><engine>seir-ref</engine>"
                          b"<forzar_error>false</forzar_error></solicitud>")
    assert r.status_code == 202 and r.mimetype == "application/xml"
    assert ET.fromstring(r.data).findtext("seed") == "5"
    assert ET.fromstring(r.data).findtext("engine") == "seir-ref"


@pytest.mark.parametrize("cuerpo", [{}, {"scenario_version_id": "x"}, {"scenario_version_id": 0},
                                    {"scenario_version_id": 11, "seed": -1},
                                    {"scenario_version_id": 11, "seed": 2**31},
                                    {"scenario_version_id": 11, "seed": 1.5},
                                    {"scenario_version_id": 11, "seed": True},
                                    {"scenario_version_id": 11, "engine": 5},
                                    {"scenario_version_id": 11, "engine": "Python-Ref"},
                                    {"scenario_version_id": 11, "forzar_error": "si"}])
def test_cuerpo_invalido_es_422(cliente, token, base, cuerpo):
    r = lanzar(cliente, token(), cuerpo)
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"
    assert base.creadas == []


def test_version_inexistente_es_404(cliente, token):
    assert lanzar(cliente, token(), {"scenario_version_id": 99}).status_code == 404


def test_version_no_aprobada_es_409(cliente, token, redis_falso):
    r = lanzar(cliente, token(), {"scenario_version_id": VERSION_BORRADOR})
    assert r.status_code == 409 and "no está aprobada" in r.get_json()["detail"]
    assert en_cola(redis_falso) == []


def test_doble_clic_es_409(cliente, token, base, redis_falso):
    redis_falso.set(llaves.candado_corrida(11), "otra-peticion", ex=10)
    r = lanzar(cliente, token(), {"scenario_version_id": 11})
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"
    assert base.creadas == []


def test_si_no_se_puede_encolar_la_corrida_se_cancela(cliente, token, base, monkeypatch):
    def caido(*_):
        raise RedisNoDisponible("caído")
    monkeypatch.setattr(rutas.cola, "encolar", caido)
    r = lanzar(cliente, token(), {"scenario_version_id": 11})
    assert r.status_code == 503 and r.get_json()["codigo"] == "SERVICIO_NO_DISPONIBLE"
    assert base.canceladas == [(40, 7)]


def test_redis_caido_es_503_sin_crear_nada(cliente, token, base, apagar_redis):
    cabeceras = token()
    apagar_redis()
    assert lanzar(cliente, cabeceras, {"scenario_version_id": 11}).status_code == 503
    assert base.creadas == []


# ---- consultar ------------------------------------------------------------------------

def test_lista_con_limite(cliente, token, base):
    r = cliente.get("/api/v1/runs?limit=3&format=json", headers=token(("EPIDEMIOLOGO",)))
    assert r.status_code == 200 and r.get_json()["total"] == 3
    assert base.filtros == [{}]


def test_lista_con_todos_los_filtros(cliente, token, base):
    r = cliente.get("/api/v1/runs?format=json&scenario_id=3&scenario_version_id=11&status=fallido"
                    "&engine=abm-gpu&from=2026-10-01&to=2026-10-20", headers=token())
    assert r.status_code == 200
    # abm-gpu no está habilitado para lanzar, pero sus corridas se pueden buscar.
    assert base.filtros == [{"scenario_id": 3, "scenario_version_id": 11, "status": "fallido",
                             "engine": "abm-gpu", "desde": date(2026, 10, 1),
                             "hasta": date(2026, 10, 20)}]


def test_el_filtro_acepta_el_nombre_anterior_del_motor(cliente, token, base):
    r = cliente.get("/api/v1/runs?format=json&engine=numba", headers=token())
    assert r.status_code == 200 and base.filtros == [{"engine": "abm-ref"}]


def test_un_solo_dia(cliente, token, base):
    cliente.get("/api/v1/runs?from=2026-10-20&to=2026-10-20", headers=token())
    assert base.filtros == [{"desde": date(2026, 10, 20), "hasta": date(2026, 10, 20)}]


@pytest.mark.parametrize("limite", ["0", "x", str(rutas.LIMITE_MAX + 1)])
def test_limite_invalido_es_422(cliente, token, limite):
    assert cliente.get("/api/v1/runs?limit=" + limite, headers=token()).status_code == 422


@pytest.mark.parametrize("filtro", ["scenario_id=0", "scenario_version_id=x", "status=pausado",
                                    "status=", "engine=gpu", "from=20-10-2026", "to=2026-13-01",
                                    "from=2026-10-21&to=2026-10-20"])
def test_filtro_invalido_es_422_sin_consultar(cliente, token, base, filtro):
    r = cliente.get("/api/v1/runs?format=json&" + filtro, headers=token())
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"
    assert base.filtros == []


def test_capturista_no_ve_corridas(cliente, token):
    assert cliente.get("/api/v1/runs", headers=token(("CAPTURISTA",))).status_code == 403


def test_progreso_en_vivo_sale_de_redis(cliente, token, base, redis_falso):
    base.corridas[40] = corrida(40, "ejecutando", progress=0)
    redis_falso.set(llaves.progreso(40), 30)
    datos = cliente.get("/api/v1/runs/40?format=json", headers=token()).get_json()
    assert datos["progress"] == 30 and datos["terminal"] is False


def test_sin_redis_el_progreso_es_el_de_la_base(cliente, token, base):
    base.corridas[40] = corrida(40, "ejecutando", progress=0)
    assert cliente.get("/api/v1/runs/40?format=json", headers=token()).get_json()["progress"] == 0


def test_una_terminada_usa_el_progreso_de_la_base(cliente, token, base, redis_falso):
    base.corridas[40] = corrida(40, "completado", progress=100)
    redis_falso.set(llaves.progreso(40), 90)
    datos = cliente.get("/api/v1/runs/40?format=json", headers=token()).get_json()
    assert datos["progress"] == 100 and datos["terminal"] is True


def test_consultar_en_xml_por_omision(cliente, token, base):
    base.corridas[40] = corrida(40, "encolado")
    r = cliente.get("/api/v1/runs/40", headers=token())
    assert r.mimetype == "application/xml"
    assert ET.fromstring(r.data).findtext("status") == "encolado"


def test_consultar_y_listar_responden_solo_lo_del_contrato(cliente, token, base, monkeypatch):
    base.corridas[40] = dict(corrida(40, "encolado"), region_population=1142994)
    ejemplos = RAIZ / "docs/contratos/corridas/ejemplos"
    detalle = cliente.get("/api/v1/runs/40?format=json", headers=token()).get_json()
    assert set(detalle) == set(json.loads((ejemplos / "consultar_corrida.json").read_text()))
    fila = dict(corrida(40, "encolado"), region_population=1142994)
    monkeypatch.setattr(datos, "get_runs_recientes", lambda limit=20, **_: [fila])
    listado = cliente.get("/api/v1/runs?format=json", headers=token()).get_json()
    assert set(listado["corridas"][0]) == set(
        json.loads((ejemplos / "listar_corridas.json").read_text())["corridas"][0])


def test_consultar_dice_el_motor(cliente, token, base):
    base.corridas[40] = corrida(40, "encolado")
    base.motores[40] = ("abm-gpu", None)
    assert cliente.get("/api/v1/runs/40?format=json", headers=token()).get_json()["engine"] == "abm-gpu"


def test_consultar_trae_la_estimacion(cliente, token, base):
    base.corridas[40] = corrida(40, "encolado")
    base.estimacion = {"priority": "alta", "queue_position": 2, "estimated_seconds": 90,
                       "estimate_samples": 4, "estimate_reason": None}
    datos = cliente.get("/api/v1/runs/40?format=json", headers=token()).get_json()
    assert (datos["priority"], datos["queue_position"], datos["estimated_seconds"]) == ("alta", 2, 90)
    assert datos["estimate_reason"] is None


def test_sin_historial_la_estimacion_es_nula_con_motivo(cliente, token, base):
    base.corridas[40] = corrida(40, "encolado")
    datos = cliente.get("/api/v1/runs/40?format=json", headers=token()).get_json()
    assert datos["estimated_seconds"] is None and datos["estimate_reason"]


def test_corrida_inexistente_es_404(cliente, token):
    assert cliente.get("/api/v1/runs/404", headers=token()).status_code == 404


# ---- cancelar -------------------------------------------------------------------------

def test_cancelar_una_encolada(cliente, token, base):
    base.corridas[40] = corrida(40, "encolado")
    r = cliente.post("/api/v1/runs/40/cancel?format=json", headers=token())
    assert r.status_code == 200 and r.get_json() == {"id": 40, "status": "cancelado"}
    assert base.canceladas == [(40, 7)]


def test_no_se_cancela_una_que_ya_empezo(cliente, token, base):
    base.corridas[40] = corrida(40, "ejecutando")
    r = cliente.post("/api/v1/runs/40/cancel?format=json", headers=token())
    assert r.status_code == 409 and "ejecutando" in r.get_json()["detail"]


def test_epidemiologo_no_cancela(cliente, token, base):
    base.corridas[40] = corrida(40, "encolado")
    assert cliente.post("/api/v1/runs/40/cancel", headers=token(("EPIDEMIOLOGO",))).status_code == 403
    assert base.canceladas == []


# ---- reintentar -----------------------------------------------------------------------

def test_reintentar_una_fallida_la_encola_con_su_prioridad(cliente, token, base, redis_falso):
    base.corridas[40] = corrida(40, "fallido")
    base.prioridades[40] = "alta"
    r = cliente.post("/api/v1/runs/40/retry?format=json", headers=token(("ADMINISTRADOR",)))
    assert r.status_code == 202
    assert r.get_json() == {"id": 40, "seed": 982314, "priority": "alta", "status": "encolado"}
    assert base.reintentadas == [(40, 7)]
    assert en_cola(redis_falso, prioridad="alta") == [{"id": 40}]


def test_analista_no_reencola_en_alta_la_corrida_del_administrador(cliente, token, base, redis_falso):
    base.corridas[40] = corrida(40, "fallido")
    base.prioridades[40] = "alta"
    r = cliente.post("/api/v1/runs/40/retry?format=json", headers=token(("ANALISTA",)))
    assert r.status_code == 202 and r.get_json()["priority"] == "normal"
    assert en_cola(redis_falso, prioridad="alta") == [] and en_cola(redis_falso) == [{"id": 40}]


def test_redis_caido_al_reintentar_responde_202_porque_ya_quedo_encolada(cliente, token, base, monkeypatch):
    base.corridas[40] = corrida(40, "fallido")

    def caido(*a, **k):
        raise RedisNoDisponible("caído")

    monkeypatch.setattr(rutas.cola, "encolar", caido)
    r = cliente.post("/api/v1/runs/40/retry?format=json", headers=token())
    assert r.status_code == 202 and r.get_json()["status"] == "encolado"
    assert base.corridas[40]["status"] == "encolado"


def test_un_segundo_reintento_es_409_y_no_encola_otra_vez(cliente, token, base, redis_falso):
    base.corridas[40] = corrida(40, "fallido")
    assert cliente.post("/api/v1/runs/40/retry", headers=token()).status_code == 202
    r = cliente.post("/api/v1/runs/40/retry?format=json", headers=token())
    assert r.status_code == 409 and "solo se reintenta una fallida" in r.get_json()["detail"]
    assert len(en_cola(redis_falso)) == 1 and len(base.reintentadas) == 1


@pytest.mark.parametrize("estado", ["encolado", "ejecutando", "completado", "cancelado"])
def test_solo_se_reintenta_una_fallida(cliente, token, base, redis_falso, estado):
    base.corridas[40] = corrida(40, estado)
    assert cliente.post("/api/v1/runs/40/retry", headers=token()).status_code == 409
    assert base.reintentadas == [] and en_cola(redis_falso) == []


def test_epidemiologo_no_reintenta(cliente, token, base):
    base.corridas[40] = corrida(40, "fallido")
    assert cliente.post("/api/v1/runs/40/retry", headers=token(("EPIDEMIOLOGO",))).status_code == 403
    assert base.reintentadas == []


def test_reintentar_una_inexistente_es_404(cliente, token):
    assert cliente.post("/api/v1/runs/404/retry", headers=token()).status_code == 404


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (RAIZ / "docs/contratos/corridas/openapi.json").read_bytes()


def test_las_respuestas_xml_validan_contra_el_xsd(cliente, token, base, monkeypatch):
    base.corridas[41] = corrida(41, "fallido")
    # Las columnas de get_runs_recientes; una corrida sin lote no tiene motor.
    reciente = {"id": 43, "status": "fallido", "seed": 7, "engine": "seir-ref",
                "engine_version": "seir-ref-0.1", "horizon_days": 150,
                "queued_at": datetime(2026, 10, 20, 15, tzinfo=timezone.utc),
                "started_at": datetime(2026, 10, 20, 15, 1, tzinfo=timezone.utc),
                "finished_at": datetime(2026, 10, 20, 15, 2, tzinfo=timezone.utc),
                "error_message": "Error forzado de prueba.", "scenario_version_id": 11,
                "scenario_id": 3, "version_number": 2, "scenario_name": "Ola Influenza ZMM",
                "requested_by_username": "alex.cavazos", "disease_name": "Influenza",
                "region_name": "Monterrey"}
    sin_lote = dict(reciente, id=41, status="encolado", engine=None, engine_version=None, started_at=None,
                    finished_at=None, error_message=None)
    monkeypatch.setattr(datos, "get_runs_recientes", lambda limit=20: [reciente, sin_lote])
    respuestas = [cliente.post("/api/v1/runs", json={"scenario_version_id": 11}, headers=token()),
                  cliente.get("/api/v1/runs/40", headers=token()),
                  cliente.post("/api/v1/runs/40/cancel", headers=token()),
                  cliente.post("/api/v1/runs/41/retry", headers=token()),
                  cliente.get("/api/v1/runs", headers=token())]
    xsd = xmlschema.XMLSchema(str(RAIZ / "docs/contratos/corridas/corrida.xsd"))
    for r in respuestas:
        assert r.status_code in (200, 202) and r.mimetype == "application/xml", r.data
        xsd.validate(r.data.decode("utf-8"))


class Equivalencias:
    """simulation_runs para la ruta de la corrida equivalente."""

    def __init__(self):
        self.filas = {43: {"id": 43, "scenario_version_id": 11, "seed": 7, "scenario_checksum": "abc",
                         "region_id": REGION},
                      44: {"id": 44, "scenario_version_id": 11, "seed": 8, "scenario_checksum": None,
                           "region_id": REGION}}
        self.otras = {(11, 7, 43, "abc"): {"id": 40, "resumen": {"casos_acumulados": 120,
                                                                 "tasa_ataque": 0.25}}}

    def query(self, sql, params, one=False):
        if "WHERE r.id = %s" in sql:
            return self.filas.get(params[0])
        return self.otras.get(tuple(params))


@pytest.fixture
def equivalencias(monkeypatch):
    falsa = Equivalencias()
    monkeypatch.setattr(rutas, "query", falsa.query)
    return falsa


def test_corrida_equivalente(cliente, token, equivalencias):
    r = cliente.get("/api/v1/runs/43/equivalent?format=json", headers=token(("EPIDEMIOLOGO",)))
    assert r.status_code == 200
    assert r.get_json() == {"run_id": 43, "scenario_version_id": 11, "seed": 7,
                            "scenario_checksum": "abc",
                            "equivalente": {"id": 40, "resumen": {"casos_acumulados": 120,
                                                                  "tasa_ataque": 0.25}}}


def test_sin_equivalente_o_sin_huella_es_nulo(cliente, token, equivalencias):
    equivalencias.otras.clear()
    assert cliente.get("/api/v1/runs/43/equivalent?format=json",
                       headers=token()).get_json()["equivalente"] is None
    assert cliente.get("/api/v1/runs/44/equivalent?format=json",
                       headers=token()).get_json()["equivalente"] is None


def test_equivalente_de_una_corrida_inexistente_es_404(cliente, token, equivalencias):
    assert cliente.get("/api/v1/runs/99/equivalent?format=json", headers=token()).status_code == 404
    assert cliente.get("/api/v1/runs/x/equivalent?format=json", headers=token()).status_code == 422


def test_capturista_no_ve_la_equivalente(cliente, token, equivalencias, negados):
    r = cliente.get("/api/v1/runs/43/equivalent?format=json", headers=token(("CAPTURISTA",)))
    assert r.status_code == 403
    assert negados[0][1:4] == ("PERMISSION_DENIED", "corridas", "/api/v1/runs/43/equivalent")
    assert cliente.get("/api/v1/runs/43/equivalent").status_code == 401


def test_la_equivalencia_en_xml_valida_contra_el_xsd(cliente, token, equivalencias):
    xsd = xmlschema.XMLSchema(str(RAIZ / "docs/contratos/corridas/corrida.xsd"))
    con = cliente.get("/api/v1/runs/43/equivalent", headers=token())
    assert con.mimetype == "application/xml"
    xsd.validate(con.data.decode("utf-8"))
    equivalencias.otras.clear()
    xsd.validate(cliente.get("/api/v1/runs/44/equivalent", headers=token()).data.decode("utf-8"))
    assert not xsd.is_valid("<equivalencia><run_id tipo='numero'>1</run_id></equivalencia>")


# ---- alcance por región (D43) y perfiles de solo lectura (D42) ------------------------

@pytest.mark.parametrize("rol", ["INVESTIGADOR", "AUTORIDAD_SANITARIA"])
def test_los_perfiles_de_lectura_consultan_pero_no_lanzan_ni_cancelan(cliente, token, base, rol):
    base.corridas[43] = corrida(43, "encolado")
    assert cliente.get("/api/v1/runs?format=json", headers=token((rol,))).status_code == 200
    assert cliente.get("/api/v1/runs/43?format=json", headers=token((rol,))).status_code == 200
    assert lanzar(cliente, token((rol,)), {"scenario_version_id": VERSION_APROBADA}).status_code == 403
    assert cliente.post("/api/v1/runs/43/cancel", headers=token((rol,))).status_code == 403
    assert base.creadas == [] and base.canceladas == []


def test_una_cuenta_con_alcance_solo_lista_las_corridas_de_sus_regiones(
        cliente, token, base, alcance_falso):
    alcance_falso["regiones"] = [9, 10]
    cliente.get("/api/v1/runs?format=json", headers=token())
    assert base.filtros[-1]["regiones"] == [9, 10]
    alcance_falso["regiones"] = None
    cliente.get("/api/v1/runs?format=json", headers=token())
    assert "regiones" not in base.filtros[-1]


def test_una_corrida_de_otra_region_es_403_en_todas_sus_rutas(
        cliente, token, base, equivalencias, alcance_falso):
    base.corridas[43] = corrida(43, "encolado")
    alcance_falso["regiones"] = [10]
    for metodo, ruta in (("get", "/api/v1/runs/43"), ("get", "/api/v1/runs/43/equivalent"),
                         ("post", "/api/v1/runs/43/cancel"), ("post", "/api/v1/runs/43/retry")):
        r = getattr(cliente, metodo)(ruta + "?format=json", headers=token())
        assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE", ruta
    assert base.canceladas == [] and base.reintentadas == []
    alcance_falso["regiones"] = [REGION]
    assert cliente.get("/api/v1/runs/43?format=json", headers=token()).status_code == 200


def test_no_se_lanza_sobre_una_version_de_otra_region(cliente, token, base, alcance_falso):
    alcance_falso["regiones"] = [10]
    r = lanzar(cliente, token(), {"scenario_version_id": VERSION_APROBADA})
    assert r.status_code == 403 and base.creadas == []
    alcance_falso["regiones"] = [REGION]
    assert lanzar(cliente, token(), {"scenario_version_id": VERSION_APROBADA}).status_code == 202


def test_si_roles_no_responde_las_rutas_con_datos_dan_503(cliente, token, base, monkeypatch):
    from epidemia_comun import alcance
    from epidemia_comun.errores import ErrorAPI

    def caido(*a, **k):
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio no respondió.")

    monkeypatch.setattr(alcance, "llamar", caido)
    assert cliente.get("/api/v1/runs?format=json", headers=token()).status_code == 503


def test_los_motores_habilitados_se_anuncian(cliente, token, monkeypatch):
    monkeypatch.delenv("MOTORES_HABILITADOS", raising=False)
    r = cliente.get("/api/v1/runs/engines?format=json", headers=token())
    assert r.status_code == 200
    assert r.get_json() == {"total": 1, "referencia": "seir-ref", "motores": ["seir-ref"]}
    monkeypatch.setenv("MOTORES_HABILITADOS", "abm-ref, cuda")
    assert cliente.get("/api/v1/runs/engines?format=json", headers=token(("INVESTIGADOR",))).get_json()[
        "motores"] == ["seir-ref", "abm-ref", "abm-gpu"]


def test_los_motores_en_xml_validan_contra_el_xsd(cliente, token, monkeypatch):
    monkeypatch.setenv("MOTORES_HABILITADOS", "abm-ref")
    xsd = xmlschema.XMLSchema(str(RAIZ / "docs/contratos/corridas/corrida.xsd"))
    con = cliente.get("/api/v1/runs/engines", headers=token())
    assert con.mimetype == "application/xml"
    xsd.validate(con.data.decode("utf-8"))


def test_los_motores_piden_sesion_y_rol(cliente, token, negados):
    assert cliente.get("/api/v1/runs/engines").status_code == 401
    assert cliente.get("/api/v1/runs/engines", headers=token(("CAPTURISTA",))).status_code == 403
    assert negados[0][1:4] == ("PERMISSION_DENIED", "corridas", "/api/v1/runs/engines")
