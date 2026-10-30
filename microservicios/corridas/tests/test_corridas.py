import json
from datetime import date, datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import xmlschema

from backend_web import queries
from epidemia_comun import llaves
from epidemia_comun.redis_compartido import RedisNoDisponible
from microservicios.corridas import rutas

RAIZ = Path(__file__).resolve().parents[3]
VERSION_APROBADA, VERSION_BORRADOR = 11, 12


class Base:
    """Las corridas de una base simulada, con las reglas de crear_corrida y cancelar_run.
    `motores` guarda el motor y la versión con que se creó cada corrida."""

    def __init__(self):
        self.corridas, self.creadas, self.canceladas, self.motores = {}, [], [], {}

    def crear_corrida(self, version_id, seed, user_id, engine_version, *, engine="python-ref",
                      contexto=None, forzar_error=False):
        if version_id not in (VERSION_APROBADA, VERSION_BORRADOR):
            return None, None, "La versión de escenario no existe."
        if version_id == VERSION_BORRADOR:
            return None, None, ("Esta versión no está aprobada (estado: borrador); solo se pueden "
                                "ejecutar simulaciones sobre versiones aprobadas.")
        run_id = 40 + len(self.creadas)
        self.creadas.append((version_id, seed, user_id, contexto.user_id, forzar_error))
        self.motores[run_id] = (engine, engine_version)
        self.corridas[run_id] = corrida(run_id, "encolado")
        return run_id, 90 + len(self.creadas), None

    def get_run(self, run_id):
        return dict(self.corridas[run_id]) if run_id in self.corridas else None

    def get_motor_run(self, run_id):
        if run_id not in self.corridas:
            return None
        return self.motores.get(run_id, ("python-ref",))[0]

    def cancelar_run(self, run_id, *, contexto):
        if self.corridas.get(run_id, {}).get("status") != "encolado":
            return False
        self.corridas[run_id]["status"] = "cancelado"
        self.canceladas.append((run_id, contexto.user_id))
        return True


def corrida(run_id, status, progress=0):
    return {"id": run_id, "batch_id": 90, "scenario_version_id": VERSION_APROBADA, "seed": 982314,
            "status": status, "progress": progress, "engine_version": "python-ref-0.1",
            "queued_at": datetime(2026, 10, 20, 15, tzinfo=timezone.utc), "started_at": None,
            "finished_at": None, "error_message": None, "requested_by": 7, "version_number": 2,
            "scenario_id": 3, "version_status": "aprobado", "population_size": 500000,
            "horizon_days": 120, "initial_infected": 100, "scenario_name": "Ola Influenza ZMM",
            "disease_id": 1, "disease_name": "Influenza A", "region_id": 9,
            "region_name": "Monterrey", "requested_by_username": "alex.cavazos",
            "requested_by_nombre": "Alex Cavazos"}


@pytest.fixture
def base(monkeypatch):
    b = Base()
    for nombre in ("crear_corrida", "get_run", "cancelar_run", "get_motor_run"):
        monkeypatch.setattr(queries, nombre, getattr(b, nombre))
    b.filtros = []

    def recientes(limit=20, **filtros):
        b.filtros.append(filtros)
        return [{"id": i, "status": "completado"} for i in range(limit)]

    monkeypatch.setattr(queries, "get_runs_recientes", recientes)
    return b


@pytest.fixture
def cliente(crear_cliente, base):
    return crear_cliente("corridas")


def lanzar(cliente, cabeceras, cuerpo):
    return cliente.post("/api/v1/runs?format=json", json=cuerpo, headers=cabeceras)


def en_cola(redis_falso, motor="python-ref"):
    # LPUSH y BRPOP: el que se toma primero está al final de la lista.
    llave = llaves.cola_simulaciones(motor)
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
                            "engine": "python-ref", "forzar_error": False, "status": "encolado"}
    assert base.creadas == [(11, 0, 7, 7, False)]
    assert base.motores == {40: ("python-ref", "python-ref-0.1")}
    assert en_cola(redis_falso) == [{"id": 40, "forzar_error": False}]
    # El candado se suelta al terminar.
    assert redis_falso.get(llaves.candado_corrida(11)) is None


def test_un_motor_no_habilitado_es_422(cliente, token, base, redis_falso, monkeypatch):
    monkeypatch.delenv("MOTORES_HABILITADOS", raising=False)
    r = lanzar(cliente, token(), {"scenario_version_id": 11, "engine": "cuda"})
    assert r.status_code == 422 and r.get_json()["detail"] == "engine debe ser uno de: python-ref."
    assert base.creadas == [] and en_cola(redis_falso, "cuda") == []


