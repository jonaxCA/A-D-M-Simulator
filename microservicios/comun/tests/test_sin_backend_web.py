import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
IDENTIDAD = ("auth", "sesiones", "usuarios", "roles")
# Los servicios de E (identidad y simulación). `procesamiento` solo lo importan los que corren el motor.
SIMULACION = ("corridas", "resultados", "comparacion", "pareto")
SERVICIOS_E = IDENTIDAD + SIMULACION
PROHIBIDOS = ("backend_web",)
# validaciones.py ya no importa backend_web: parametros_epidemiologicos se mudó a
# microservicios/parametros/reglas.py (D7, 2026-11-23). ambito.py (F) tampoco lo importa (E8).
COMUN_CON_REGLAS_AJENAS = set()


def _importaciones(ruta):
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            yield from (a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and not nodo.level:
            yield nodo.module


def _modulos_de_servicios():
    for servicio in SERVICIOS_E:
        yield from (RAIZ / servicio).glob("*.py")


def _modulos():
    yield from _modulos_de_servicios()
    for ruta in (RAIZ / "comun" / "epidemia_comun").glob("*.py"):
        if ruta.name not in COMUN_CON_REGLAS_AJENAS:
            yield ruta


@pytest.mark.parametrize("ruta", sorted(_modulos()), ids=lambda r: "%s/%s" % (r.parent.name, r.name))
def test_no_importa_backend_web(ruta):
    assert not [m for m in _importaciones(ruta) if m.split(".")[0] in PROHIBIDOS]


@pytest.mark.parametrize("servicio", IDENTIDAD)
def test_identidad_no_importa_el_motor(servicio):
    assert not [m for r in (RAIZ / servicio).glob("*.py") for m in _importaciones(r)
                if m.split(".")[0] == "procesamiento"]


def test_las_exenciones_son_exactamente_los_modulos_que_importan_backend_web():
    comun = RAIZ / "comun" / "epidemia_comun"
    con_backend = {r.name for r in comun.glob("*.py")
                   if [m for m in _importaciones(r) if m.split(".")[0] in PROHIBIDOS]}
    assert con_backend == COMUN_CON_REGLAS_AJENAS


# La regla de los rangos de los parámetros es de parametros (D37): ningún servicio de E la usa.
FUNCIONES_AJENAS = ("parametros_epidemiologicos",)


def test_ningun_servicio_de_e_usa_las_funciones_que_piden_backend_web():
    texto = "".join(r.read_text(encoding="utf-8") for r in _modulos_de_servicios())
    assert not [f for f in FUNCIONES_AJENAS if f in texto]


@pytest.mark.parametrize("servicio", IDENTIDAD)
def test_la_imagen_no_parte_de_la_base_con_backend_web(servicio):
    dockerfile = (RAIZ / servicio / "Dockerfile").read_text()
    assert dockerfile.startswith("FROM epidemia/base-identidad\n")
