from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from backend_web import notificaciones
from epidemia_comun.seguridad import token_servicio

RAIZ = Path(__file__).resolve().parents[3]
CREADA = datetime(2026, 10, 20, 15, tzinfo=timezone.utc)


class Bandeja:
    """La tabla notifications simulada, con las reglas de backend_web.notificaciones."""

    def __init__(self):
        self.filas = {1: self.fila(1, 7), 2: self.fila(2, 8)}
        self.contextos = []

    @staticmethod
    def fila(notificacion_id, user_id):
        return {"id": notificacion_id, "user_id": user_id, "type": "RUN_FINISHED",
                "title": "La corrida SIM-00042 terminó", "body": "Ola Influenza ZMM, versión 2.",
                "payload": {"run_id": 42}, "read_at": None, "created_at": CREADA}

    def listar(self, user_id, solo_no_leidas=False, limite=50):
        filas = [dict(f) for f in self.filas.values() if f["user_id"] == user_id
                 and not (solo_no_leidas and f["read_at"])]
        return filas[:limite], sum(1 for f in filas if not f["read_at"])

    def marcar(self, notificacion_id, user_id, *, contexto):
        fila = self.filas.get(notificacion_id)
        if not fila or fila["user_id"] != user_id:
            return None, "No existe la notificación."
        fila["read_at"] = fila["read_at"] or CREADA
        self.contextos.append(contexto)
        return dict(fila), None

    def crear(self, datos, *, contexto):
        errores = notificaciones.valida_notificacion(datos)
        if errores:
            return None, " ".join(errores)
        if datos["user_id"] == 404:
            return None, "No existe el usuario destinatario."
        nuevo = max(self.filas) + 1
        self.filas[nuevo] = dict(self.fila(nuevo, datos["user_id"]), **datos)
        self.contextos.append(contexto)
        return nuevo, None


@pytest.fixture
def bandeja(monkeypatch):
    b = Bandeja()
    monkeypatch.setattr(notificaciones, "listar_notificaciones", b.listar)
    monkeypatch.setattr(notificaciones, "marcar_leida", b.marcar)
    monkeypatch.setattr(notificaciones, "crear_notificacion", b.crear)
    return b


@pytest.fixture
def cliente(crear_cliente, bandeja):
    return crear_cliente("notificaciones")


@pytest.fixture
def servicio(cliente):
    return {"Authorization": "Bearer " + token_servicio(cliente.application.config, "simulador")}


AVISO = {"user_id": 7, "type": "RUN_FAILED", "title": "La corrida SIM-00043 falló",
         "body": "Error forzado de prueba.", "payload": {"run_id": 43}}


# ---- leer -----------------------------------------------------------------------------

def test_sin_token_es_401(cliente):
    assert cliente.get("/api/v1/notifications").status_code == 401


@pytest.mark.parametrize("rol", ["CAPTURISTA", "ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR"])
def test_cada_quien_ve_solo_las_suyas(cliente, token, rol):
    datos = cliente.get("/api/v1/notifications?format=json", headers=token((rol,))).get_json()
    assert datos["total"] == 1 and datos["no_leidas"] == 1
    assert [n["id"] for n in datos["notificaciones"]] == [1]


def test_en_xml_cada_aviso_es_una_notificacion(cliente, token):
    r = cliente.get("/api/v1/notifications", headers=token())
    assert r.mimetype == "application/xml"
    assert [n.findtext("id") for n in ET.fromstring(r.data).findall("notificaciones/notificacion")] == ["1"]


@pytest.mark.parametrize("consulta", ["unread=si", "limit=0", "limit=201"])
def test_filtros_invalidos_son_422(cliente, token, consulta):
    assert cliente.get("/api/v1/notifications?" + consulta, headers=token()).status_code == 422


def test_marcar_leida_la_propia(cliente, token, bandeja):
    r = cliente.post("/api/v1/notifications/1/read?format=json", headers=token())
    assert r.status_code == 200 and r.get_json()["read_at"].startswith("2026-10-20")
    assert bandeja.contextos[0].user_id == 7
    datos = cliente.get("/api/v1/notifications?unread=true&format=json", headers=token()).get_json()
    assert datos["total"] == 0


def test_la_de_otra_persona_es_404(cliente, token, bandeja):
    assert cliente.post("/api/v1/notifications/2/read", headers=token()).status_code == 404
    assert bandeja.filas[2]["read_at"] is None


# ---- crear (ruta interna) -------------------------------------------------------------

def test_crear_con_token_de_servicio(cliente, servicio, bandeja):
    r = cliente.post("/api/v1/notifications?format=json", json=AVISO, headers=servicio)
    assert r.status_code == 201
    assert r.get_json() == {"id": 3, "user_id": 7, "type": "RUN_FAILED"}
    contexto = bandeja.contextos[0]
    assert contexto.user_id is None and contexto.user_agent == "servicio simulador"


@pytest.mark.parametrize("roles", [("ADMINISTRADOR",), ("ANALISTA",)])
def test_una_persona_no_crea_avisos(cliente, token, bandeja, roles):
    r = cliente.post("/api/v1/notifications?format=json", json=AVISO, headers=token(roles))
    assert r.status_code == 401
    assert len(bandeja.filas) == 2


def test_crear_en_xml(cliente, servicio):
    r = cliente.post("/api/v1/notifications", headers={**servicio, "Content-Type": "application/xml"},
                     data="<solicitud><user_id>7</user_id><type>SCENARIO_APPROVED</type>"
                          "<title>Versión 2 aprobada</title></solicitud>".encode("utf-8"))
    assert r.status_code == 201 and ET.fromstring(r.data).findtext("type") == "SCENARIO_APPROVED"


@pytest.mark.parametrize("cuerpo", [dict(AVISO, type="OTRO"), dict(AVISO, title=" "),
                                    dict(AVISO, payload=[1]), dict(AVISO, user_id="x"),
                                    dict(AVISO, entity_id=11)])
def test_aviso_invalido_es_422(cliente, servicio, cuerpo):
    r = cliente.post("/api/v1/notifications?format=json", json=cuerpo, headers=servicio)
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"


def test_destinatario_inexistente_es_404(cliente, servicio):
    r = cliente.post("/api/v1/notifications?format=json", json=dict(AVISO, user_id=404),
                     headers=servicio)
    assert r.status_code == 404


def test_redis_caido_es_503(cliente, token, apagar_redis):
    cabeceras = token()
    apagar_redis()
    assert cliente.get("/api/v1/notifications", headers=cabeceras).status_code == 503


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (RAIZ / "docs/contratos/notificaciones/openapi.json").read_bytes()
