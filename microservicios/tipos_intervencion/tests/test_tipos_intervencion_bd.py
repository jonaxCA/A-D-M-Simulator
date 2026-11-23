import unittest

from epidemia_comun.bd import query
from microservicios.pruebas_bd import contexto_de_prueba, escribe, tiene_base
from microservicios.tipos_intervencion import datos


# Contra la base de pruebas, con la 042. Agrega un supuesto de cubrebocas para influenza y lo borra.
@unittest.skipUnless(tiene_base(), "Requiere la base de pruebas")
class TiposBdTests(unittest.TestCase):
    def setUp(self):
        self.tipos = {t["code"]: t for t in datos.tipos()}
        self.influenza = datos.enfermedad_id("INFLUENZA_ESTACIONAL")
        self.addCleanup(escribe, "DELETE FROM intervention_effectiveness WHERE disease_id = %s "
                                 "AND intervention_type_id = %s", (self.influenza, self.tipos["CUBREBOCAS"]["id"]))

    def test_la_042_trae_los_supuestos_con_su_fuente(self):
        vacuna = {e["enfermedad"]: e for e in datos.efectividad(self.tipos["VACUNACION"]["id"])}
        self.assertEqual(float(vacuna["SARS_COV_2_ANCESTRAL"]["valor"]), 0.95)
        self.assertIn("doi:10.1056/NEJMoa2034577", vacuna["SARS_COV_2_ANCESTRAL"]["fuente"])
        self.assertFalse(vacuna["INFLUENZA_ESTACIONAL"]["supuesto"])
        escuelas = datos.efectividad(self.tipos["CIERRE_ESCUELAS"]["id"])
        self.assertTrue(escuelas[0]["supuesto"] and escuelas[0]["min"] is None)
        total = query("SELECT count(*) AS n FROM intervention_effectiveness", one=True)["n"]
        self.assertEqual(total, 7)

    def test_crear_y_reemplazar_un_supuesto(self):
        tipo = self.tipos["CUBREBOCAS"]["id"]
        contexto = contexto_de_prueba(query("SELECT min(id) AS id FROM users", one=True)["id"])
        valores = {"valor": 0.5, "min": 0.3, "max": 0.7, "fuente": "Prueba", "supuesto": True}
        self.assertTrue(datos.guarda_efectividad(tipo, "eficacia", self.influenza, valores, contexto=contexto))
        self.assertFalse(datos.guarda_efectividad(tipo, "eficacia", self.influenza, dict(valores, valor=0.6),
                                                  contexto=contexto))
        fila = datos.efectividad_de(tipo, "eficacia", self.influenza)
        self.assertEqual((float(fila["valor"]), fila["enfermedad"]), (0.6, "INFLUENZA_ESTACIONAL"))
        general = datos.efectividad_de(tipo, "eficacia", None)
        self.assertEqual(float(general["valor"]), 0.85)
