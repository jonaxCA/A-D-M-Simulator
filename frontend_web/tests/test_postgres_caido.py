import unittest
from unittest.mock import patch

import psycopg2

from frontend_web.tests.base import AppTestCase


class PostgresCaido(AppTestCase):
    def test_sin_base_la_web_da_503_amable(self):
        error = psycopg2.OperationalError("connection refused host=db password=secreta")
        with patch("backend_web.queries.get_resumen_indicadores", side_effect=error):
            resp = self.app.test_client().get("/")
        html = resp.data.decode("utf-8")
        self.assertEqual(resp.status_code, 503)
        self.assertIn("no está disponible por ahora", html)
        self.assertNotIn("secreta", html)

    def test_con_cookie_tampoco_es_500(self):
        error = psycopg2.OperationalError("x")
        with patch("backend_web.queries.get_resumen_indicadores", side_effect=error):
            client = self.app.test_client()
            client.set_cookie("access_token", "cualquiera")
            self.assertEqual(client.get("/").status_code, 503)


if __name__ == "__main__":
    unittest.main()
