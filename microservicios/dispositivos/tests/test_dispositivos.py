from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from backend_web import dispositivos
from epidemia_comun.formatos import a_xml
from microservicios.dispositivos import rutas

RAIZ = Path(__file__).resolve().parents[3]
PROPIO, AJENO = 3, 9          # el 3 es de quien firma el token (sub 7); el 9, de la cuenta 8
UID = "3f2a9c1e-77b0-4d2e-a1f5-0c9b8e6d4a21"


def dispositivo(device_id, user_id, revocado=False):
    return {"id": device_id, "user_id": user_id, "device_uid": "uid-%08d" % device_id,
            "platform": "android", "model": "Pixel 7", "app_version": "0.1.0",
            "is_revoked": revocado, "last_seen_at": datetime(2026, 10, 31, 16, tzinfo=timezone.utc),
            "created_at": datetime(2026, 10, 31, 16, tzinfo=timezone.utc), "has_push_token": False}


class Mundo:
    """backend_web.dispositivos simulado: guarda lo que le piden."""

    def __init__(self):
        self.filas = {PROPIO: dispositivo(PROPIO, 7), AJENO: dispositivo(AJENO, 8)}
        self.altas, self.listados, self.revocaciones = [], [], []
        self.conflicto, self.creado = None, True

    def registrar_dispositivo(self, user_id, datos, *, contexto):
        self.altas.append((user_id, datos, contexto.user_id))
        if self.conflicto:
            return None, False, self.conflicto
        return dict(dispositivo(10, user_id), device_uid=datos["device_uid"]), self.creado, None

    def listar_dispositivos(self, user_id=None, limite=50):
        self.listados.append((user_id, limite))
        return [f for f in self.filas.values() if user_id is None or f["user_id"] == user_id]

    def get_dispositivo(self, device_id):
        return dict(self.filas[device_id]) if device_id in self.filas else None

    def revocar_dispositivo(self, device_id, *, contexto, user_id=None):
        self.revocaciones.append((device_id, user_id, contexto.user_id))
        if self.filas[device_id]["is_revoked"]:
            return None, "El dispositivo ya estaba revocado."
        self.filas[device_id]["is_revoked"] = True
        return dict(self.filas[device_id]), None


@pytest.fixture
def mundo(monkeypatch):
    m = Mundo()
    for nombre in ("registrar_dispositivo", "listar_dispositivos", "get_dispositivo",
                   "revocar_dispositivo"):
        monkeypatch.setattr(dispositivos, nombre, getattr(m, nombre))
    return m


@pytest.fixture
def cliente(crear_cliente, mundo):
    return crear_cliente("dispositivos")


@pytest.fixture
def admin(token):
    return token(("ADMINISTRADOR",))


# ---- registrar ------------------------------------------------------------------------

def test_sin_token_es_401(cliente):
    assert cliente.post("/api/v1/devices", json={"device_uid": UID}).status_code == 401
    assert cliente.get("/api/v1/devices").status_code == 401


@pytest.mark.parametrize("rol", rutas.ROLES)
def test_cualquier_rol_registra_el_suyo(cliente, token, mundo, rol):
    r = cliente.post("/api/v1/devices?format=json", json={"device_uid": UID, "model": "Pixel 7"},
                     headers=token((rol,)))
    assert r.status_code == 201
    assert r.get_json()["device_uid"] == UID and r.get_json()["user_id"] == 7
    assert mundo.altas == [(7, {"device_uid": UID, "model": "Pixel 7"}, 7)]


def test_si_ya_era_suyo_responde_200(cliente, token, mundo):
    mundo.creado = False
    assert cliente.post("/api/v1/devices", json={"device_uid": UID}, headers=token()).status_code == 200


def test_acepta_xml(cliente, token, mundo):
    r = cliente.post("/api/v1/devices", headers={**token(), "Content-Type": "application/xml"},
                     data=a_xml({"device_uid": UID, "platform": "ios"}, "solicitud"))
    assert r.status_code == 201 and r.mimetype == "application/xml"
    assert ET.fromstring(r.data).findtext("device_uid") == UID
    assert mundo.altas[0][1] == {"device_uid": UID, "platform": "ios"}


