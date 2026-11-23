import unittest

from epidemia_comun.bd import query
from microservicios.parametros import datos
from microservicios.parametros.reglas import parametros_epidemiologicos
from microservicios.pruebas_bd import contexto_de_prueba, escribe, tiene_base


# Contra la base de pruebas, con la 042. Cambia los parámetros de PATOGENO_X y los deja como estaban.
@unittest.skipUnless(tiene_base(), "Requiere la base de pruebas")
class ParametrosBdTests(unittest.TestCase):
    def setUp(self):
        fila = query("SELECT id, default_params FROM diseases WHERE code = 'PATOGENO_X'", one=True)
        self.disease_id, self.params = fila["id"], fila["default_params"]
        self.versiones = [v["version"] for v in datos.versiones(self.disease_id)]
        self.addCleanup(escribe, "DELETE FROM disease_parameter_versions WHERE disease_id = %s AND version > %s",
                        (self.disease_id, max(self.versiones)))
        self.addCleanup(escribe, "UPDATE diseases SET default_params = %s::jsonb WHERE id = %s",
                        (__import__("json").dumps(self.params), self.disease_id))

    def test_la_042_trae_la_version_1_y_los_intervalos_de_las_fuentes(self):
        covid = query("SELECT id, default_params FROM diseases WHERE code = 'SARS_COV_2_ANCESTRAL'", one=True)
        self.assertEqual(covid["default_params"]["r0"]["intervalo"], {"min": 2.39, "max": 3.44, "tipo": "IC95"})
        uno = datos.version(covid["id"], 1)
        self.assertNotIn("intervalo", uno["params"]["r0"])
        self.assertEqual(datos.version(covid["id"], 2)["params"], covid["default_params"])
        self.assertEqual(self.versiones, [1])

    def test_cada_cambio_guarda_su_version_completa(self):
        nuevos, numero = datos.guardar(
            self.disease_id,
            lambda anteriores: parametros_epidemiologicos(
                {"r0": {"valor": 1.5, "supuesto": True, "intervalo": {"min": 1.0, "max": 2.0}}}, anteriores),
            "Prueba", contexto=contexto_de_prueba(query("SELECT min(id) AS id FROM users", one=True)["id"]))
        self.assertEqual(numero, 2)
        guardada = datos.version(self.disease_id, 2)
        self.assertEqual((guardada["params"], guardada["reason"]), (nuevos, "Prueba"))
        self.assertEqual(datos.parametros(self.disease_id)["r0"]["intervalo"]["tipo"], "rango")
        asiento = query("""SELECT data_after FROM audit_log WHERE entity_type = 'diseases' AND entity_id = %s
                           ORDER BY id DESC LIMIT 1""", (str(self.disease_id),), one=True)
        self.assertEqual(asiento["data_after"]["version_parametros"], 2)
