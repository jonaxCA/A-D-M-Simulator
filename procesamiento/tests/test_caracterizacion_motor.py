"""
Caracterizacion de resolver(): su salida, hoy, fijada en un archivo.

POR QUE EXISTE
resolver() valida la entrada y calcula los parametros con los que corre la
simulacion. La huella de un escenario (huella_escenario) se calcula sobre la
ENTRADA, asi que si un cambio en resolver() altera un valor resuelto, la misma
semilla da otro resultado con el mismo ENGINE_VERSION y la promesa de
reproducibilidad se rompe sin que nada avise. Esta prueba es esa alarma: compara
cada caso de corpus_resolver.py contra snapshot_resolver.json.

Que se fija por caso:
  - valido: el diccionario resuelto completo (incluye avisos y trazabilidad) y,
    con una semilla fija, el resumen de simular() y una huella de su serie;
  - invalido: la lista exacta de errores, en orden.

Ademas comprueba que el corpus pase por cada `errores.append` y
`avisos.append` de motor/parametros.py: si alguien agrega una validacion, la
prueba le pide el caso que la ejercite.

Si un cambio de resultados es intencional, va con un nuevo ENGINE_VERSION y se
regenera el archivo (desde procesamiento/):
    python -m tests.test_caracterizacion_motor --regenerar

Ejecutar:
    cd procesamiento && python -m unittest tests.test_caracterizacion_motor -v
"""
import ast
import hashlib
import json
import pathlib
import sys
import unittest

from motor import parametros, simular
from motor.parametros import EscenarioInvalido, resolver
from tests.corpus_resolver import INVALIDOS, VALIDOS

SNAPSHOT = pathlib.Path(__file__).with_name("snapshot_resolver.json")
SEMILLA = 20261004


def _huella_serie(serie):
    canonico = json.dumps(serie, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _foto_valido(escenario):
    resultado = simular(escenario, semilla=SEMILLA)
    return {
        "resuelto": resolver(escenario),
        "simulacion": {
            "engine_version": resultado["engine_version"],
            "resumen": resultado["resumen"],
            "serie_sha256": _huella_serie(resultado["serie"]),
        },
    }


def _foto_invalido(escenario):
    try:
        resolver(escenario)
    except EscenarioInvalido as exc:
        return {"errores": exc.errores}
    raise AssertionError("el caso se marco invalido pero resolver() lo acepto")


def foto_actual():
    """La salida de hoy para todo el corpus, en la forma del archivo."""
    foto = {nombre: _foto_valido(e) for nombre, (_, e) in VALIDOS.items()}
    foto.update({nombre: _foto_invalido(e) for nombre, (_, e) in INVALIDOS.items()})
    # Ida y vuelta por JSON para comparar lo mismo que se guarda.
    return json.loads(json.dumps(foto, sort_keys=True, default=str))


def _lineas_de_append():
    """Lineas de parametros.py con errores.append(...) o avisos.append(...)."""
    arbol = ast.parse(pathlib.Path(parametros.__file__).read_text(encoding="utf-8"))
    return {n.lineno for n in ast.walk(arbol)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "append" and isinstance(n.func.value, ast.Name)
            and n.func.value.id in ("errores", "avisos")}


def _lineas_ejecutadas():
    archivo = pathlib.Path(parametros.__file__).resolve()
    vistas = set()

    def traza(marco, evento, _arg):
        if pathlib.Path(marco.f_code.co_filename).resolve() != archivo:
            return None
        if evento == "line":
            vistas.add(marco.f_lineno)
        return traza

    anterior = sys.gettrace()
    sys.settrace(traza)
    try:
        for _, escenario in list(VALIDOS.values()) + list(INVALIDOS.values()):
            try:
                resolver(escenario)
            except EscenarioInvalido:
                pass
    finally:
        sys.settrace(anterior)
    return vistas


class CaracterizacionResolverTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.guardada = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.actual = foto_actual()

    def test_el_archivo_tiene_exactamente_los_casos_del_corpus(self):
        self.assertEqual(sorted(self.guardada), sorted(self.actual))

    def test_cada_caso_valido_resuelve_y_simula_igual(self):
        for nombre in VALIDOS:
            with self.subTest(caso=nombre):
                self.assertEqual(self.actual[nombre], self.guardada[nombre])

    def test_cada_caso_invalido_da_los_mismos_errores_en_el_mismo_orden(self):
        for nombre in INVALIDOS:
            with self.subTest(caso=nombre):
                self.assertEqual(self.actual[nombre], self.guardada[nombre])

    def test_el_corpus_pasa_por_cada_error_y_cada_aviso(self):
        faltan = sorted(_lineas_de_append() - _lineas_ejecutadas())
        self.assertEqual(faltan, [], "lineas de motor/parametros.py sin un caso en "
                                     f"corpus_resolver.py: {faltan}")


if __name__ == "__main__":
    if "--regenerar" in sys.argv:
        SNAPSHOT.write_text(json.dumps(foto_actual(), indent=1, sort_keys=True,
                                       ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"escrito {SNAPSHOT} ({len(VALIDOS)} validos, {len(INVALIDOS)} invalidos)")
    else:
        unittest.main()
