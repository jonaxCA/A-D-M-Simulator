import re
from pathlib import Path

import pytest

from microservicios.consola import app as modulo

RAIZ = Path(__file__).resolve().parents[3]
JS = (RAIZ / "microservicios/consola/estatico/consola.js").read_text(encoding="utf-8")


@pytest.fixture
def cliente():
    return modulo.app.test_client()


def test_sirve_la_pagina_con_sus_archivos(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and r.mimetype == "text/html"
    assert b'src="/estatico/consola.js"' in r.data and b'href="/estatico/consola.css"' in r.data
    assert cliente.get("/estatico/consola.js").status_code == 200
    assert cliente.get("/estatico/consola.css").status_code == 200


@pytest.mark.parametrize("ruta", ["/", "/estatico/consola.js", "/health", "/config"])
def test_cada_respuesta_lleva_la_politica_de_contenido(cliente, ruta):
    r = cliente.get(ruta)
    politica = r.headers["Content-Security-Policy"]
    assert "script-src 'self' https://unpkg.com;" in politica
    assert "form-action 'none'" in politica and "frame-ancestors 'none'" in politica
    assert "unsafe-eval" not in politica
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_salud_en_xml_y_en_json(cliente):
    assert cliente.get("/health").mimetype == "application/xml"
    assert cliente.get("/health?format=json").get_json() == {
        "servicio": "consola", "version": "0.1.0", "estado": "ok"}


def test_directorio_por_omision_y_configurable(cliente, monkeypatch):
    assert cliente.get("/config?format=json").get_json() == {"directorio": "http://localhost:5262"}
    monkeypatch.setenv("URL_DIRECTORIO", "http://192.168.1.20:5262")
    assert cliente.get("/config?format=json").get_json()["directorio"] == "http://192.168.1.20:5262"


@pytest.mark.parametrize("almacen", ["localStorage", "sessionStorage", "document.cookie", "indexedDB"])
def test_el_token_no_se_guarda_en_el_navegador(almacen):
    assert almacen not in JS


@pytest.mark.parametrize("html", ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"])
def test_las_respuestas_se_pintan_como_texto(html):
    # Lo que regresa un servicio nunca se interpreta como HTML.
    assert html not in JS


def test_swagger_ui_fijo_y_del_origen_permitido():
    assert re.search(r'const SWAGGER = "https://unpkg\.com/swagger-ui-dist@\d+\.\d+\.\d+";', JS)


def test_dockerfile():
    docker = (RAIZ / "microservicios/consola/Dockerfile").read_text(encoding="utf-8")
    assert "microservicios.consola.app:app" in docker
    assert "HEALTHCHECK" in docker and "USER epidemia" in docker


def test_compose_publica_la_consola_y_le_abre_cors_en_los_26():
    compose = (RAIZ / "infra/docker-compose.yml").read_text(encoding="utf-8")
    assert re.search(r'^  consola:\n(?:    .*\n)*?    profiles: \[plataforma\]\n    ports:\n'
                     r'      - "5260:8000"', compose, re.M)
    servicios = compose.count("      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0\n")
    assert servicios == 26
    assert compose.count("      CONSOLE_ORIGIN: ${CONSOLE_ORIGIN:-http://localhost:5260}\n") == servicios
