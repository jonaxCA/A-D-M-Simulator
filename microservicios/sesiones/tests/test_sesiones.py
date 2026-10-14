import time
import uuid
from xml.etree import ElementTree as ET

import jwt
import pytest

from epidemia_comun import sesiones
from microservicios.sesiones import rutas
from microservicios.sesiones.rutas import emitir_access

SECRETO = "secreto-solo-para-pruebas-unitarias-0123456789"


@pytest.fixture
def bitacora(monkeypatch):
    eventos = []
    monkeypatch.setattr(rutas, "log_audit",
                        lambda ctx, accion, entidad, entity_id=None, **_:
                        eventos.append((ctx.user_id, accion, entity_id)))
    return eventos


@pytest.fixture
def cliente(crear_cliente, bitacora):
    return crear_cliente("sesiones")


@pytest.fixture
def login(cliente):
    """Lo que entrega auth: una sesión abierta en Redis, su access y su refresh."""
    def abrir(usuario=7, roles=("ANALISTA",)):
        sesion = sesiones.abrir(usuario, list(roles), ttl=600)
        access = emitir_access(usuario, roles, sesion["sid"], cliente.application.config)
        return {"Authorization": "Bearer " + access}, sesion["refresh"]
    return abrir


def token_servicio(**cambios):
    ahora = int(time.time())
    claims = {"iss": "epidemia-auth", "aud": "epidemia-interno", "sub": "usuarios",
              "jti": str(uuid.uuid4()), "iat": ahora, "nbf": ahora, "exp": ahora + 60}
    claims.update(cambios)
    return {"Authorization": "Bearer " + jwt.encode(claims, SECRETO, algorithm="HS256")}


def test_current_dice_quien_soy(cliente, login):
    cabecera, _ = login(roles=("EPIDEMIOLOGO", "ADMINISTRADOR"))
    r = cliente.get("/api/v1/sessions/current?format=json", headers=cabecera)
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["usuario"] == 7
    assert datos["roles"] == ["EPIDEMIOLOGO", "ADMINISTRADOR"]
    assert datos["expira"] > datos["creada"] and datos["access_expira"] > 0


def test_current_en_xml_por_omision(cliente, login):
    cabecera, _ = login()
    r = cliente.get("/api/v1/sessions/current", headers=cabecera)
    assert r.content_type.startswith("application/xml")
    assert ET.fromstring(r.data).findtext("usuario") == "7"


def test_current_sin_token_es_401(cliente):
    r = cliente.get("/api/v1/sessions/current?format=json")
    assert r.status_code == 401
    assert r.get_json()["codigo"] == "TOKEN_AUSENTE"


def test_refresh_rota_y_el_nuevo_access_sirve(cliente, login):
    _, refresh = login()
    r = cliente.post("/api/v1/sessions/refresh?format=json", json={"refresh_token": refresh})
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["refresh_token"] != refresh and datos["expires_in"] == 1200
    nuevo = {"Authorization": "Bearer " + datos["access_token"]}
    assert cliente.get("/api/v1/sessions/current?format=json", headers=nuevo).status_code == 200


def test_refresh_acepta_cuerpo_xml(cliente, login):
    _, refresh = login()
    r = cliente.post("/api/v1/sessions/refresh",
                     data="<refresh><refresh_token>%s</refresh_token></refresh>" % refresh,
                     content_type="application/xml")
    assert r.status_code == 200
    assert ET.fromstring(r.data).findtext("token_type") == "Bearer"


def test_refresh_reutilizado_cierra_la_sesion(cliente, login):
    cabecera, refresh = login()
    cliente.post("/api/v1/sessions/refresh?format=json", json={"refresh_token": refresh})
    r = cliente.post("/api/v1/sessions/refresh?format=json", json={"refresh_token": refresh})
    assert r.status_code == 401
    assert r.get_json()["codigo"] == "TOKEN_REVOCADO"
    assert cliente.get("/api/v1/sessions/current?format=json", headers=cabecera).status_code == 401


@pytest.mark.parametrize("cuerpo", [{}, {"refresh_token": ""}, {"refresh_token": 5}])
def test_refresh_faltante_es_422(cliente, cuerpo):
    assert cliente.post("/api/v1/sessions/refresh?format=json", json=cuerpo).status_code == 422


def test_refresh_desconocido_es_401(cliente):
    r = cliente.post("/api/v1/sessions/refresh?format=json", json={"refresh_token": "x.y"})
    assert r.status_code == 401
    assert r.get_json()["codigo"] == "TOKEN_INVALIDO"


def test_logout_revoca_el_access_y_cierra_la_sesion(cliente, login, bitacora):
    cabecera, refresh = login()
    r = cliente.post("/api/v1/sessions/logout?format=json", headers=cabecera)
    assert r.status_code == 200
    assert bitacora == [(7, "LOGOUT", "7")]
    assert cliente.get("/api/v1/sessions/current?format=json", headers=cabecera).status_code == 401
    r = cliente.post("/api/v1/sessions/refresh?format=json", json={"refresh_token": refresh})
    assert r.status_code == 401


def test_ruta_interna_cierra_todas_las_sesiones(cliente, login):
    a, _ = login()
    b, _ = login()
    otro, _ = login(usuario=8)
    r = cliente.delete("/api/v1/sessions/user/7?format=json", headers=token_servicio())
    assert r.status_code == 200
    assert r.get_json() == {"usuario": 7, "cerradas": 2}
    assert cliente.get("/api/v1/sessions/current?format=json", headers=a).status_code == 401
    assert cliente.get("/api/v1/sessions/current?format=json", headers=b).status_code == 401
    assert cliente.get("/api/v1/sessions/current?format=json", headers=otro).status_code == 200


def test_ruta_interna_rechaza_el_token_de_una_persona(cliente, login):
    cabecera, _ = login(roles=("ADMINISTRADOR",))
    r = cliente.delete("/api/v1/sessions/user/7?format=json", headers=cabecera)
    assert r.status_code == 401


@pytest.mark.parametrize("valor", ["0", "abc", "-3"])
def test_ruta_interna_id_invalido_es_422(cliente, valor):
    r = cliente.delete("/api/v1/sessions/user/%s?format=json" % valor, headers=token_servicio())
    assert r.status_code == 422


def test_redis_caido_es_503(cliente, apagar_redis):
    apagar_redis()
    r = cliente.post("/api/v1/sessions/refresh?format=json", json={"refresh_token": "x.y"})
    assert r.status_code == 503
    assert r.get_json()["codigo"] == "SERVICIO_NO_DISPONIBLE"


def test_contrato_servido_es_el_de_docs(cliente):
    from microservicios.sesiones.app import CONTRATO
    r = cliente.get("/openapi.json")
    assert r.data == CONTRATO.read_bytes()
    assert set(r.get_json()["paths"]) == {
        "/api/v1/sessions/refresh", "/api/v1/sessions/logout",
        "/api/v1/sessions/current", "/api/v1/sessions/user/{id}"}
