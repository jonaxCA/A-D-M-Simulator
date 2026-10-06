"""
Las pruebas nunca corren contra la base de la aplicacion
(backend_web/tests/__init__.py).

Ejecutar:
    python -m unittest backend_web.tests.test_base_de_pruebas -v
"""
import unittest

from backend_web import db
from backend_web.tests import BASE_DE_LA_APP, url_de_pruebas
from backend_web.tests.base import requiere_base

APP = "postgresql://epidemia_app:s3cr%40to@localhost:5432/simulador_epidemico?sslmode=prefer"


class UrlDePruebasTests(unittest.TestCase):
    def test_deriva_el_nombre_y_conserva_todo_lo_demas(self):
        self.assertEqual(
            url_de_pruebas(APP),
            "postgresql://epidemia_app:s3cr%40to@localhost:5432/simulador_epidemico_pruebas"
            "?sslmode=prefer")

    def test_respeta_una_url_de_pruebas_explicita(self):
        otra = "postgresql://ci:ci@db-ci:5432/ci_pruebas"
        self.assertEqual(url_de_pruebas(APP, otra), otra)

    def test_se_niega_a_usar_la_base_de_la_aplicacion(self):
        for misma in (APP, "postgresql://otro:otra@LOCALHOST/simulador_epidemico"):
            with self.subTest(url=misma):
                with self.assertRaisesRegex(RuntimeError, "misma base"):
                    url_de_pruebas(APP, misma)

    def test_sin_nombre_de_base_no_adivina(self):
        with self.assertRaisesRegex(RuntimeError, "DATABASE_URL_PRUEBAS"):
            url_de_pruebas("postgresql://u:p@localhost:5432")


class EsteProcesoTests(unittest.TestCase):
    def test_la_conexion_de_este_proceso_no_es_la_de_la_aplicacion(self):
        if not BASE_DE_LA_APP:
            self.skipTest("sin DATABASE_URL no hay base de la aplicacion que proteger")
        self.assertNotEqual(db.DATABASE_URL.rsplit("/", 1)[-1].split("?")[0], BASE_DE_LA_APP)


@requiere_base
class BaseConectadaTests(unittest.TestCase):
    def test_la_base_conectada_no_es_la_de_la_aplicacion(self):
        conectada = db.query("SELECT current_database() AS base", one=True)["base"]
        self.assertNotEqual(conectada, BASE_DE_LA_APP)


if __name__ == "__main__":
    unittest.main()
