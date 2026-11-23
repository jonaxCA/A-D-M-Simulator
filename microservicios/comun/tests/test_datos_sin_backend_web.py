"""E8 en los servicios de D (catálogos, escenarios y archivos) que ya no importan backend_web.

Hoy evidencias (D2, 2026-11-22), cuyas reglas pasaron de backend_web/evidencias.py a
microservicios/evidencias/; importacion (D6), que nació sin él, y aprobacion (D7, 2026-11-23), cuyo
flujo de revisión pasó de backend_web.queries a microservicios/aprobacion/datos.py. Las tres imágenes
parten de epidemia/base-vigilancia. Los demás servicios de D se agregan a SIN_BACKEND_WEB conforme se
muden.
"""
import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
SIN_BACKEND_WEB = ("evidencias", "importacion", "aprobacion")


def _importaciones(ruta):
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            yield from (a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and not nodo.level:
            yield nodo.module


@pytest.mark.parametrize("servicio", SIN_BACKEND_WEB)
def test_no_importa_backend_web_ni_el_motor(servicio):
    for ruta in (RAIZ / "microservicios" / servicio).rglob("*.py"):
        raices = {m.split(".")[0] for m in _importaciones(ruta)}
        assert not raices & {"backend_web", "procesamiento"}, ruta


@pytest.mark.parametrize("servicio", SIN_BACKEND_WEB)
def test_la_imagen_parte_de_la_base_sin_backend_web(servicio):
    docker = (RAIZ / "microservicios" / servicio / "Dockerfile").read_text(encoding="utf-8")
    assert docker.startswith("FROM epidemia/base-vigilancia\n")
    compose = (RAIZ / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    inicio = compose.index("\n  %s:\n" % servicio)
    assert "<<: *construye-vigilancia" in compose[inicio:inicio + 200]


def test_backend_web_ya_no_tiene_las_reglas_de_evidencias():
    assert not (RAIZ / "backend_web" / "evidencias.py").exists()
