import unittest
from unittest.mock import patch

from frontend_web.tests.base import ConUsuarioSimulado
from frontend_web.app.permisos import COOKIE_NAME


class ComparacionTablaTests(ConUsuarioSimulado):
    @patch("frontend_web.app.routes.simulaciones.construir_comparacion_costo_impacto")
    @patch("frontend_web.app.routes.queries.get_runs_completados_para_comparar")
    @patch("frontend_web.app.routes.queries.get_corridas_para_comparar")
    def test_tabla_muestra_indicadores_comparativos(
        self, mock_corridas, mock_lista, mock_pareto
    ):
        mock_pareto.return_value = (None, [])
        mock_lista.return_value = []
        mock_corridas.return_value = [{
            "id": 42,
            "scenario_id": 3,
            "version_number": 2,
            "scenario_name": "Escenario prueba",
            "serie": [],
            "fallecimientos": 7,
            "pico_casos_activos": 145,
            "dia_pico": 18,
            "tasa_ataque": 0.125,
        }]

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            resp = client.get("/comparacion?run_id=41&run_id=42")

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"SIM-00042", resp.data)
        self.assertIn(b"Fallecimientos", resp.data)
        self.assertIn(b"Pico de casos activos", resp.data)
        self.assertIn(b"D\xc3\xada del pico", resp.data)
        self.assertIn(b"Tasa de ataque", resp.data)
        self.assertIn(b"145", resp.data)
        self.assertIn(b"12.50%", resp.data)


if __name__ == "__main__":
    unittest.main()
