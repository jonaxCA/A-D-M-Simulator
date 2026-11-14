"""Conformidad con el contrato de los motores (procesamiento/contrato.py, D2).

Los motores salen del registro (procesamiento/motores.py): uno nuevo pasa estas pruebas solo.

    python -m pytest procesamiento/tests/test_contrato_motor.py -v
"""
import copy
import json
import unittest

from procesamiento import contrato, motores
from procesamiento.motor import EscenarioInvalido
from procesamiento.motor import simular as simular_seir
from procesamiento.motor.modelo import huella_escenario

# nombre del motor -> su simular(escenario, semilla)
MOTORES_IMPLEMENTADOS = {nombre: m.simular for nombre, m in motores.IMPLEMENTADOS.items()}

ESCENARIO = contrato.ESCENARIO_EJEMPLO
SEMILLA = contrato.SEMILLA_EJEMPLO


class ConformidadTests(unittest.TestCase):
    def test_la_salida_cumple_el_contrato(self):
        for motor, simular in MOTORES_IMPLEMENTADOS.items():
            with self.subTest(motor=motor):
                salida = simular(copy.deepcopy(ESCENARIO), SEMILLA)
                self.assertEqual(contrato.revisa_salida(salida, ESCENARIO, SEMILLA, motor), [])

    def test_misma_entrada_y_semilla_dan_la_misma_salida(self):
        for motor, simular in MOTORES_IMPLEMENTADOS.items():
            with self.subTest(motor=motor):
                self.assertEqual(simular(copy.deepcopy(ESCENARIO), SEMILLA),
                                 simular(copy.deepcopy(ESCENARIO), SEMILLA))

    def test_otra_semilla_da_otra_serie(self):
        for motor, simular in MOTORES_IMPLEMENTADOS.items():
            with self.subTest(motor=motor):
                self.assertNotEqual(simular(copy.deepcopy(ESCENARIO), 1)["serie"],
                                    simular(copy.deepcopy(ESCENARIO), 2)["serie"])

    def test_no_modifica_el_escenario_que_recibe(self):
        for motor, simular in MOTORES_IMPLEMENTADOS.items():
            with self.subTest(motor=motor):
                escenario = copy.deepcopy(ESCENARIO)
                simular(escenario, SEMILLA)
                self.assertEqual(escenario, ESCENARIO)

    def test_un_escenario_invalido_es_escenario_invalido_con_todos_sus_errores(self):
        escenario = copy.deepcopy(ESCENARIO)
        del escenario["enfermedad"]["r0"]
        escenario["dias"] = 0
        for motor, simular in MOTORES_IMPLEMENTADOS.items():
            with self.subTest(motor=motor):
                with self.assertRaises(EscenarioInvalido) as error:
                    simular(copy.deepcopy(escenario), SEMILLA)
                self.assertGreaterEqual(len(error.exception.errores), 2)

    def test_una_semilla_invalida_es_value_error(self):
        for motor, simular in MOTORES_IMPLEMENTADOS.items():
            for semilla in (-1, 1.5, True, "7"):
                with self.subTest(motor=motor, semilla=semilla):
                    with self.assertRaises(ValueError):
                        simular(copy.deepcopy(ESCENARIO), semilla)


class RegistroTests(unittest.TestCase):
    def test_estan_seir_ref_y_abm_ref_con_los_nombres_de_d2(self):
        self.assertEqual(set(motores.IMPLEMENTADOS), {"seir-ref", "abm-ref"})
        self.assertLessEqual(set(motores.IMPLEMENTADOS), set(contrato.MOTORES))

    def test_version_y_simplificaciones_son_las_de_su_salida(self):
        for nombre, motor in motores.IMPLEMENTADOS.items():
            with self.subTest(motor=nombre):
                salida = motor.simular(copy.deepcopy(ESCENARIO), SEMILLA)
                self.assertEqual(salida["engine_version"], motor.version)
                self.assertEqual(salida["simplificaciones"], list(motor.simplificaciones))
                self.assertIs(motores.de_version(motor.version), motor)

    def test_un_motor_sin_implementar_o_desconocido_no_esta_disponible(self):
        for nombre in ("abm-gpu", "numba", "otro", None):
            with self.subTest(nombre=nombre):
                with self.assertRaises(motores.MotorNoDisponible):
                    motores.del_nombre(nombre)

    def test_las_versiones_anteriores_a_la_035_son_seir_ref(self):
        self.assertIs(motores.de_version("python-ref-0.1"), motores.IMPLEMENTADOS["seir-ref"])
        for version in ("abm-gpu-0.1", "sin-guion", "", None, 3):
            with self.subTest(version=version):
                self.assertIsNone(motores.de_version(version))


