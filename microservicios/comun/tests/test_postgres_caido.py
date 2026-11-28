import json
from pathlib import Path

import psycopg2
import pytest
from psycopg2 import errors

from epidemia_comun import llaves
from epidemia_comun.fabrica import crear_app

CONTRATO = Path(__file__).resolve().parents[3] / "docs/contratos/zonas/openapi.json"


@pytest.fixture
def cliente(redis_falso):
    app = crear_app("zonas", CONTRATO)
    app.config["TESTING"] = False
    app.extensions["epidemia_redis"] = redis_falso

    return app, redis_falso


def _con_ruta(app, exc, nombre):
    app.add_url_rule("/falla/" + nombre, nombre, lambda: (_ for _ in ()).throw(exc))


@pytest.mark.parametrize("exc", [
    psycopg2.OperationalError("connection refused host=db password=secreta"),
    psycopg2.InterfaceError("connection already closed"),
])
def test_conexion_caida_da_503(cliente, exc):
    app, r = cliente
    _con_ruta(app, exc, "a")
    resp = app.test_client().get("/falla/a?format=json")
    cuerpo = json.loads(resp.data)
    assert resp.status_code == 503
    assert cuerpo["codigo"] == "SERVICIO_NO_DISPONIBLE"
    assert "secreta" not in resp.get_data(as_text=True)
    assert resp.headers["Retry-After"] == "5"
    assert int(r.get(llaves.errores("zonas"))) == 1


def test_503_en_xml(cliente):
    app, _ = cliente
    _con_ruta(app, psycopg2.OperationalError("x"), "b")
    resp = app.test_client().get("/falla/b?format=xml")
    assert resp.status_code == 503
    assert resp.content_type.startswith("application/problem+xml")
    assert b"SERVICIO_NO_DISPONIBLE" in resp.data


@pytest.mark.parametrize("clase", [
    errors.UniqueViolation, errors.SyntaxError, errors.QueryCanceled, errors.DeadlockDetected])
def test_otros_errores_siguen_en_500(cliente, clase):
    app, _ = cliente
    exc = type("E", (clase,), {"pgcode": "XX000"})("x")
    _con_ruta(app, exc, "c" + clase.__name__)
    resp = app.test_client().get("/falla/c" + clase.__name__ + "?format=json")
    assert resp.status_code == 500
    assert json.loads(resp.data)["codigo"] == "ERROR_INTERNO"
