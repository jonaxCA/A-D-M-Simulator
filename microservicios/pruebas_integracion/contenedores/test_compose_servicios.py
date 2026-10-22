"""Cada uno de los 26 contra su contenedor: salud en XML y en JSON, el contrato que sirve y sus
rutas GET sin 5xx. Es la prueba de integración de la definición de terminado de cada servicio."""
import json
import re

import pytest

from microservicios.estado_servicios.sondeo import SERVICIOS
from .conftest import RAIZ


@pytest.mark.parametrize("servicio", list(SERVICIOS))
def test_salud_en_xml_y_en_json(api, servicio):
    xml = api(servicio, "GET", "/health", formato=None)
    assert xml.status_code == 200 and xml.headers["Content-Type"].startswith("application/xml")
    datos = api(servicio, "GET", "/health", formato=None, headers={"Accept": "application/json"}).json()
    assert (datos["servicio"], datos["estado"], datos["postgresql"], datos["redis"]) == (servicio, "ok", True, True)


@pytest.mark.parametrize("servicio", list(SERVICIOS))
def test_sirve_el_contrato_del_repositorio(api, servicio):
    r = api(servicio, "GET", "/openapi.json", formato=None)
    assert r.status_code == 200
    assert r.content == (RAIZ / "docs/contratos" / servicio / "openapi.json").read_bytes()


@pytest.mark.parametrize("servicio", list(SERVICIOS))
def test_sus_rutas_get_responden_sin_5xx(api, sesion, servicio):
    token = sesion("admin")["access"]
    contrato = json.loads((RAIZ / "docs/contratos" / servicio / "openapi.json").read_text(encoding="utf-8"))
    for ruta, metodos in contrato["paths"].items():
        if "get" in metodos:
            concreta = re.sub(r"\{[^}]+\}", "1", ruta)
            r = api(servicio, "GET", concreta, token)
            assert r.status_code < 500, (concreta, r.status_code, r.text[:300])
