import ast
import inspect
import re
import unittest
from pathlib import Path

from epidemia_comun import llaves

CATALOGO = Path(__file__).resolve().parents[3] / "docs" / "arquitectura" / "microservicios.md"
SERVICIOS = Path(__file__).resolve().parents[2]
PREFIJO = re.compile(r"[a-z_]+(:[a-z_]+)*:")


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


def _llaves_armadas_a_mano():
    # Busca "captcha:" + x y f"captcha:{x}" en el código de los servicios: una llave
    # armada fuera de llaves.py no la ve la prueba del catálogo.
    hallazgos = []
    for ruta in sorted(SERVICIOS.rglob("*.py")):
        partes = ruta.relative_to(SERVICIOS).parts
        if ruta.name in ("llaves.py", "conftest.py") or "tests" in partes or "pruebas_integracion" in partes:
            continue
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add):
                inicio = nodo.left
            elif isinstance(nodo, ast.JoinedStr) and nodo.values:
                inicio = nodo.values[0]
            else:
                continue
            if isinstance(inicio, ast.Constant) and isinstance(inicio.value, str) \
                    and PREFIJO.fullmatch(inicio.value):
                hallazgos.append("%s:%d %r" % ("/".join(partes), nodo.lineno, inicio.value))
    return hallazgos


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


class LlavesSoloDeLlavesPy(unittest.TestCase):
    def test_ningun_servicio_arma_llaves_a_mano(self):
        self.assertEqual(_llaves_armadas_a_mano(), [])
