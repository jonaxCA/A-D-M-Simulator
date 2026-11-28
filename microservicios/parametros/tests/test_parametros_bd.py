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


# La 044: los ajustes de una versión de escenario (D59). Crea un escenario con un borrador y lo borra.
@unittest.skipUnless(tiene_base(), "Requiere la base de pruebas")
class AjustesDeVersionBdTests(unittest.TestCase):
    def setUp(self):
        covid = query("SELECT id, default_params FROM diseases WHERE code = 'SARS_COV_2_ANCESTRAL'", one=True)
        self.catalogo = covid["default_params"]
        self.usuario = query("SELECT min(id) AS id FROM users", one=True)["id"]
        region = query("SELECT min(id) AS id FROM regions WHERE level = 'municipio'", one=True)["id"]
        escribe("INSERT INTO scenarios (name, disease_id, region_id, owner_id) VALUES ('AJUSTES D59', %s, %s, %s)",
                (covid["id"], region, self.usuario))
        self.escenario = query("SELECT max(id) AS id FROM scenarios WHERE name = 'AJUSTES D59'", one=True)["id"]
        escribe("""INSERT INTO scenario_versions (scenario_id, version_number, is_current, population_size, horizon_days,
                                                  initial_infected, created_by, status)
                   VALUES (%s, 1, true, 100000, 60, 10, %s, 'borrador')""", (self.escenario, self.usuario))
        self.version = query("SELECT id FROM scenario_versions WHERE scenario_id = %s", (self.escenario,), one=True)["id"]
        self.addCleanup(escribe, "DELETE FROM scenarios WHERE id = %s", (self.escenario,))
        self.addCleanup(escribe, "DELETE FROM scenario_versions WHERE scenario_id = %s", (self.escenario,))

    def efectivos(self):
        return query("""SELECT coalesce(v.disease_params, d.default_params || v.param_overrides) AS p
                        FROM scenario_versions v JOIN scenarios s ON s.id = v.scenario_id
                        JOIN diseases d ON d.id = s.disease_id WHERE v.id = %s""", (self.version,), one=True)["p"]

    def test_la_version_nace_sin_ajustes_y_usa_el_catalogo(self):
        fila = datos.version_de_escenario(self.version)
        self.assertEqual(fila["param_overrides"], {})
        self.assertEqual(self.efectivos(), self.catalogo)

    def test_un_ajuste_cambia_lo_efectivo_y_no_el_catalogo(self):
        nuevos = datos.guardar_ajustes(
            self.version, lambda v: None,
            lambda previos: parametros_epidemiologicos({"r0": {"valor": 3.2, "supuesto": True}}, previos),
            contexto=contexto_de_prueba(self.usuario))
        self.assertEqual(nuevos["r0"]["valor"], 3.2)
        efectivos = self.efectivos()
        self.assertEqual(efectivos["r0"], {"valor": 3.2, "fuente": None, "supuesto": True})
        self.assertEqual(efectivos["incubacion_dias"], self.catalogo["incubacion_dias"])
        self.assertEqual(query("SELECT default_params FROM diseases WHERE code = 'SARS_COV_2_ANCESTRAL'",
                               one=True)["default_params"], self.catalogo)
        asiento = query("""SELECT data_before, data_after FROM audit_log WHERE entity_type = 'scenario_versions'
                           AND entity_id = %s ORDER BY id DESC LIMIT 1""", (str(self.version),), one=True)
        self.assertEqual(asiento["data_before"]["param_overrides"], {})
        self.assertEqual(asiento["data_after"]["param_overrides"]["r0"]["valor"], 3.2)

    def test_una_versión_enviada_usa_su_foto_aunque_cambie_el_catalogo(self):
        datos.guardar_ajustes(self.version, lambda v: None,
                              lambda previos: parametros_epidemiologicos({"r0": {"valor": 3.2, "supuesto": True}}, previos),
                              contexto=contexto_de_prueba(self.usuario))
        escribe("UPDATE scenario_versions SET disease_params = %s::jsonb WHERE id = %s",
                (__import__("json").dumps(dict(self.catalogo, r0={"valor": 3.2, "fuente": None, "supuesto": True})),
                 self.version))
        escribe("UPDATE scenario_versions SET param_overrides = '{}'::jsonb WHERE id = %s", (self.version,))
        self.assertEqual(self.efectivos()["r0"]["valor"], 3.2)

    def test_los_ajustes_deben_ser_un_objeto(self):
        with self.assertRaises(Exception):
            escribe("UPDATE scenario_versions SET param_overrides = '[]'::jsonb WHERE id = %s", (self.version,))
