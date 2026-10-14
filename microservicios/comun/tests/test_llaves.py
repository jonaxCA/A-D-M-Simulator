import inspect
import re
import unittest
from pathlib import Path

from epidemia_comun import llaves

CATALOGO = Path(__file__).resolve().parents[3] / "docs" / "arquitectura" / "microservicios.md"


def _patrones_del_catalogo():
    seccion = CATALOGO.read_text(encoding="utf-8").split("## Llaves de Redis", 1)[1].split("\n## ", 1)[0]
    primeras = [linea.split("|")[1] for linea in seccion.splitlines() if linea.startswith("| `")]
    return [
        re.sub(r"<[^>]+>", "[^:]+", re.escape(llave))
        for celda in primeras for llave in re.findall(r"`([^`]+)`", celda)
    ]


def _llaves_de_ejemplo():
    ejemplos = []
    for nombre, valor in vars(llaves).items():
        if nombre.isupper():
            ejemplos.append(valor)
        elif inspect.isfunction(valor) and nombre != "huella":
            ejemplos.append(valor(*["x"] * valor.__code__.co_argcount))
    return ejemplos


@unittest.skipUnless(CATALOGO.exists(), "El catálogo no está junto al código")
class LlavesDelCatalogo(unittest.TestCase):
    def test_cada_llave_esta_en_la_tabla_del_catalogo(self):
        patrones = _patrones_del_catalogo()
        for llave in _llaves_de_ejemplo():
            with self.subTest(llave):
                self.assertTrue(any(re.fullmatch(p, llave) for p in patrones))

    def test_cada_llave_del_catalogo_tiene_su_funcion(self):
        ejemplos = _llaves_de_ejemplo()
        for patron in _patrones_del_catalogo():
            with self.subTest(patron):
                self.assertTrue(any(re.fullmatch(patron, llave) for llave in ejemplos))