def test_un_motor_habilitado_va_a_su_propia_cola(cliente, token, base, redis_falso, monkeypatch):
    monkeypatch.setenv("MOTORES_HABILITADOS", " cuda ,gpu")
    r = lanzar(cliente, token(), {"scenario_version_id": 11, "engine": "cuda"})
    assert r.status_code == 202 and r.get_json()["engine"] == "cuda"
    # La versión de cuda no la sabe corridas: la pone su simulador.
    assert base.motores == {40: ("cuda", None)}
    assert en_cola(redis_falso, "cuda") == [{"id": 40, "forzar_error": False}]
    assert en_cola(redis_falso) == []
    # Un nombre que la base no acepta no se habilita aunque venga en la variable.
    assert rutas.motores_habilitados() == ["python-ref", "cuda"]
    assert lanzar(cliente, token(), {"scenario_version_id": 11, "engine": "gpu"}).status_code == 422


def test_semilla_aleatoria_si_no_llega(cliente, token, base):
    r = lanzar(cliente, token(), {"scenario_version_id": VERSION_APROBADA})
    assert 0 <= r.get_json()["seed"] <= rutas.SEMILLA_MAX


def test_forzar_error_solo_para_administrador(cliente, token, base, redis_falso):
    lanzar(cliente, token(("ANALISTA",)), {"scenario_version_id": 11, "forzar_error": True})
    lanzar(cliente, token(("ADMINISTRADOR",)), {"scenario_version_id": 11, "forzar_error": True})
    assert [c[4] for c in base.creadas] == [False, True]
    assert [p["forzar_error"] for p in en_cola(redis_falso)] == [False, True]


def test_acepta_xml(cliente, token, base):
    r = cliente.post("/api/v1/runs", headers={**token(), "Content-Type": "application/xml"},
                     data=b"<solicitud><scenario_version_id>11</scenario_version_id>"
                          b"<seed>5</seed><engine>python-ref</engine>"
                          b"<forzar_error>false</forzar_error></solicitud>")
    assert r.status_code == 202 and r.mimetype == "application/xml"
    assert ET.fromstring(r.data).findtext("seed") == "5"
    assert ET.fromstring(r.data).findtext("engine") == "python-ref"


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
                    "&engine=cuda&from=2026-10-01&to=2026-10-20", headers=token())
    assert r.status_code == 200
    # cuda no está habilitado para lanzar, pero sus corridas se pueden buscar.
    assert base.filtros == [{"scenario_id": 3, "scenario_version_id": 11, "status": "fallido",
                             "engine": "cuda", "desde": date(2026, 10, 1),
                             "hasta": date(2026, 10, 20)}]


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


def test_consultar_dice_el_motor(cliente, token, base):
    base.corridas[40] = corrida(40, "encolado")
    base.motores[40] = ("cuda", None)
    assert cliente.get("/api/v1/runs/40?format=json", headers=token()).get_json()["engine"] == "cuda"


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


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (RAIZ / "docs/contratos/corridas/openapi.json").read_bytes()


def test_las_respuestas_xml_validan_contra_el_xsd(cliente, token, base, monkeypatch):
    # Las columnas de get_runs_recientes; una corrida sin lote no tiene motor.
    reciente = {"id": 43, "status": "fallido", "seed": 7, "engine": "python-ref",
                "queued_at": datetime(2026, 10, 20, 15, tzinfo=timezone.utc),
                "started_at": datetime(2026, 10, 20, 15, 1, tzinfo=timezone.utc),
                "finished_at": datetime(2026, 10, 20, 15, 2, tzinfo=timezone.utc),
                "error_message": "Error forzado de prueba.", "scenario_version_id": 11,
                "scenario_id": 3, "version_number": 2, "scenario_name": "Ola Influenza ZMM",
                "requested_by_username": "alex.cavazos"}
    sin_lote = dict(reciente, id=41, status="encolado", engine=None, started_at=None,
                    finished_at=None, error_message=None)
    monkeypatch.setattr(queries, "get_runs_recientes", lambda limit=20: [reciente, sin_lote])
    respuestas = [cliente.post("/api/v1/runs", json={"scenario_version_id": 11}, headers=token()),
                  cliente.get("/api/v1/runs/40", headers=token()),
                  cliente.post("/api/v1/runs/40/cancel", headers=token()),
                  cliente.get("/api/v1/runs", headers=token())]
    xsd = xmlschema.XMLSchema(str(RAIZ / "docs/contratos/corridas/corrida.xsd"))
    for r in respuestas:
        assert r.status_code in (200, 202) and r.mimetype == "application/xml", r.data
        xsd.validate(r.data.decode("utf-8"))
