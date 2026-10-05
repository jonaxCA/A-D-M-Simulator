import unittest
from datetime import datetime
from unittest.mock import patch

from frontend_web.tests.base import ConUsuarioSimulado
from frontend_web.app.permisos import COOKIE_NAME


class ComparacionRutaTests(ConUsuarioSimulado):
    def test_comparacion_requiere_login(self):
        with self.app.test_client() as client:
            resp = client.get("/comparacion", follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/login", resp.headers["Location"])

    @patch("frontend_web.app.routes.queries.get_runs_completados_para_comparar")
    def test_comparacion_muestra_corridas_completadas(self, mock_runs):
        mock_runs.return_value = [{
            "id": 42,
            "scenario_id": 3,
            "scenario_name": "Escenario de prueba",
            "disease_name": "Influenza",
            "region_name": "Monterrey",
            "version_number": 2,
            "finished_at": datetime(2026, 9, 26, 20, 30),
            "seed": 123,
            "casos_acumulados": 100,
            "hospitalizaciones": 10,
            "fallecimientos": 2,
            "pico_casos_activos": 25,
            "dia_pico": 12,
            "tasa_ataque": 0.10,
        }]

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            resp = client.get("/comparacion")

            self.assertEqual(resp.status_code, 200)
            self.assertIn(b'SIM-00042', resp.data)
            self.assertIn(b'name="run_id"', resp.data)
            self.assertIn(b'value="42"', resp.data)
            self.assertIn(
                "Escenario de prueba".encode("utf-8"),
                resp.data,
            )

    @patch("frontend_web.app.routes.queries.get_runs_completados_para_comparar")
    def test_comparacion_vacia_muestra_mensaje(self, mock_runs):
        mock_runs.return_value = []

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            resp = client.get("/comparacion")

            self.assertEqual(resp.status_code, 200)
            self.assertIn(
                "No hay corridas completadas disponibles".encode("utf-8"),
                resp.data,
            )


if __name__ == "__main__":
    unittest.main()
