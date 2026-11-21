import unittest

from procesamiento.entrada_motor import entrada_de_version
from procesamiento.motor import simular

PARAMETROS = {
    "r0": {"valor": 1.8, "fuente": "prueba", "supuesto": False},
    "incubacion_dias": {"valor": 2.0, "supuesto": True},
    "infeccioso_dias": {"valor": 4.0, "supuesto": True},
    "dias_hospitalizacion": {"valor": 7.0, "supuesto": True},
    "tasa_hospitalizacion": {"valor": 0.02, "supuesto": True},
    "letalidad": {"valor": 0.005, "supuesto": True},
}


def version(**cambios):
    datos = {"id": 7, "scenario_id": 3, "version_number": 2, "status": "aprobado",
             "population_size": 10000, "horizon_days": 30, "initial_infected": 10,
             "population_by_age": None, "population_age_unknown": 0, "age_unknown_policy": None,
             "disease_params": None, "default_params": PARAMETROS}
    datos.update(cambios)
    return datos


class EntradaDeVersionTests(unittest.TestCase):
    def test_una_version_aprobada_da_la_entrada_que_el_motor_acepta(self):
        escenario, _, errores = entrada_de_version(version(), [])
        self.assertEqual(errores, [])
        self.assertEqual((escenario["poblacion"], escenario["dias"]), (10000, 30))
        self.assertEqual(simular(escenario, 1)["dias"], 30)

    def test_los_parametros_congelados_mandan_sobre_los_vivos(self):
        congelados = dict(PARAMETROS, r0={"valor": 2.5, "fuente": "otra", "supuesto": False})
        escenario, _, _ = entrada_de_version(version(disease_params=congelados), [])
        self.assertEqual(escenario["enfermedad"]["r0"]["valor"], 2.5)

    def test_traduce_las_intervenciones(self):
        fila = {"code": "CIERRE_ESCUELAS", "start_day": 5, "end_day": 20, "coverage": "0.5",
                "compliance": None, "params": None}
        escenario, _, _ = entrada_de_version(version(), [fila])
        self.assertEqual(escenario["intervenciones"], [
            {"tipo": "CIERRE_ESCUELAS", "dia_inicio": 5, "dia_fin": 20, "cobertura": 0.5,
             "cumplimiento": None, "params": {}}])

    def test_no_simula_una_version_que_no_esta_aprobada(self):
        escenario, fila, errores = entrada_de_version(version(status="borrador"), [])
        self.assertIsNone(escenario)
        self.assertEqual(fila["id"], 7)
        self.assertIn("ESC-003", errores[0])
        self.assertIn("no esta aprobada", errores[0])

    def test_se_niega_a_simular_parametros_sin_fuente(self):
        sin_fuente = dict(PARAMETROS, r0={"valor": 1.8, "supuesto": False})
        escenario, _, errores = entrada_de_version(version(default_params=sin_fuente), [])
        self.assertIsNone(escenario)
        self.assertIn("no se puede simular", errores[0])

    def test_una_version_que_no_existe(self):
        self.assertEqual(entrada_de_version(None, []),
                         (None, None, ["La version de escenario no existe."]))


if __name__ == "__main__":
    unittest.main()
