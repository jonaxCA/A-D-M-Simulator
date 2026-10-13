from xml.etree import ElementTree as ET

import jwt
import pytest

from backend_web import auth
from epidemia_comun import sesiones
from epidemia_comun.seguridad import verificar_token
from microservicios.auth import rutas

CUENTA = {"id": 7, "username": "analista1", "full_name": "Ana Lista", "roles": ["ANALISTA"]}


@pytest.fixture
def bitacora(monkeypatch):
    eventos = []
    monkeypatch.setattr(rutas, "log_audit",
                        lambda ctx, accion, entidad, entity_id=None, **_:
                        eventos.append((ctx.user_id, accion, entity_id)))
    return eventos


@pytest.fixture
def cliente(crear_cliente, monkeypatch, bitacora):
    def intento(usuario, password):
        if usuario == "analista1" and password == "correcta":
            return dict(CUENTA), None
        return None, auth.MENSAJE_CREDENCIALES
    monkeypatch.setattr(auth, "attempt_login", intento)
    return crear_cliente("auth")


def resolver(cliente, redis_falso):
    datos = cliente.get("/api/v1/auth/captcha?format=json").get_json()
    a, b = (int(x) for x in datos["pregunta"].split(" + "))
    assert redis_falso.ttl(rutas.llave_captcha(datos["captcha_id"])) > 0
    return datos["captcha_id"], str(a + b)


def login(cliente, redis_falso, usuario="analista1", password="correcta", respuesta=None):
    captcha_id, correcta = resolver(cliente, redis_falso)
    return cliente.post("/api/v1/auth/login?format=json", json={
        "usuario": usuario, "password": password, "captcha_id": captcha_id,
        "captcha_respuesta": correcta if respuesta is None else respuesta})


def test_captcha_en_xml_por_omision(cliente):
    r = cliente.get("/api/v1/auth/captcha")
    assert r.content_type.startswith("application/xml")
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "captcha" and raiz.findtext("captcha_id")


def test_login_emite_access_que_acepta_la_biblioteca(cliente, redis_falso, bitacora):
    r = login(cliente, redis_falso)
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["usuario"]["roles"] == ["ANALISTA"] and datos["expires_in"] == 1200
    claims = verificar_token(datos["access_token"], cliente.application.config,
                             redis_falso, roles=("ANALISTA",))
    assert set(claims) >= {"iss", "aud", "sub", "roles", "sid", "jti", "iat", "nbf", "exp"}
    assert claims["sub"] == "7"
    assert sesiones.renovar(datos["refresh_token"])["usuario"] == 7
    assert bitacora == [(7, "LOGIN", "7")]


def test_login_acepta_cuerpo_xml(cliente, redis_falso):
    captcha_id, correcta = resolver(cliente, redis_falso)
    cuerpo = ("<login><usuario>analista1</usuario><password>correcta</password>"
              "<captcha_id>%s</captcha_id><captcha_respuesta>%s</captcha_respuesta></login>"
              % (captcha_id, correcta))
    r = cliente.post("/api/v1/auth/login", data=cuerpo, content_type="application/xml")
    assert r.status_code == 200
    assert ET.fromstring(r.data).findtext("token_type") == "Bearer"


def test_password_equivocada_es_401_y_se_audita(cliente, redis_falso, bitacora):
    r = login(cliente, redis_falso, password="mala")
    assert r.status_code == 401
    assert r.get_json()["codigo"] == "CREDENCIALES_INVALIDAS"
    assert r.get_json()["detail"] == auth.MENSAJE_CREDENCIALES
    assert bitacora == [(None, "LOGIN_FAILED", "analista1")]


def test_captcha_equivocado_no_revisa_la_password(cliente, redis_falso, bitacora, monkeypatch):
    monkeypatch.setattr(auth, "attempt_login", lambda *a: pytest.fail("no debió llamarse"))
    r = login(cliente, redis_falso, respuesta="999")
    assert r.status_code == 422
    assert bitacora == []


def test_captcha_sirve_una_sola_vez(cliente, redis_falso):
    captcha_id, correcta = resolver(cliente, redis_falso)
    cuerpo = {"usuario": "analista1", "password": "correcta",
              "captcha_id": captcha_id, "captcha_respuesta": correcta}
    assert cliente.post("/api/v1/auth/login?format=json", json=cuerpo).status_code == 200
    assert cliente.post("/api/v1/auth/login?format=json", json=cuerpo).status_code == 422


@pytest.mark.parametrize("falta", ["usuario", "password", "captcha_id", "captcha_respuesta"])
def test_campo_faltante_es_422(cliente, falta):
    cuerpo = {"usuario": "a", "password": "b", "captcha_id": "c", "captcha_respuesta": "1"}
    del cuerpo[falta]
    r = cliente.post("/api/v1/auth/login?format=json", json=cuerpo)
    assert r.status_code == 422


def test_redis_caido_es_503(cliente, apagar_redis):
    apagar_redis()
    r = cliente.get("/api/v1/auth/captcha?format=json")
    assert r.status_code == 503
    assert r.get_json()["codigo"] == "SERVICIO_NO_DISPONIBLE"


def test_el_token_no_lleva_datos_de_mas(cliente, redis_falso):
    token = login(cliente, redis_falso).get_json()["access_token"]
    claims = jwt.decode(token, options={"verify_signature": False})
    assert "password" not in claims and "password_hash" not in claims


def test_contrato_servido_es_el_de_docs(cliente):
    from microservicios.auth.app import CONTRATO
    r = cliente.get("/openapi.json")
    assert r.data == CONTRATO.read_bytes()
    assert set(r.get_json()["paths"]) == {"/api/v1/auth/captcha", "/api/v1/auth/login"}
