"""Pruebas propias de abm-ref, el modelo basado en agentes. El contrato (forma de la salida,
reproducibilidad, errores) lo revisan las de test_contrato_motor.py.

    python -m pytest procesamiento/tests/test_abm.py -v

Las comparaciones promedian varias semillas para no depender de la suerte de una corrida.
"""
import copy
import statistics
import unittest

import numpy as np

from procesamiento import contrato
from procesamiento.abm import poblacion
from procesamiento.abm import simular as simular_abm
from procesamiento.motor import simular as simular_seir

SEMILLAS = range(1, 5)


def escenario(r0=1.6, dias=120, factor=0.4, intervenciones=()):
    """El ejemplo del contrato, sin intervenciones y con 20 000 personas por omisión."""
    esc = copy.deepcopy(contrato.ESCENARIO_EJEMPLO)
    esc["poblacion"] = {g: round(n * factor) for g, n in esc["poblacion"].items()}
    esc["enfermedad"]["r0"]["valor"] = r0
    esc["dias"] = dias
    esc["intervenciones"] = list(intervenciones)
    return esc


def promedio(simular, esc, campo="tasa_ataque"):
    return statistics.mean(simular(copy.deepcopy(esc), s)["resumen"][campo] for s in SEMILLAS)


def casos_de(resultado, grupo):
    return next(g["casos"] for g in resultado["resumen"]["desglose_por_grupo"]
                if g["grupo"] == grupo)


class EstructuraTests(unittest.TestCase):
    """Lo que el ABM aporta frente al SEIR es la estructura de contactos (D2)."""

    def test_con_un_solo_grupo_por_capa_da_lo_mismo_que_el_seir(self):
        """Si cada capa fuera un solo grupo con todos, la fuerza de infección es la del SEIR:
        prueba que la fórmula del ABM no cambia nada más que la agrupación."""
        original = dict(poblacion.TAMANO_MEDIO)
        poblacion.TAMANO_MEDIO.update({capa: 10 ** 9 for capa in original})
        try:
            abm = promedio(simular_abm, escenario(r0=2.0))
        finally:
            poblacion.TAMANO_MEDIO.update(original)
        seir = promedio(simular_seir, escenario(r0=2.0))
        self.assertAlmostEqual(abm, seir, delta=0.03)

    def test_con_hogares_salones_y_trabajos_el_contagio_se_agota_antes(self):
        self.assertLess(promedio(simular_abm, escenario(r0=1.6)) + 0.05,
                        promedio(simular_seir, escenario(r0=1.6)))

    def test_cerrar_escuelas_protege_sobre_todo_a_los_escolares(self):
        cierre = {"tipo": "CIERRE_ESCUELAS", "dia_inicio": 0, "dia_fin": None, "cobertura": 1.0,
                  "cumplimiento": 1.0, "params": {"reduccion": 1.0}}
        abiertas = [simular_abm(escenario(r0=2.0), s) for s in SEMILLAS]
        cerradas = [simular_abm(escenario(r0=2.0, intervenciones=[cierre]), s) for s in SEMILLAS]
        for grupo in ("0-19", "60-79"):
            with self.subTest(grupo=grupo):
                self.assertLess(statistics.mean(casos_de(r, grupo) for r in cerradas),
                                statistics.mean(casos_de(r, grupo) for r in abiertas))
        # La caída relativa es mayor en quienes van a la escuela.
        caida = {g: 1 - statistics.mean(casos_de(r, g) for r in cerradas)
                 / statistics.mean(casos_de(r, g) for r in abiertas) for g in ("0-19", "60-79")}
        self.assertGreater(caida["0-19"], caida["60-79"])


class VacunacionTests(unittest.TestCase):
    VACUNA = {"tipo": "VACUNACION", "dia_inicio": 1, "cobertura": 0.9,
              "params": {"eficacia": 0.9, "dosis_diarias": 100, "prioridad": "edad_desc"}}

    def test_por_edad_empieza_por_los_mayores(self):
        r = simular_abm(escenario(dias=10, intervenciones=[self.VACUNA]), 3)
        dosis = {g["grupo"]: g["dosis_aplicadas"] for g in r["resumen"]["desglose_por_grupo"]}
        self.assertEqual(r["resumen"]["dosis_aplicadas"], 1000)
        # 80+ tiene 310 personas: con 90 % de cobertura caben 279 dosis y lo demás va a 60-79.
        self.assertEqual(dosis["80+"], 279)
        self.assertEqual(dosis["60-79"], 1000 - 279)
        self.assertEqual(dosis["0-19"] + dosis["20-39"] + dosis["40-59"], 0)

    def test_nadie_pasa_del_tope_ni_recibe_dos_dosis(self):
        vacuna = copy.deepcopy(self.VACUNA)
        vacuna["params"].update(dosis_diarias=5000, prioridad="aleatorio")
        r = simular_abm(escenario(dias=30, intervenciones=[vacuna]), 4)
        for g in r["resumen"]["desglose_por_grupo"]:
            with self.subTest(grupo=g["grupo"]):
                self.assertLessEqual(g["dosis_aplicadas"], int(0.9 * g["poblacion"]))
                self.assertLessEqual(g["vacunados_protegidos"], g["dosis_aplicadas"])

    def test_vacunar_reduce_los_casos(self):
        self.assertLess(promedio(simular_abm, escenario(r0=2.0, intervenciones=[self.VACUNA])),
                        promedio(simular_abm, escenario(r0=2.0)))


class PoblacionTests(unittest.TestCase):
    def test_los_grupos_de_contacto_siguen_la_edad(self):
        rng = np.random.default_rng(1)
        pob = [1000, 1000, 1000, 1000]
        grupo = np.repeat(np.arange(4), pob)
        capas, trazabilidad, avisos = poblacion.arma_capas(grupo, [0, 20, 40, 60], rng)
        self.assertTrue((capas["hogar"][0] >= 0).all(), "todos viven en un hogar")
        en_escuela = np.unique(grupo[capas["escuela"][0] >= 0])
        en_trabajo = np.unique(grupo[capas["trabajo"][0] >= 0])
        self.assertEqual(en_escuela.tolist(), [0])
        self.assertEqual(en_trabajo.tolist(), [1, 2])
        self.assertEqual(avisos, [])
        self.assertEqual({t["estado"] for t in trazabilidad}, {"supuesto"})

    def test_el_tamano_medio_de_los_grupos_es_el_supuesto(self):
        rng = np.random.default_rng(2)
        for capa, medio in poblacion.TAMANO_MEDIO.items():
            with self.subTest(capa=capa):
                numero, cuantos = poblacion.agrupa(np.arange(200_000), medio, rng)
                self.assertEqual(len(numero), 200_000)
                self.assertAlmostEqual(200_000 / cuantos, medio, delta=medio * 0.05)

    def test_sin_grupos_de_edad_sortea_con_el_censo_y_lo_avisa(self):
        esc = escenario(dias=30)
        esc["poblacion"] = 20_000
        esc["enfermedad"]["tasa_hospitalizacion"] = 0.01
        esc["enfermedad"]["letalidad"] = 0.001
        r = simular_abm(esc, 5)
        self.assertEqual(contrato.revisa_salida(r, esc, 5, "abm-ref"), [])
        self.assertTrue(any("Censo 2020" in a for a in r["avisos"]))
        self.assertIn("fraccion_escuela_trabajo",
                      [t["parametro"] for t in r["trazabilidad_parametros"]])


if __name__ == "__main__":
    unittest.main()
