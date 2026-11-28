"""E8 en los servicios de D (catálogos, escenarios y archivos): ninguno importa backend_web.

Las reglas de cada uno viven en su carpeta (duenos_de_reglas.md). Los que no usan el motor parten de
epidemia/base-vigilancia y no importan procesamiento. enfermedades (el estado de los parámetros),
parametros (los límites del motor) y validacion (el escenario contra el motor) usan
procesamiento, la biblioteca de los modelos (D37), y parten de epidemia/base-simulacion. Ninguno
importa a otro servicio fuera de sus pruebas: se piden por HTTP (D37).
"""
import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
SIN_BACKEND_WEB = ("evidencias", "importacion", "aprobacion", "tipos_intervencion", "poblacion",
                   "regiones", "escenarios", "escenarios_xml", "intervenciones")
CON_PROCESAMIENTO = ("enfermedades", "parametros", "validacion")


def _importaciones(ruta):
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            yield from (a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and not nodo.level:
            yield nodo.module


def _bloque_del_compose(servicio):
    compose = (RAIZ / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    inicio = compose.index("\n  %s:\n" % servicio.replace("_", "-"))
    return compose[inicio:inicio + 200]


@pytest.mark.parametrize("servicio", SIN_BACKEND_WEB)
def test_no_importa_backend_web_ni_el_motor(servicio):
    for ruta in (RAIZ / "microservicios" / servicio).rglob("*.py"):
        raices = {m.split(".")[0] for m in _importaciones(ruta)}
        assert not raices & {"backend_web", "procesamiento"}, ruta


@pytest.mark.parametrize("servicio", CON_PROCESAMIENTO)
def test_usa_el_motor_sin_backend_web(servicio):
    for ruta in (RAIZ / "microservicios" / servicio).rglob("*.py"):
        assert "backend_web" not in {m.split(".")[0] for m in _importaciones(ruta)}, ruta


@pytest.mark.parametrize("servicio", SIN_BACKEND_WEB + CON_PROCESAMIENTO)
def test_ningun_servicio_importa_a_otro(servicio):
    for ruta in (RAIZ / "microservicios" / servicio).rglob("*.py"):
        if "tests" in ruta.parts:
            continue
        ajenos = [m for m in _importaciones(ruta)
                  if m.startswith("microservicios.") and m.split(".")[1] != servicio]
        assert not ajenos, ruta


@pytest.mark.parametrize("servicio", SIN_BACKEND_WEB)
def test_la_imagen_parte_de_la_base_sin_backend_web(servicio):
    docker = (RAIZ / "microservicios" / servicio / "Dockerfile").read_text(encoding="utf-8")
    assert docker.startswith("FROM epidemia/base-vigilancia\n")
    assert "<<: *construye-vigilancia" in _bloque_del_compose(servicio)


@pytest.mark.parametrize("servicio", CON_PROCESAMIENTO)
def test_la_imagen_parte_de_la_base_de_simulacion(servicio):
    docker = (RAIZ / "microservicios" / servicio / "Dockerfile").read_text(encoding="utf-8")
    assert docker.startswith("FROM epidemia/base-simulacion\n")
    assert "<<: *construye-simulacion" in _bloque_del_compose(servicio)


def test_backend_web_ya_no_tiene_las_reglas_de_evidencias():
    assert not (RAIZ / "backend_web" / "evidencias.py").exists()


def test_solo_la_consola_y_la_web_parten_de_la_base_con_backend_web():
    compose = (RAIZ / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    nombres = list(re.finditer(r"\n  ([a-z][a-z0-9-]*):\n", compose))
    con_base = [m.group(1) for m, siguiente in zip(nombres, nombres[1:] + [None])
                if "<<: *construye\n" in compose[m.end():siguiente.start() if siguiente else None]]
    assert con_base == ["consola", "web"]
