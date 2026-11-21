import json
import unittest

from procesamiento.analitica import (PARAMETROS, SensibilidadInvalida, sensibilidad,
                                     valores_por_porcentaje)

from .test_motor import escenario


class Sensibilidad(unittest.TestCase):
    def test_r0_mayor_da_mas_fallecimientos(self):
        r = sensibilidad(escenario(), "r0", [1.4, 2.2])
        medias = [f["media"] for f in r["filas"]]
        self.assertEqual([f["valor"] for f in r["filas"]], [1.4, 1.8, 2.2])
        self.assertEqual(medias, sorted(medias))
        base = r["filas"][1]
        self.assertTrue(base["es_base"])
        self.assertEqual(base["diferencia_vs_base"], 0)

    def test_siempre_exploratoria_y_serializable(self):
        r = sensibilidad(escenario(), "incubacion_dias", [3.0], "hospitalizaciones")
        self.assertEqual(r["categoria"], "exploratoria")
        self.assertEqual(r["metrica"], "hospitalizaciones")
        json.dumps(r)

    def test_es_determinista_y_no_toca_el_escenario(self):
        esc = escenario()
        self.assertEqual(sensibilidad(esc, "r0", [1.5]), sensibilidad(esc, "r0", [1.5]))
        self.assertEqual(esc, escenario())

    def test_valor_igual_a_la_base_no_se_repite(self):
        r = sensibilidad(escenario(), "r0", [1.8, 2.0])
        self.assertEqual(len(r["filas"]), 2)

    def test_porcentajes(self):
        self.assertEqual(valores_por_porcentaje(escenario(), "r0", [-50, 50]), [0.9, 2.7])

    def test_entradas_invalidas(self):
        for parametro, valores, metrica in [("letalidad", [1], "fallecimientos"),
                                            ("r0", [], "fallecimientos"),
                                            ("r0", [0], "fallecimientos"),
                                            ("r0", [True], "fallecimientos"),
                                            ("r0", list(range(1, 11)), "fallecimientos"),
                                            ("r0", [1.5], "costo")]:
            with self.assertRaises(SensibilidadInvalida):
                sensibilidad(escenario(), parametro, valores, metrica)

    def test_escenario_que_el_motor_rechaza(self):
        esc = escenario(dias=0)
        with self.assertRaises(SensibilidadInvalida):
            sensibilidad(esc, "r0", [1.5])

    def test_parametros(self):
        self.assertIn("r0", PARAMETROS)
