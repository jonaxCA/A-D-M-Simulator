"""
resolver() ante cualquier entrada que pueda llegar en un JSON.

POR QUE EXISTE
Un escenario invalido tiene que salir como EscenarioInvalido, con su mensaje.
Habia entradas que lo hacian reventar con TypeError o AttributeError: un `tipo`
o una `prioridad` que llegaban como lista u objeto, `intervenciones` como
numero, `params` como texto. Desde el sitio no se alcanzaban (los formularios
mandan texto), pero desde una API JSON un cliente recibiria un 500 en lugar de
un 422 con el error. Una prueba diferencial contra la version anterior de
resolver() las encontro: 1,117 de 50,000 escenarios al azar.

Parte de los escenarios de corpus_resolver.py y reemplaza de 1 a 3 valores, en
cualquier nivel, por valores JSON al azar. La semilla es fija: la prueba da
siempre el mismo resultado.

Ejecutar:
    cd procesamiento && python -m unittest tests.test_resolver_robustez -v
"""
import copy
import random
import traceback
import unittest

from motor.parametros import EscenarioInvalido, resolver
from tests.corpus_resolver import INVALIDOS, VALIDOS

SEMILLA = 20261005
ESCENARIOS = 6000
BASES = [e for _, e in list(VALIDOS.values()) + list(INVALIDOS.values())
         if isinstance(e, dict)]
TEXTOS = ["", "x", "excluir", "prorratear", "edad_desc", "aleatorio", "CUBREBOCAS",
          "VACUNACION", "TESTEO_AISLAMIENTO", "0-19", "60+"]
CLAVES = ["valor", "fuente", "supuesto", "media", "0-19", "20-59", "60+", "x",
          "tipo", "dia_inicio", "eficacia", "deteccion", "retraso_dias"]


def valor_json(rnd, profundidad=0):
    """Un valor que podria llegar en un JSON: numero, texto, booleano, null,
    lista u objeto (con claves de texto)."""
    r = rnd.random()
    if r < 0.18:
        return rnd.choice([0, 1, -1, 2, 5, 60, 1000, 50000, 10**9])
    if r < 0.30:
        return rnd.choice([0.0, 0.5, 1.5, -0.1, 7.5, float("nan"), float("inf")])
    if r < 0.45:
        return rnd.choice(TEXTOS)
    if r < 0.52 or profundidad > 1:
        return rnd.choice([True, False, None])
    if r < 0.76:
        return [valor_json(rnd, profundidad + 1) for _ in range(rnd.randint(0, 3))]
    return {rnd.choice(CLAVES): valor_json(rnd, profundidad + 1)
            for _ in range(rnd.randint(0, 3))}


def _rutas(objeto, prefijo=()):
    yield prefijo
    if isinstance(objeto, dict):
        for k, v in objeto.items():
            yield from _rutas(v, prefijo + (k,))
    elif isinstance(objeto, list):
        for i, v in enumerate(objeto):
            yield from _rutas(v, prefijo + (i,))


def escenario_al_azar(rnd):
    e = copy.deepcopy(rnd.choice(BASES))
    for _ in range(rnd.randint(1, 3)):
        ruta = rnd.choice([r for r in _rutas(e) if r])
        padre = e
        for paso in ruta[:-1]:
            padre = padre[paso]
        padre[ruta[-1]] = valor_json(rnd)
    return e


class ResolverRobustezTests(unittest.TestCase):

    def test_ninguna_entrada_json_lo_hace_reventar(self):
        rnd = random.Random(SEMILLA)
        choques = []
        for _ in range(ESCENARIOS):
            escenario = escenario_al_azar(rnd)
            try:
                resolver(copy.deepcopy(escenario))
            except EscenarioInvalido:
                pass
            except Exception as exc:  # cualquier otra cosa es el bug
                lugar = traceback.extract_tb(exc.__traceback__)[-1]
                choques.append(f"{type(exc).__name__} en {lugar.name}(): {lugar.line}")
        self.assertEqual(sorted(set(choques)), [],
                         f"{len(choques)} de {ESCENARIOS} escenarios reventaron")
