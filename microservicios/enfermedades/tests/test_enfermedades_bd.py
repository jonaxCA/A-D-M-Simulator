import unittest

from epidemia_comun.bd import query
from epidemia_comun.errores import ErrorAPI
from microservicios.enfermedades import datos
from microservicios.pruebas_bd import contexto_de_prueba, escribe, tiene_base

CRITERIOS = [{"clasificacion": "Caso sospechoso", "texto": "Fiebre."}]


# Contra la base de pruebas, con la 042. Trabaja sobre PATOGENO_X, que no trae definición, y la deja así.
@unittest.skipUnless(tiene_base(), "Requiere la base de pruebas")
class EnfermedadesBdTests(unittest.TestCase):
    def setUp(self):
        self.disease_id = query("SELECT id FROM diseases WHERE code = 'PATOGENO_X'", one=True)["id"]
        self.contexto = contexto_de_prueba(query("SELECT min(id) AS id FROM users", one=True)["id"])
        self.addCleanup(escribe, "DELETE FROM case_definitions WHERE disease_id = %s", (self.disease_id,))
        self.addCleanup(escribe, "UPDATE diseases SET transmission = NULL, icd10 = NULL, classification_source = NULL "
                                 "WHERE id = %s", (self.disease_id,))

    def test_la_042_trae_las_definiciones_de_la_dge(self):
        por_codigo = {f["code"]: f for f in query(
            """SELECT d.code, count(*) AS versiones, count(*) FILTER (WHERE c.status = 'vigente') AS vigentes
               FROM case_definitions c JOIN diseases d ON d.id = c.disease_id GROUP BY d.code""")}
        self.assertEqual(set(por_codigo), {"SARS_COV_2_ANCESTRAL", "INFLUENZA_ESTACIONAL", "DENGUE_DEMO",
                                           "MALARIA_DEMO", "ZIKA_DEMO"})
        self.assertTrue(all(f["vigentes"] == 1 for f in por_codigo.values()))
        self.assertEqual(por_codigo["INFLUENZA_ESTACIONAL"]["versiones"], 2)
        influenza = query("SELECT id FROM diseases WHERE code = 'INFLUENZA_ESTACIONAL'", one=True)["id"]
        vigente = datos.definicion(influenza)
        self.assertEqual(vigente["version"], 2)
        self.assertIn("septiembre de 2023", vigente["fuente"])
        self.assertEqual(datos.enfermedad(influenza)["icd10"], "J09-J11")
        self.assertEqual(datos.definiciones(self.disease_id), [])

    def test_borrador_publicacion_y_retiro(self):
        self.assertEqual(datos.crea_borrador(self.disease_id, CRITERIOS, "Fuente 1", None, contexto=self.contexto), 1)
        with self.assertRaises(ErrorAPI):
            datos.crea_borrador(self.disease_id, CRITERIOS, "Otra", None, contexto=self.contexto)
        datos.edita_borrador(self.disease_id, 1, CRITERIOS * 2, "Fuente 1 corregida", None, contexto=self.contexto)
        self.assertIsNone(datos.publica(self.disease_id, 1, contexto=self.contexto))
        datos.crea_borrador(self.disease_id, CRITERIOS, "Fuente 2", "https://x.mx/y.pdf", contexto=self.contexto)
        self.assertEqual(datos.publica(self.disease_id, 2, contexto=self.contexto), 1)
        estados = [(d["version"], d["status"]) for d in datos.definiciones(self.disease_id)]
        self.assertEqual(estados, [(2, "vigente"), (1, "retirada")])
        with self.assertRaises(ErrorAPI) as error:
            datos.edita_borrador(self.disease_id, 1, CRITERIOS, "X", None, contexto=self.contexto)
        self.assertEqual(error.exception.estado, 409)
        self.assertEqual(len(datos.definicion(self.disease_id, 1)["criterios"]), 2)

    def test_clasificar(self):
        datos.clasifica(self.disease_id, {"transmission": "respiratoria", "icd10": "X00",
                                          "classification_source": "Prueba"}, contexto=self.contexto)
        self.assertEqual(datos.enfermedad(self.disease_id)["transmission"], "respiratoria")
        with self.assertRaises(ErrorAPI):
            datos.clasifica(self.disease_id, {"transmission": "aerea"}, contexto=self.contexto)
