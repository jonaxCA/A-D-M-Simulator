"""El factor de escala de D6 (procesamiento/analitica/escala.py): los agentes simulados contra
los habitantes de la región, fuera del motor.

    python -m pytest procesamiento/tests/test_escala.py -v
"""
import unittest

from procesamiento.analitica import INDICADORES_ESCALABLES, factor_de_escala, representados

RESUMEN = {"casos_acumulados": 1000, "casos_activos_final": 10, "pico_casos_activos": 120,
           "dia_pico": 40, "pico_nuevos_casos": 30, "dia_pico_nuevos_casos": 38,
           "hospitalizaciones": 7, "pico_hospitalizados": 3, "dia_pico_hospitalizados": 41,
           "fallecimientos": 1, "tasa_ataque": 0.002, "vacunados_protegidos": 0,
           "dosis_aplicadas": 0, "desglose_por_grupo": []}


class FactorTests(unittest.TestCase):
    def test_un_agente_por_habitante_es_factor_1(self):
        escala = factor_de_escala(1_142_994, 1_142_994)
        self.assertEqual((escala["factor"], escala["avisos"]), (1.0, []))
        self.assertEqual(representados(RESUMEN, escala)["casos_acumulados"], 1000)

    def test_menos_agentes_que_habitantes(self):
        # El escenario de la demo: 500 000 agentes para Nuevo León.
        escala = factor_de_escala(5_784_442, 500_000)
        self.assertEqual(escala["factor"], 11.5689)
        self.assertIn("Censo 2020", escala["fuente"])
        llevados = representados(RESUMEN, escala)
        self.assertEqual(llevados["casos_acumulados"], round(1000 * 5_784_442 / 500_000))
        self.assertEqual(llevados["fallecimientos"], 12)

    def test_solo_se_escalan_los_conteos(self):
        llevados = representados(RESUMEN, factor_de_escala(2000, 1000))
        self.assertEqual(set(llevados), set(INDICADORES_ESCALABLES))
        for campo in ("tasa_ataque", "dia_pico", "desglose_por_grupo"):
            self.assertNotIn(campo, llevados)

    def test_mas_agentes_que_habitantes_avisa(self):
        escala = factor_de_escala(1000, 5000)
        self.assertEqual(escala["factor"], 0.2)
        self.assertEqual(len(escala["avisos"]), 1)
        self.assertIn("menos de una persona", escala["avisos"][0])

    def test_sin_datos_no_hay_factor_ni_numeros_escalados(self):
        for habitantes, agentes in ((None, 1000), (0, 1000), (1000, 0), (1000, None), (True, 5)):
            with self.subTest(habitantes=habitantes, agentes=agentes):
                escala = factor_de_escala(habitantes, agentes)
                self.assertIsNone(escala["factor"])
                self.assertTrue(escala["avisos"])
                self.assertEqual(representados(RESUMEN, escala), {})


if __name__ == "__main__":
    unittest.main()
