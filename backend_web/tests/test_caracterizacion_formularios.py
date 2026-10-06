"""
Caracterizacion de las valida_* de queries.py: su salida, hoy, fijada en un
archivo.

POR QUE EXISTE
Lo que la persona ve cuando un formulario no pasa es el texto de cada error.
La conversion de texto a numero o fecha la comparten varios formularios; un
cambio ahi puede alterar un mensaje, o aceptar algo que antes se rechazaba, en
una pantalla que nadie volvio a abrir. Esta prueba compara cada caso de
corpus_formularios.py (datos convertidos y lista exacta de errores, en orden)
contra snapshot_formularios.json.

No usa la base: con un formulario invalido valida_escenario no la consulta, y
si algun caso llegara a hacerlo la prueba falla en vez de conectarse.

Si un cambio de mensajes es intencional, se regenera el archivo:
    python -m backend_web.tests.test_caracterizacion_formularios --regenerar

Ejecutar:
    python -m unittest backend_web.tests.test_caracterizacion_formularios -v
"""
import json
import math
import pathlib
import sys
import unittest
from unittest.mock import patch

from backend_web import queries
from backend_web.tests.corpus_formularios import (CASOS, ENFERMEDADES, EXISTENTES,
                                                  PARAMETROS_ENFERMEDAD, REGIONES,
                                                  TIPOS, VERSION)

SNAPSHOT = pathlib.Path(__file__).with_name("snapshot_formularios.json")

LLAMADAS = {
    "valida_caso": lambda form: queries.valida_caso(form),
    "valida_escenario": lambda form: queries.valida_escenario(form, REGIONES, ENFERMEDADES),
    "valida_version": lambda form: queries.valida_version(form, REGIONES[0],
                                                          PARAMETROS_ENFERMEDAD),
    "valida_intervencion": lambda form: queries.valida_intervencion(form, TIPOS, VERSION,
                                                                    EXISTENTES),
}


def _sin_base(*_args, **_kwargs):
    raise AssertionError("un caso del corpus llego a consultar la base")


def _comparable(valor):
    """Lo que JSON no distingue o no compara, escrito con su tipo: una fecha
    no debe confundirse con la cadena que la escribe, y NaN no es igual a NaN."""
    if isinstance(valor, dict):
        return {k: _comparable(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_comparable(v) for v in valor]
    if isinstance(valor, float) and not math.isfinite(valor):
        return f"float:{valor}"
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    return f"{type(valor).__name__}:{valor}"


def _foto(validador, form):
    with patch.object(queries, "query", _sin_base):
        datos, errores = LLAMADAS[validador](form)
    return _comparable({"datos": datos, "errores": errores})


def foto_actual():
    """La salida de hoy para todo el corpus, en la forma del archivo."""
    foto = {nombre: _foto(validador, form) for nombre, (_, validador, form) in CASOS.items()}
    # Ida y vuelta por JSON para comparar lo mismo que se guarda.
    return json.loads(json.dumps(foto, sort_keys=True))


class CaracterizacionFormulariosTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.guardada = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.actual = foto_actual()

    def test_el_archivo_tiene_exactamente_los_casos_del_corpus(self):
        self.assertEqual(sorted(self.guardada), sorted(self.actual))

    def test_cada_formulario_da_los_mismos_datos_y_errores(self):
        for nombre in CASOS:
            with self.subTest(caso=nombre):
                self.assertEqual(self.actual[nombre], self.guardada[nombre])


if __name__ == "__main__":
    if "--regenerar" in sys.argv:
        SNAPSHOT.write_text(json.dumps(foto_actual(), indent=1, sort_keys=True,
                                       ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"escrito {SNAPSHOT} ({len(CASOS)} casos)")
    else:
        unittest.main()
