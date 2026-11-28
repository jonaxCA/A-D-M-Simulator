"""Las lecturas de solo consulta que un servicio copia de su dueño siguen iguales (E8, D37).

Una lectura copiada no es una regla repetida: el dueño escribe y decide; la copia solo lee las
mismas columnas para no pedir por HTTP lo que ya puede leer su rol. Si el dueño cambia la consulta,
esta prueba obliga a cambiar la copia en el mismo PR (duenos_de_reglas.md, «Compartidas o con
copia»). Las reglas que escriben ya no se copian: el estado del lote lo lleva la base (065).
"""
import importlib
import inspect
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
# (dueño, copia, función)
COPIAS = [
    ("corridas.datos", "simulador.datos", "get_run"),
    ("corridas.datos", "resultados.datos", "get_run"),
    ("corridas.datos", "pareto.datos", "get_run"),
    ("corridas.datos", "simulador.datos", "get_motor_run"),
    ("resultados.datos", "pareto.datos", "get_resultado_run"),
    ("corridas.datos", "pareto.datos", "region_de_version"),
    ("simulador.datos", "pareto.datos", "version_para_motor"),
    ("escenarios.datos", "validacion.datos", "escenario_detalle"),
    ("tipos_intervencion.datos", "intervenciones.datos", "tipos"),
]


def _fuente(modulo, nombre):
    return inspect.getsource(getattr(importlib.import_module("microservicios." + modulo), nombre))


@pytest.mark.parametrize("duenio,copia,nombre", COPIAS, ids=lambda x: str(x))
def test_la_copia_es_igual_a_la_del_duenio(duenio, copia, nombre):
    assert _fuente(copia, nombre) == _fuente(duenio, nombre)


def test_la_seleccion_de_corridas_es_la_misma_en_comparacion_y_pareto():
    assert ((RAIZ / "microservicios/pareto/seleccion.py").read_bytes()
            == (RAIZ / "microservicios/comparacion/seleccion.py").read_bytes())


def test_ningun_servicio_sincroniza_el_lote_a_mano():
    for ruta in (RAIZ / "microservicios").rglob("*.py"):
        if "tests" not in ruta.parts:
            assert "UPDATE simulation_batches" not in ruta.read_text(encoding="utf-8"), ruta
