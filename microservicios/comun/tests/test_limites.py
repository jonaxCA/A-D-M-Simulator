import json

import pytest
from flask import Flask

from epidemia_comun import llaves, limites
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.seguridad import requiere_token

RUTA = "/api/v1/prueba"


@pytest.fixture
def cliente(redis_falso):
    app = Flask("prueba")
    app.config.update(NOMBRE_SERVICIO="series", JWT_SECRET_KEY="secreto-solo-para-pruebas-unitarias-0123456789",
                      JWT_ISSUER="epidemia-auth", JWT_AUDIENCE="epidemia-api",
                      JWT_AUDIENCE_INTERNA="epidemia-interno")
    app.extensions["epidemia_redis"] = redis_falso
    app.errorhandler(ErrorAPI)(respuesta_error)

    @app.get(RUTA)
    @requiere_token()
    def ver():
        return "ok"

    return app.test_client()


def test_excedido_da_429_con_retry_after(cliente, token, monkeypatch):
    monkeypatch.setenv("LIMITE_NORMAL", "3/60")
    ruta = RUTA
    cabeceras = token()
    estados = [cliente.get(ruta, headers=cabeceras).status_code for _ in range(3)]
    assert 429 not in estados
    r = cliente.get(ruta + "?format=json", headers=cabeceras)
    assert r.status_code == 429
    assert json.loads(r.data)["codigo"] == "LIMITE_EXCEDIDO"
    assert 0 < int(r.headers["Retry-After"]) <= 60


def test_usuarios_no_comparten_contador(cliente, token, monkeypatch):
    monkeypatch.setenv("LIMITE_NORMAL", "1/60")
    ruta = RUTA
    assert cliente.get(ruta, headers=token(sub="7")).status_code != 429
    assert cliente.get(ruta, headers=token(sub="7")).status_code == 429
    assert cliente.get(ruta, headers=token(sub="8")).status_code != 429


def test_la_ventana_vence(cliente, token, redis_falso, monkeypatch):
    monkeypatch.setenv("LIMITE_NORMAL", "1/60")
    ruta = RUTA
    redis_falso.flushall()
    cabeceras = token()
    cliente.get(ruta, headers=cabeceras)
    assert cliente.get(ruta, headers=cabeceras).status_code == 429
    llave = llaves.limite("7", "GET:" + ruta)
    assert 0 < redis_falso.ttl(llave) <= 60
    redis_falso.delete(llave)
    assert cliente.get(ruta, headers=cabeceras).status_code != 429


def test_el_429_respeta_xml(cliente, token, monkeypatch):
    monkeypatch.setenv("LIMITE_NORMAL", "1/60")
    ruta = RUTA
    cabeceras = token()
    cliente.get(ruta, headers=cabeceras)
    r = cliente.get(ruta + "?format=xml", headers=cabeceras)
    assert r.status_code == 429
    assert r.content_type.startswith("application/problem+xml")
    assert "Retry-After" in r.headers


def test_sin_redis_sigue_el_503_de_la_sesion(cliente, token, apagar_redis):
    ruta = RUTA
    cabeceras = token()
    apagar_redis()
    assert cliente.get(ruta, headers=cabeceras).status_code == 503


def test_perfiles_por_servicio():
    assert limites.perfil_de("corridas", "POST") == "estricto"
    assert limites.perfil_de("corridas", "GET") == "normal"
    assert limites.perfil_de("casos", "POST") == "permisivo"
    assert limites.perfil_de("series", "GET") == "normal"
    assert limites.cifras("estricto")[0] < limites.cifras("normal")[0] < limites.cifras("permisivo")[0]


def test_cifras_por_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("LIMITE_ESTRICTO", "2/30")
    assert limites.cifras("estricto") == (2, 30)
    monkeypatch.setenv("LIMITE_ESTRICTO", "basura")
    assert limites.cifras("estricto") == (10, 60)


def test_ruta_publica_va_por_ip(crear_cliente, redis_falso, monkeypatch):
    monkeypatch.setenv("LIMITE_NORMAL", "2/60")
    cliente = crear_cliente("auth")
    estados = [cliente.get("/api/v1/auth/captcha").status_code for _ in range(3)]
    assert estados[2] == 429 and 429 not in estados[:2]
    assert any(k.startswith("ratelimit:ip-") for k in redis_falso.keys("ratelimit:*"))


def test_login_es_mas_estricto(crear_cliente, redis_falso):
    cliente = crear_cliente("auth")
    estados = [cliente.post("/api/v1/auth/login", json={}).status_code for _ in range(11)]
    assert estados[-1] == 429 and 429 not in estados[:-1]
