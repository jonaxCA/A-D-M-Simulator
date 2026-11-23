"""E8 en los servicios de F (vigilancia, analítica y plataforma): sin backend_web ni el motor.

Cada regla vive con su servicio (docs/arquitectura/duenos_de_reglas.md) y la imagen parte de
epidemia/base-vigilancia, que no trae ni backend_web ni procesamiento.
"""
import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SERVICIOS_F = ("casos", "sincronizacion", "dispositivos", "vacunas", "indicadores", "series", "zonas",
               "notificaciones", "estado_servicios")


def _importaciones(ruta):
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            yield from (a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and not nodo.level:
            yield nodo.module


def _modulos(con_pruebas=True):
    for servicio in SERVICIOS_F:
        yield from (r for r in (RAIZ / servicio).rglob("*.py") if con_pruebas or "tests" not in r.parts)


def _id(ruta):
    return str(ruta.relative_to(RAIZ))


@pytest.mark.parametrize("ruta", sorted(_modulos()), ids=_id)
def test_no_importa_backend_web(ruta):
    assert not [m for m in _importaciones(ruta) if m.split(".")[0] == "backend_web"]


@pytest.mark.parametrize("ruta", sorted(_modulos(con_pruebas=False)), ids=_id)
def test_no_importa_el_motor_ni_otro_servicio(ruta):
    propio = ruta.relative_to(RAIZ).parts[0]
    ajenos = [m for m in _importaciones(ruta)
              if m.split(".")[0] == "procesamiento"
              or (m.startswith("microservicios.") and m.split(".")[1] != propio)]
    assert not ajenos


def test_ninguno_usa_lo_de_epidemia_comun_que_pide_backend_web():
    texto = "".join(r.read_text(encoding="utf-8") for r in _modulos(con_pruebas=False))
    assert "parametros_epidemiologicos" not in texto


@pytest.mark.parametrize("servicio", SERVICIOS_F)
def test_la_imagen_parte_de_la_base_de_vigilancia(servicio):
    assert (RAIZ / servicio / "Dockerfile").read_text().startswith("FROM epidemia/base-vigilancia\n")


def test_la_base_de_vigilancia_no_trae_backend_web_ni_el_motor():
    base = (RAIZ.parent / "infra" / "docker" / "base-vigilancia.Dockerfile").read_text()
    instrucciones = [l for l in base.splitlines() if l and not l.startswith("#")]
    assert instrucciones[0] == "FROM python:3.12-slim"
    assert not [l for l in instrucciones if "backend_web" in l or "procesamiento" in l]


def test_el_compose_construye_los_de_f_con_su_base():
    compose = (RAIZ.parent / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    servicios = compose.split("\nservices:\n", 1)[1].split("\nvolumes:\n", 1)[0]
    bloques = dict(re.findall(r"^  ([a-z][a-z0-9-]*):\n((?:(?:    .*)?\n)*)", servicios + "\n", re.M))
    assert "epidemia/base-vigilancia: service:base-vigilancia" in compose
    assert "      dockerfile: infra/docker/base-vigilancia.Dockerfile\n" in bloques["base-vigilancia"]
    for servicio in SERVICIOS_F:
        assert "    build:\n      <<: *construye-vigilancia\n" in bloques[servicio.replace("_", "-")], servicio
