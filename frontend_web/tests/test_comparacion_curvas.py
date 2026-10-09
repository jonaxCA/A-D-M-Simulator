import unittest
from unittest.mock import patch

from frontend_web.tests.base import ConUsuarioSimulado
from frontend_web.app.permisos import COOKIE_NAME


class ComparacionCurvasTests(ConUsuarioSimulado):
    @patch("frontend_web.app.routes.simulaciones.construir_comparacion_costo_impacto")
    @patch("frontend_web.app.routes.queries.get_runs_completados_para_comparar")
    @patch("frontend_web.app.routes.queries.get_corridas_para_comparar")
    def test_dos_corridas_generan_graficas(
        self, mock_corridas, mock_lista, mock_pareto
    ):
        mock_pareto.return_value = (None, [])
        mock_lista.return_value = []
        mock_corridas.return_value = [
            {
                "id": 41,
                "scenario_id": 1,
                "version_number": 1,
                "scenario_name": "Escenario A",
                "serie": [
                    {"dia": 0, "casos_activos": 10, "H": 2, "D": 0},
                    {"dia": 1, "casos_activos": 14, "H": 3, "D": 1},
                ],
            },
            {
                "id": 42,
                "scenario_id": 2,
                "version_number": 1,
                "scenario_name": "Escenario B",
                "serie": [
                    {"dia": 0, "casos_activos": 8, "H": 1, "D": 0},
                    {"dia": 1, "casos_activos": 11, "H": 2, "D": 0},
                ],
            },
        ]

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            resp = client.get("/comparacion?run_id=41&run_id=42")

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"comparacion-casos", resp.data)
        self.assertIn(b"comparacion-hospitalizaciones", resp.data)
        self.assertIn(b"comparacion-fallecimientos", resp.data)
        self.assertIn(b"casos_activos", resp.data)

        mock_corridas.assert_called_once_with([41, 42])

    @patch("frontend_web.app.routes.queries.get_runs_completados_para_comparar")
    @patch("frontend_web.app.routes.queries.get_corridas_para_comparar")
    def test_sin_seleccion_no_muestra_graficas(self, mock_corridas, mock_lista):
        mock_lista.return_value = []
        mock_corridas.return_value = []

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            resp = client.get("/comparacion")

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(b"comparacion-casos", resp.data)


if __name__ == "__main__":
    unittest.main()
