"""
Contrato de backend_web/conversion.py. Los mensajes de cada formulario los fija
test_caracterizacion_formularios; aqui va lo que la firma promete, y que el
corpus de esa prueba pase por cada mensaje de este modulo: si alguien agrega
uno, la prueba le pide el caso.

Ejecutar:
    python -m unittest backend_web.tests.test_conversion -v
"""
import ast
import pathlib
import sys
import unittest
from datetime import date

from backend_web import conversion
from backend_web.tests.test_caracterizacion_formularios import foto_actual

CONVERSION = pathlib.Path(conversion.__file__)


def _lineas_de_append():
    arbol = ast.parse(CONVERSION.read_text(encoding="utf-8"))
    return {n.lineno for n in ast.walk(arbol)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "append" and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "errores"}


def _lineas_ejecutadas():
    archivo = CONVERSION.resolve()
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
        foto_actual()
    finally:
        sys.settrace(anterior)
    return vistas


class CorpusCubreConversionTests(unittest.TestCase):
    def test_el_corpus_pasa_por_cada_mensaje_de_conversion(self):
        faltan = sorted(_lineas_de_append() - _lineas_ejecutadas())
        self.assertEqual(faltan, [], "lineas de backend_web/conversion.py sin un caso en "
                                     f"corpus_formularios.py: {faltan}")


class EnteroTests(unittest.TestCase):
    def test_los_limites_y_la_etiqueta_solo_entran_por_nombre(self):
        """Habia dos parseadores de enteros con los mismos datos en distinto
        orden; cruzar `minimo` con `etiqueta` no tronaba, solo daba rangos o
        mensajes equivocados. Con argumentos por nombre, el cruce es un TypeError."""
        with self.assertRaises(TypeError):
            conversion.entero("5", [], "La edad", 0, 120)

    def test_con_miles_acepta_comas_y_las_escribe_en_el_mensaje(self):
        errores = []
        self.assertEqual(conversion.entero("1,500", errores, etiqueta="La población",
                                           minimo=1000, maximo=20_000_000), 1500)
        self.assertIsNone(conversion.entero("999", errores, etiqueta="La población",
                                            minimo=1000, maximo=20_000_000))
        self.assertEqual(errores, ["La población debe estar entre 1,000 y 20,000,000."])

    def test_sin_miles_una_coma_no_es_un_entero(self):
        errores = []
        self.assertIsNone(conversion.entero("1,500", errores, etiqueta="La edad",
                                            minimo=0, maximo=2000, miles=False))
        conversion.entero("2001", errores, etiqueta="La edad", minimo=0, maximo=2000,
                          miles=False)
        self.assertEqual(errores, ["La edad debe ser un número entero.",
                                   "La edad debe estar entre 0 y 2000."])

    def test_vacio_obligatorio_y_opcional(self):
        errores = []
        for vacio in (None, "", "   "):
            self.assertIsNone(conversion.entero(vacio, errores, etiqueta="La región",
                                                minimo=1, maximo=9))
        self.assertIsNone(conversion.entero("", errores, etiqueta="La edad", minimo=0,
                                            maximo=9, obligatorio=False))
        self.assertEqual(errores, ["La región es obligatoria."] * 3)

    def test_los_mensajes_concuerdan_con_el_articulo_de_la_etiqueta(self):
        """Antes el genero lo fijaba la funcion, no la etiqueta, y salian cosas
        como "La enfermedad es obligatorio." o "Los infectados iniciales es
        obligatoria."."""
        casos = {
            "El municipio": ["El municipio es obligatorio.",
                             "El municipio debe ser un número entero.",
                             "El municipio debe estar entre 1 y 9."],
            "La enfermedad": ["La enfermedad es obligatoria.",
                              "La enfermedad debe ser un número entero.",
                              "La enfermedad debe estar entre 1 y 9."],
            "Los infectados iniciales": ["Los infectados iniciales son obligatorios.",
                                         "Los infectados iniciales deben ser un número entero.",
                                         "Los infectados iniciales deben estar entre 1 y 9."],
            "Las dosis": ["Las dosis son obligatorias.",
                          "Las dosis deben ser un número entero.",
                          "Las dosis deben estar entre 1 y 9."],
            "«dias»": ["«dias» es obligatorio.",
                       "«dias» debe ser un número entero.",
                       "«dias» debe estar entre 1 y 9."],
        }
        for etiqueta, esperados in casos.items():
            with self.subTest(etiqueta=etiqueta):
                errores = []
                for valor in ("", "x", "10"):
                    conversion.entero(valor, errores, etiqueta=etiqueta, minimo=1, maximo=9)
                self.assertEqual(errores, esperados)
        errores = []
        conversion.fecha("", errores, etiqueta="El día del reporte")
        self.assertEqual(errores, ["El día del reporte es obligatorio."])


