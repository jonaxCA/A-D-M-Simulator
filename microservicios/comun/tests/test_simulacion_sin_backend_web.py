import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SIMULACION = ("corridas", "simulador", "resultados", "comparacion", "pareto")


def _importaciones(ruta):
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            yield from (a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and not nodo.level:
            yield nodo.module


def _modulos():
    for servicio in SIMULACION:
        yield from (RAIZ / servicio).rglob("*.py")


def _id(ruta):
    return str(ruta.relative_to(RAIZ))


@pytest.mark.parametrize("ruta", sorted(_modulos()), ids=_id)
def test_no_importa_backend_web(ruta):
    assert not [m for m in _importaciones(ruta) if m.split(".")[0] == "backend_web"]


@pytest.mark.parametrize("ruta", sorted(r for r in _modulos() if "tests" not in r.parts), ids=_id)
def test_ningun_servicio_importa_a_otro(ruta):
    propio = ruta.relative_to(RAIZ).parts[0]
    ajenos = [m for m in _importaciones(ruta)
              if m.startswith("microservicios.") and m.split(".")[1] != propio]
    assert not ajenos


@pytest.mark.parametrize("servicio", SIMULACION)
def test_la_imagen_no_parte_de_la_base_con_backend_web(servicio):
    assert (RAIZ / servicio / "Dockerfile").read_text().startswith("FROM epidemia/base-simulacion\n")


def test_la_base_de_simulacion_no_copia_backend_web():
    base = (RAIZ.parent / "infra" / "docker" / "base-simulacion.Dockerfile").read_text()
    instrucciones = [l for l in base.splitlines() if not l.startswith("#")]
    assert not [l for l in instrucciones if "backend_web" in l]
    assert "COPY procesamiento/ /app/procesamiento/" in instrucciones
