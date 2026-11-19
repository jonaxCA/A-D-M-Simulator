"""Interoperabilidad [Retro: «Hay evidencias de interoperabilidad pendientes»; E6].

Recorre cada ruta de cada contrato de docs/contratos/ contra el servicio que lo sirve, como lo
haría una app cliente que solo conoce el contrato: permisos (401 sin token), respuestas de error
RFC 7807 en XML (validadas con problem.xsd) y en JSON, versiones (/api/v2 no existe), formato
desconocido y cuerpos inválidos. Los datos válidos e inválidos de cada ruta, y las respuestas
XML contra su XSD, los prueban las pruebas de cada servicio y test_xsd.py.
"""
import json
import re
from pathlib import Path

import pytest
import xmlschema

RAIZ = Path(__file__).resolve().parents[3]
PROBLEM = xmlschema.XMLSchema(str(RAIZ / "docs/contratos/comun/problem.xsd"))
CODIGOS_401 = {"TOKEN_AUSENTE", "TOKEN_INVALIDO", "TOKEN_EXPIRADO", "TOKEN_REVOCADO"}


def _operaciones():
    for archivo in sorted((RAIZ / "docs/contratos").glob("*/openapi.json")):
        servicio = archivo.parent.name
        contrato = json.loads(archivo.read_text(encoding="utf-8"))
        for ruta, metodos in contrato["paths"].items():
            url = re.sub(r"\{[^}]+\}", "1", ruta).replace("/1/1", "/1/activate") \
                if ruta.endswith("/{accion}") else re.sub(r"\{[^}]+\}", "1", ruta)
            for metodo, item in metodos.items():
                yield pytest.param(servicio, metodo, url, item.get("security") == [{"bearerAuth": []}],
                                   id="%s %s %s" % (servicio, metodo.upper(), ruta))


OPERACIONES = list(_operaciones())


@pytest.fixture(autouse=True)
def sin_base(monkeypatch):
    # Una base que no responde: lo que llegue a ella es 503, nunca 500 ni la traza.
    from backend_web import db
    monkeypatch.setattr(db, "DATABASE_URL", "postgresql://nadie:nada@127.0.0.1:1/ninguna")


def _cliente(crear_cliente, servicio):
    return crear_cliente(servicio.replace("-", "_"))


@pytest.mark.parametrize("servicio,metodo,url,protegida", OPERACIONES)
def test_sin_token_es_401_rfc7807_en_xml_y_json(crear_cliente, servicio, metodo, url, protegida):
    if not protegida:
        pytest.skip("ruta pública o solo para servicios")
    c = _cliente(crear_cliente, servicio)
    r = getattr(c, metodo)(url)
    assert r.status_code == 401 and r.mimetype == "application/problem+xml"
    PROBLEM.validate(r.data.decode("utf-8"))
    r = getattr(c, metodo)(url + "?format=json")
    assert r.status_code == 401 and r.mimetype == "application/problem+json"
    assert r.get_json()["codigo"] in CODIGOS_401 and r.get_json()["status"] == 401


@pytest.mark.parametrize("servicio,metodo,url,protegida", OPERACIONES)
def test_una_version_que_no_existe_es_404(crear_cliente, token, servicio, metodo, url, protegida):
    c = _cliente(crear_cliente, servicio)
    r = getattr(c, metodo)(url.replace("/api/v1/", "/api/v2/"), headers=token())
    assert r.status_code == 404
    PROBLEM.validate(r.data.decode("utf-8"))


@pytest.mark.parametrize("servicio,metodo,url,protegida", OPERACIONES)
def test_un_formato_desconocido_es_400_antes_de_todo(crear_cliente, servicio, metodo, url, protegida):
    # Con un formato que no entiende, el error sale en JSON (errores.respuesta_error).
    c = _cliente(crear_cliente, servicio)
    r = getattr(c, metodo)(url + "?format=yaml")
    assert r.status_code == 400 and r.mimetype == "application/problem+json"
    assert r.get_json()["codigo"] == "DATOS_INVALIDOS"


@pytest.mark.parametrize("servicio,metodo,url,protegida",
                         [o for o in OPERACIONES if o.values[1] in ("post", "put")])
def test_un_cuerpo_invalido_nunca_es_500(crear_cliente, token, servicio, metodo, url, protegida):
    c = _cliente(crear_cliente, servicio)
    cabeceras = token(roles=("ADMINISTRADOR", "ANALISTA", "EPIDEMIOLOGO", "CAPTURISTA"))
    for datos, tipo in (("<roto", "application/xml"), ("{roto", "application/json"),
                        ("texto", "text/plain")):
        r = getattr(c, metodo)(url, headers=cabeceras, data=datos, content_type=tipo)
        assert r.status_code in (400, 401, 404, 413, 415, 422, 503), (datos, r.status_code, r.data)
        PROBLEM.validate(r.data.decode("utf-8"))
        assert b"Traceback" not in r.data
