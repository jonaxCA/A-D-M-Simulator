import re
from pathlib import Path

import pytest

from microservicios.consola import app as modulo

RAIZ = Path(__file__).resolve().parents[3]
ESTATICO = RAIZ / "microservicios/consola/estatico"
JS = (ESTATICO / "consola.js").read_text(encoding="utf-8")
RECORRIDO = (ESTATICO / "recorrido.js").read_text(encoding="utf-8")


@pytest.fixture
def cliente():
    return modulo.app.test_client()


def test_sirve_la_pagina_con_sus_archivos(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and r.mimetype == "text/html"
    assert b'href="/estatico/consola.css"' in r.data
    # recorrido.js antes que consola.js: los dos con defer, se ejecutan en ese orden.
    assert r.data.index(b'src="/estatico/recorrido.js"') < r.data.index(b'src="/estatico/consola.js"')
    assert cliente.get("/estatico/consola.js").status_code == 200
    assert cliente.get("/estatico/recorrido.js").status_code == 200
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


@pytest.mark.parametrize("codigo", [JS, RECORRIDO], ids=["consola", "recorrido"])
@pytest.mark.parametrize("almacen", ["localStorage", "sessionStorage", "document.cookie", "indexedDB"])
def test_el_token_no_se_guarda_en_el_navegador(codigo, almacen):
    assert almacen not in codigo


@pytest.mark.parametrize("codigo", [JS, RECORRIDO], ids=["consola", "recorrido"])
@pytest.mark.parametrize("html", ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"])
def test_las_respuestas_se_pintan_como_texto(codigo, html):
    # Lo que regresa un servicio nunca se interpreta como HTML.
    assert html not in codigo


def test_el_recorrido_tiene_los_22_pasos_del_guion():
    guion = (RAIZ / "docs/CHECKLIST_SEGUNDO_PARCIAL.md").read_text(encoding="utf-8")
    seccion = guion.split("## Prueba de aceptación", 1)[1].split("Verificaciones extra", 1)[0]
    del_guion = {int(n) for n in re.findall(r"^- \[[ x]\] (\d+)\. ", seccion, re.M)}
    assert del_guion == set(range(1, 23))
    pasos = re.findall(r'\{n: "(\d+)([a-z]?)"', RECORRIDO)
    assert {int(n) for n, _ in pasos} == del_guion
    assert len(pasos) == len(set(pasos))


def test_el_recorrido_no_resuelve_el_captcha():
    # La pregunta la pide consola.js para mostrarla; la respuesta la escribe la persona.
    assert "auth/captcha" not in RECORRIDO
    assert "captcha_respuesta: captchaRespuesta" in RECORRIDO


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