class DecimalYFechaTests(unittest.TestCase):
    def test_decimal_es_opcional_y_acotado(self):
        errores = []
        self.assertIsNone(conversion.decimal("", errores, etiqueta="La latitud",
                                             minimo=-90, maximo=90))
        self.assertEqual(conversion.decimal(" 25.6 ", errores, etiqueta="La latitud",
                                            minimo=-90, maximo=90), 25.6)
        conversion.decimal("91", errores, etiqueta="La latitud", minimo=-90, maximo=90)
        self.assertEqual(errores, ["La latitud debe estar entre -90 y 90."])

    def test_fecha(self):
        errores = []
        self.assertEqual(conversion.fecha("2025-01-15", errores, etiqueta="La fecha"),
                         date(2025, 1, 15))
        self.assertIsNone(conversion.fecha("", errores, etiqueta="La fecha",
                                           obligatorio=False))
        conversion.fecha("", errores, etiqueta="La fecha")
        conversion.fecha("2025-02-30", errores, etiqueta="La fecha")
        self.assertEqual(errores, ["La fecha es obligatoria.",
                                   "La fecha no tiene un formato de fecha válido."])


class NumeroDeEsquemaTests(unittest.TestCase):
    def test_cada_limite_es_opcional_e_inclusivo(self):
        errores = []
        spec = {"minimum": 1, "maximum": 30}
        self.assertEqual(conversion.numero_de_esquema("1", errores, etiqueta="«d»",
                                                      spec=spec, tipo=int), 1)
        self.assertEqual(conversion.numero_de_esquema("30", errores, etiqueta="«d»",
                                                      spec=spec, tipo=int), 30)
        self.assertEqual(conversion.numero_de_esquema("-5", errores, etiqueta="«d»",
                                                      spec={"maximum": 30}, tipo=float), -5.0)
        conversion.numero_de_esquema("0", errores, etiqueta="«d»", spec=spec, tipo=int)
        conversion.numero_de_esquema("31", errores, etiqueta="«d»", spec=spec, tipo=int)
        conversion.numero_de_esquema("1.5", errores, etiqueta="«d»", spec=spec, tipo=int)
        self.assertEqual(errores, ["«d» no puede ser menor que 1.",
                                   "«d» no puede ser mayor que 30.",
                                   "«d» debe ser un número entero."])


class NoFinitosTests(unittest.TestCase):
    """float() acepta "nan" e "inf". nan no es menor ni mayor que nada, asi que
    pasaba cualquier limite; un parametro de intervencion con nan llegaba a la
    columna jsonb, PostgreSQL lo rechazaba y la ruta respondia 500."""

    NO_FINITOS = ("nan", "NaN", "inf", "-inf", "Infinity", "1e400")

    def test_numero_de_esquema_los_rechaza_con_o_sin_limites(self):
        for spec in ({"minimum": 0, "maximum": 1}, {"minimum": 0}, {}):
            for texto in self.NO_FINITOS:
                with self.subTest(spec=spec, texto=texto):
                    errores = []
                    self.assertIsNone(conversion.numero_de_esquema(
                        texto, errores, etiqueta="«reduccion»", spec=spec, tipo=float))
                    self.assertEqual(errores, ["«reduccion» debe ser un número."])

    def test_decimal_los_rechaza(self):
        for texto in self.NO_FINITOS:
            with self.subTest(texto=texto):
                errores = []
                self.assertIsNone(conversion.decimal(texto, errores, etiqueta="La latitud",
                                                     minimo=-90, maximo=90))
                self.assertEqual(errores, ["La latitud debe ser un número."])


if __name__ == "__main__":
    unittest.main()
