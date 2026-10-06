"""
Integridad de los modulos: que ningun nombre tape a otro.

POR QUE EXISTE
`backend_web/queries.py` llego a tener dos funciones `_entero` con firmas
distintas. Python se queda con la ultima, asi que los llamadores de la primera
empezaron a recibir TypeError y la captura de casos respondia 500. El archivo
compilaba, ninguna prueba fallaba y el error solo aparecia al usar esa pantalla.

Revisa TODOS los .py del proyecto, no una lista escrita a mano: la lista
anterior se quedo sin backend_web/simulaciones.py, el modulo mas grande que
llego despues. Y revisa tambien dentro de las clases: dos metodos de prueba con
el mismo nombre hacen que el primero nunca se ejecute, sin que nada falle.

Ademas vigila que el motor se cargue una sola vez (ver el ultimo caso).

Ejecutar:
    python -m unittest backend_web.tests.test_integridad -v
"""
import ast
import pathlib
import unittest

RAIZ = pathlib.Path(__file__).resolve().parents[2]

CARPETAS = ("backend_web", "frontend_web", "procesamiento", "datos/scripts")

# Archivos que no pueden faltar en el recorrido: si alguno se mueve, la prueba
# lo dice en vez de dejar de cubrirlo en silencio.
IMPRESCINDIBLES = (
    "backend_web/queries.py",
    "backend_web/simulaciones.py",
    "backend_web/auth.py",
    "frontend_web/app/routes.py",
    "frontend_web/app/permisos.py",
    "procesamiento/motor/parametros.py",
    "procesamiento/motor/modelo.py",
)


def _modulos():
    for carpeta in CARPETAS:
        for ruta in sorted((RAIZ / carpeta).rglob("*.py")):
            if "__pycache__" not in ruta.parts:
                yield ruta


def _duplicados(cuerpo):
    """{nombre: [lineas]} de funciones y clases definidas mas de una vez en
    el mismo bloque."""
    vistos = {}
    for nodo in cuerpo:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            vistos.setdefault(nodo.name, []).append(nodo.lineno)
    return {n: l for n, l in vistos.items() if len(l) > 1}


class SinNombresTapadosTests(unittest.TestCase):
    def test_ningun_modulo_ni_clase_define_dos_veces_el_mismo_nombre(self):
        problemas = []
        for ruta in _modulos():
            rel = ruta.relative_to(RAIZ).as_posix()
            arbol = ast.parse(ruta.read_text(encoding="utf-8"), rel)
            bloques = [("", arbol.body)] + [
                (f"clase {n.name}: ", n.body)
                for n in ast.walk(arbol) if isinstance(n, ast.ClassDef)]
            for donde, cuerpo in bloques:
                for nombre, lineas in _duplicados(cuerpo).items():
                    problemas.append(f"{rel}: {donde}'{nombre}' en las lineas "
                                     + ", ".join(str(l) for l in lineas))
        self.assertEqual(problemas, [],
                         "hay definiciones que tapan a otras:\n  " + "\n  ".join(problemas))

    def test_el_recorrido_cubre_los_modulos_que_importan(self):
        cubiertos = {r.relative_to(RAIZ).as_posix() for r in _modulos()}
        faltan = [rel for rel in IMPRESCINDIBLES if rel not in cubiertos]
        self.assertEqual(faltan, [], f"módulos que ya no existen: {faltan}")


def _imports_de_backend_web(paquete):
    """'archivo:linea' de cada import de `paquete` (o de un submodulo suyo) en
    backend_web, sin contar sus pruebas, incluidos los que estan dentro de una
    funcion."""
    culpables = []
    for ruta in sorted((RAIZ / "backend_web").rglob("*.py")):
        if "tests" in ruta.parts or "__pycache__" in ruta.parts:
            continue
        rel = ruta.relative_to(RAIZ).as_posix()
        for n in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"), rel)):
            modulos = ([a.name for a in n.names] if isinstance(n, ast.Import)
                       else [n.module or ""] if isinstance(n, ast.ImportFrom) else [])
            if any(m == paquete or m.startswith(paquete + ".") for m in modulos):
                culpables.append(f"{rel}:{n.lineno}")
    return culpables


class CapaDeDatosSinFlaskTests(unittest.TestCase):
    """backend_web no importa Flask, ni siquiera dentro de una funcion.

    La capa de datos recibe quien y desde donde en un Contexto
    (backend_web/contexto.py). Leerlo de flask.request la ataba a una peticion
    web: no se podia llamar desde un hilo, un script o un microservicio, y las
    pruebas tenian que sustituir flask.request a mano.
    """

    def test_ningun_modulo_de_backend_web_importa_flask(self):
        culpables = _imports_de_backend_web("flask")
        self.assertEqual(culpables, [])

    def test_ningun_modulo_de_backend_web_importa_de_frontend_web(self):
        """La dependencia va de la web a los datos, nunca al reves: las valida_*
        tienen que poder usarse desde una API o la app de escritorio sin cargar
        la web. Por eso la conversion de texto vive en backend_web/conversion.py
        y no en frontend_web/app/formularios.py."""
        culpables = _imports_de_backend_web("frontend_web")
        self.assertEqual(culpables, [])


class MotorUnaSolaVezTests(unittest.TestCase):
    """queries.py y simulaciones.py tienen que ver EL MISMO motor.

    simulaciones.py lo importaba como `motor` (metiendo procesamiento/ en
    sys.path) y queries.py como `procesamiento.motor`. Python los cargaba como
    dos modulos distintos, con dos clases EscenarioInvalido: un `except` de un
    lado no atrapaba lo que lanzaba el otro.
    """

    def test_simulaciones_y_queries_comparten_las_clases_del_motor(self):
        from backend_web import queries, simulaciones  # noqa: F401
        from procesamiento.motor import modelo, parametros, pareto

        self.assertIs(simulaciones.EscenarioInvalido, parametros.EscenarioInvalido)
        self.assertIs(simulaciones.ComparacionInvalida, pareto.ComparacionInvalida)
        self.assertIs(simulaciones.simular, modelo.simular)

    def test_una_excepcion_de_un_lado_se_atrapa_del_otro(self):
        from backend_web import simulaciones
        from procesamiento.motor.parametros import resolver

        with self.assertRaises(simulaciones.EscenarioInvalido):
            resolver({"poblacion": -1})


if __name__ == "__main__":
    unittest.main()
