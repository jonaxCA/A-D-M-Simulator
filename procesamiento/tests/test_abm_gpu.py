"""Pruebas propias de abm-gpu, el ABM en FLAME GPU 2. El contrato (forma de la salida,
reproducibilidad, errores) lo revisan las de test_contrato_motor.py, que incluyen a abm-gpu
cuando corre en la máquina.

Necesitan pyflamegpu y una GPU de NVIDIA (procesamiento/abm_gpu/README.md); sin ellos se
saltan. Con el venv de FLAME GPU:

    C:/Temp/flamegpu/Scripts/python.exe -m pytest procesamiento/tests/test_abm_gpu.py -v

abm-gpu usa otro generador de azar que abm-ref, así que las comparaciones son de promedios de
varias semillas, no de corridas. La primera corrida de cada tamaño de población tarda unos
segundos más: FLAME GPU compila las funciones de agente y las guarda para las siguientes.
"""
import copy
import statistics
import unittest

from procesamiento import abm_gpu, contrato
from procesamiento.abm import poblacion
from procesamiento.abm import simular as simular_abm
from procesamiento.motor import simular as simular_seir
from procesamiento.tests import test_abm
from procesamiento.tests.test_abm import SEMILLAS, casos_de, escenario

DISPONIBLE, MOTIVO = abm_gpu.disponible()
simular_gpu = abm_gpu.simular


def promedio(simular, esc, campo="tasa_ataque"):
    return statistics.mean(simular(copy.deepcopy(esc), s)["resumen"][campo] for s in SEMILLAS)


@unittest.skipUnless(DISPONIBLE, "abm-gpu no corre en esta máquina: %s" % MOTIVO)
class MismoModeloQueAbmRefTests(unittest.TestCase):
    """abm-gpu es abm-ref en otra máquina: mismas fórmulas, misma población inicial."""

    def test_arranca_con_la_misma_poblacion_que_abm_ref(self):
        """Mismos grupos de contacto e infectados iniciales con la misma semilla: con un día y
        casi sin contagio, los casos por grupo de edad son los iniciales en los dos."""
        esc = escenario(r0=0.01, dias=1)
        for semilla in (3, 4):
            with self.subTest(semilla=semilla):
                gpu = simular_gpu(copy.deepcopy(esc), semilla)
                cpu = simular_abm(copy.deepcopy(esc), semilla)
                self.assertEqual(gpu["serie"][0], cpu["serie"][0])
                for grupo in esc["poblacion"]:
                    self.assertEqual(casos_de(gpu, grupo), casos_de(cpu, grupo))
                self.assertEqual(gpu["trazabilidad_parametros"], cpu["trazabilidad_parametros"])

    def test_con_un_solo_grupo_por_capa_da_lo_mismo_que_el_seir(self):
        original = dict(poblacion.TAMANO_MEDIO)
        poblacion.TAMANO_MEDIO.update({capa: 10 ** 9 for capa in original})
        try:
            gpu = promedio(simular_gpu, escenario(r0=2.0))
        finally:
            poblacion.TAMANO_MEDIO.update(original)
        self.assertAlmostEqual(gpu, promedio(simular_seir, escenario(r0=2.0)), delta=0.03)

    def test_con_hogares_salones_y_trabajos_da_lo_mismo_que_abm_ref(self):
        """Cerca del umbral una corrida de 20 000 agentes varía mucho (de 0.33 a 0.56 de
        ataque con R0 = 1.6), así que ahí se usan 100 000."""
        for r0, factor in ((1.6, 2.0), (2.5, 0.4)):
            with self.subTest(r0=r0):
                esc = escenario(r0=r0, factor=factor)
                self.assertAlmostEqual(promedio(simular_gpu, esc), promedio(simular_abm, esc),
                                       delta=0.04)

    def test_cerrar_escuelas_protege_sobre_todo_a_los_escolares(self):
        cierre = {"tipo": "CIERRE_ESCUELAS", "dia_inicio": 0, "dia_fin": None, "cobertura": 1.0,
                  "cumplimiento": 1.0, "params": {"reduccion": 1.0}}
        abiertas = [simular_gpu(escenario(r0=2.0), s) for s in SEMILLAS]
        cerradas = [simular_gpu(escenario(r0=2.0, intervenciones=[cierre]), s) for s in SEMILLAS]
        caida = {g: 1 - statistics.mean(casos_de(r, g) for r in cerradas)
                 / statistics.mean(casos_de(r, g) for r in abiertas) for g in ("0-19", "60-79")}
        self.assertGreater(caida["0-19"], caida["60-79"])
        self.assertGreater(caida["60-79"], 0)