class ContratoTests(unittest.TestCase):
    """El revisor tiene que detectar lo que promete detectar."""

    def setUp(self):
        self.salida = simular_seir(copy.deepcopy(ESCENARIO), SEMILLA)

    def _problemas(self, cambio, motor="seir-ref"):
        salida = copy.deepcopy(self.salida)
        cambio(salida)
        return contrato.revisa_salida(salida, ESCENARIO, SEMILLA, motor)

    def test_detecta_salidas_que_no_cumplen(self):
        casos = {
            "falta una llave": lambda s: s.pop("avisos"),
            "otro motor en engine_version": lambda s: s.update(engine_version="python-ref-0.1"),
            "otra semilla": lambda s: s.update(semilla=SEMILLA + 1),
            "otra huella": lambda s: s.update(huella_escenario="0" * 64),
            "un día de menos": lambda s: s["serie"].pop(),
            "población que no se conserva": lambda s: s["serie"][3].update(S=s["serie"][3]["S"] + 1),
            "casos activos mal sumados": lambda s: s["serie"][2].update(casos_activos=-1),
            "resumen que no sale de la serie": lambda s: s["resumen"].update(fallecimientos=99),
            "pico en otro día": lambda s: s["resumen"].update(dia_pico=0),
            "desglose que no suma": lambda s: s["resumen"]["desglose_por_grupo"][0].update(casos=0),
            "traza sin estado válido": lambda s: s["trazabilidad_parametros"][0].update(estado="x"),
            "sin simplificaciones": lambda s: s.update(simplificaciones=[]),
            "un NaN": lambda s: s["resumen"].update(tasa_ataque=float("nan")),
        }
        for nombre, cambio in casos.items():
            with self.subTest(nombre):
                self.assertNotEqual(self._problemas(cambio), [])

    def test_un_motor_puede_agregar_llaves_propias(self):
        self.assertIn("numpy_version", self.salida)
        self.assertEqual(self._problemas(lambda s: s.update(extra={"a": 1})), [])

    def test_el_nombre_del_motor_debe_ser_uno_de_los_de_d2(self):
        self.assertNotEqual(self._problemas(lambda s: None, motor="python-ref"), [])

    def test_la_huella_es_la_del_seir(self):
        self.assertEqual(contrato.huella(ESCENARIO), huella_escenario(ESCENARIO))


class EjemplosTests(unittest.TestCase):
    """Los ejemplos de docs/contratos/motor/ son la salida real de seir-ref. Si cambian los
    números, se regeneran con `python -m procesamiento.contrato --ejemplos`."""

    def test_los_ejemplos_son_la_salida_de_seir_ref(self):
        entrada = json.loads((contrato.CARPETA_EJEMPLOS / "entrada.json").read_text(encoding="utf-8"))
        salida = json.loads((contrato.CARPETA_EJEMPLOS / "salida.json").read_text(encoding="utf-8"))
        self.assertEqual(entrada, {"escenario": ESCENARIO, "semilla": SEMILLA})
        real = json.loads(json.dumps(simular_seir(copy.deepcopy(ESCENARIO), SEMILLA)))
        # numpy_version depende de la máquina que generó el ejemplo.
        real.pop("numpy_version")
        salida.pop("numpy_version")
        self.assertEqual(salida, real)
        self.assertEqual(contrato.revisa_salida(salida, ESCENARIO, SEMILLA, "seir-ref"), [])


if __name__ == "__main__":
    unittest.main()