def test_de_otra_cuenta_o_revocado_es_409(cliente, token, mundo):
    mundo.conflicto = "Ese dispositivo está registrado en otra cuenta."
    r = cliente.post("/api/v1/devices?format=json", json={"device_uid": UID}, headers=token())
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"
    assert "otra cuenta" in r.get_json()["detail"]


@pytest.mark.parametrize("cuerpo", [{}, {"device_uid": "corto"}, {"device_uid": UID, "platform": "nokia"},
                                    {"device_uid": UID, "imei": "35"}, ["no", "es", "objeto"]])
def test_cuerpo_invalido_es_422_sin_registrar(cliente, token, mundo, cuerpo):
    r = cliente.post("/api/v1/devices?format=json", json=cuerpo, headers=token())
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"
    assert mundo.altas == []


# ---- listar ---------------------------------------------------------------------------

def test_cada_quien_ve_los_suyos(cliente, token, mundo):
    r = cliente.get("/api/v1/devices?format=json", headers=token(("CAPTURISTA",)))
    assert r.status_code == 200
    assert [d["id"] for d in r.get_json()["dispositivos"]] == [PROPIO]
    assert mundo.listados == [(7, rutas.LIMITE)]
    assert cliente.get("/api/v1/devices?user_id=7", headers=token()).status_code == 200


def test_ver_los_de_otra_cuenta_es_solo_de_administrador(cliente, token, admin, mundo):
    r = cliente.get("/api/v1/devices?user_id=8&format=json", headers=token(("EPIDEMIOLOGO",)))
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"
    assert cliente.get("/api/v1/devices?user_id=8", headers=admin).status_code == 200
    assert cliente.get("/api/v1/devices?limit=5", headers=admin).status_code == 200
    assert mundo.listados == [(8, rutas.LIMITE), (None, 5)]


def test_lista_en_xml_con_un_elemento_por_dispositivo(cliente, admin):
    raiz = ET.fromstring(cliente.get("/api/v1/devices", headers=admin).data)
    assert raiz.tag == "listado"
    assert [d.findtext("id") for d in raiz.findall("dispositivos/dispositivo")] == ["3", "9"]


@pytest.mark.parametrize("consulta", ["limit=0", "limit=%d" % (rutas.LIMITE_MAX + 1), "user_id=x"])
def test_consulta_invalida_es_422(cliente, token, consulta):
    assert cliente.get("/api/v1/devices?" + consulta, headers=token()).status_code == 422


# ---- consultar y revocar --------------------------------------------------------------

def test_consultar_el_propio_y_el_ajeno_no_existe(cliente, token, admin):
    assert cliente.get("/api/v1/devices/%d" % PROPIO, headers=token()).status_code == 200
    r = cliente.get("/api/v1/devices/%d?format=json" % AJENO, headers=token())
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"
    assert cliente.get("/api/v1/devices/%d" % AJENO, headers=admin).status_code == 200
    assert cliente.get("/api/v1/devices/404", headers=admin).status_code == 404
    assert cliente.get("/api/v1/devices/x", headers=admin).status_code == 422


def test_revocar_el_propio(cliente, token, mundo):
    r = cliente.post("/api/v1/devices/%d/revoke?format=json" % PROPIO, headers=token(("CAPTURISTA",)))
    assert r.status_code == 200 and r.get_json()["is_revoked"] is True
    assert mundo.revocaciones == [(PROPIO, 7, 7)]
    r = cliente.post("/api/v1/devices/%d/revoke?format=json" % PROPIO, headers=token(("CAPTURISTA",)))
    assert r.status_code == 409 and "ya estaba" in r.get_json()["detail"]


def test_revocar_el_ajeno_es_404_salvo_para_administrador(cliente, token, admin, mundo):
    assert cliente.post("/api/v1/devices/%d/revoke" % AJENO, headers=token()).status_code == 404
    assert mundo.revocaciones == []
    assert cliente.post("/api/v1/devices/%d/revoke" % AJENO, headers=admin).status_code == 200
    assert mundo.revocaciones == [(AJENO, None, 7)]


def test_redis_caido_es_503(cliente, token, apagar_redis):
    cabeceras = token()
    apagar_redis()
    assert cliente.get("/api/v1/devices", headers=cabeceras).status_code == 503


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (RAIZ / "docs/contratos/dispositivos/openapi.json").read_bytes()