@unittest.skipUnless(DISPONIBLE, "abm-gpu no corre en esta máquina: %s" % MOTIVO)
class VacunacionGpuTests(unittest.TestCase):
    VACUNA = test_abm.VacunacionTests.VACUNA

    def test_por_edad_empieza_por_los_mayores(self):
        """Las mismas dosis por grupo que abm-ref: el reparto se calcula igual."""
        r = simular_gpu(escenario(dias=10, intervenciones=[self.VACUNA]), 3)
        dosis = {g["grupo"]: g["dosis_aplicadas"] for g in r["resumen"]["desglose_por_grupo"]}
        self.assertEqual(r["resumen"]["dosis_aplicadas"], 1000)
        self.assertEqual(dosis["80+"], 279)
        self.assertEqual(dosis["60-79"], 1000 - 279)
        self.assertEqual(dosis["0-19"] + dosis["20-39"] + dosis["40-59"], 0)

    def test_nadie_pasa_del_tope_ni_recibe_dos_dosis(self):
        """Dos campañas a la vez sobre los mismos grupos: entre las dos nadie recibe dos dosis,
        así que nunca hay más dosis que personas, y cada una respeta su tope."""
        primera = copy.deepcopy(self.VACUNA)
        primera["params"].update(dosis_diarias=5000, prioridad="aleatorio")
        segunda = copy.deepcopy(primera)
        segunda["cobertura"] = 0.5
        esc = escenario(dias=30, intervenciones=[primera, segunda])
        r = simular_gpu(copy.deepcopy(esc), 4)
        self.assertEqual(contrato.revisa_salida(r, esc, 4, "abm-gpu"), [])
        for g in r["resumen"]["desglose_por_grupo"]:
            with self.subTest(grupo=g["grupo"]):
                self.assertLessEqual(g["dosis_aplicadas"], g["poblacion"])
                self.assertLessEqual(g["vacunados_protegidos"], g["dosis_aplicadas"])
                self.assertGreater(g["dosis_aplicadas"], 0)

    def test_vacunar_reduce_los_casos(self):
        self.assertLess(promedio(simular_gpu, escenario(r0=2.0, intervenciones=[self.VACUNA])),
                        promedio(simular_gpu, escenario(r0=2.0)))


@unittest.skipUnless(DISPONIBLE, "abm-gpu no corre en esta máquina: %s" % MOTIVO)
class EntornoTests(unittest.TestCase):
    def test_la_telemetria_de_flame_gpu_esta_apagada(self):
        self.assertFalse(abm_gpu.entorno.carga().Telemetry.isEnabled())

    def test_sin_grupos_de_edad_corre_y_lo_avisa(self):
        """Con un solo grupo de edad los arreglos del entorno tienen un elemento."""
        esc = escenario(dias=30)
        esc["poblacion"] = 20_000
        esc["enfermedad"]["tasa_hospitalizacion"] = 0.01
        esc["enfermedad"]["letalidad"] = 0.001
        r = simular_gpu(esc, 5)
        self.assertEqual(contrato.revisa_salida(r, esc, 5, "abm-gpu"), [])
        self.assertTrue(any("Censo 2020" in a for a in r["avisos"]))


if __name__ == "__main__":
    unittest.main()
