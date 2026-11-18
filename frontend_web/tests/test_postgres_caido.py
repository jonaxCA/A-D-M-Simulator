import unittest
from unittest.mock import patch

import psycopg2
from psycopg2 import errors

from frontend_web.tests.base import AppTestCase


def con_codigo(clase, pgcode):
    # Como llegan del servidor: la clase de psycopg2 con su SQLSTATE.
    return type("E", (clase,), {"pgcode": pgcode})("x")


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

    def test_conexion_cerrada_o_servidor_apagandose_es_503(self):
        for error in (psycopg2.InterfaceError("connection already closed"),
                      con_codigo(errors.AdminShutdown, "57P01"),
                      con_codigo(errors.CannotConnectNow, "57P03")):
            with self.subTest(error=type(error).__mro__[1].__name__):
                with patch("backend_web.queries.get_resumen_indicadores", side_effect=error):
                    self.assertEqual(self.app.test_client().get("/").status_code, 503)

    def test_otros_errores_de_la_base_no_se_disfrazan_de_503(self):
        # Igual que en los servicios (fabrica.py): una consulta cancelada o un deadlock no es
        # una base caída. Con app.testing el error se propaga en lugar de dar 500.
        for clase, pgcode in ((errors.QueryCanceled, "57014"), (errors.DeadlockDetected, "40P01")):
            with self.subTest(pgcode=pgcode):
                with patch("backend_web.queries.get_resumen_indicadores",
                           side_effect=con_codigo(clase, pgcode)):
                    with self.assertRaises(clase):
                        self.app.test_client().get("/")


if __name__ == "__main__":
    unittest.main()
