import unittest
from unittest.mock import patch

from frontend_web.tests.base import ConUsuarioSimulado
from frontend_web.app.permisos import COOKIE_NAME


CORRIDAS = [
    {"id": 41, "scenario_id": 1, "version_number": 1, "scenario_name": "Escenario A"},
    {"id": 42, "scenario_id": 2, "version_number": 1, "scenario_name": "Escenario B"},
]
# La serie de cada corrida la da el servicio resultados (D28), no la base.
SERIES = {
    41: [{"dia": 0, "casos_activos": 10, "H": 2, "D": 0},
         {"dia": 1, "casos_activos": 14, "H": 3, "D": 1}],
    42: [{"dia": 0, "casos_activos": 8, "H": 1, "D": 0},
         {"dia": 1, "casos_activos": 11, "H": 2, "D": 0}],
}


@patch("frontend_web.app.routes.simulaciones.construir_comparacion_costo_impacto",
       return_value=(None, []))
@patch("frontend_web.app.routes.queries.get_runs_completados_para_comparar", return_value=[])
@patch("frontend_web.app.routes.queries.get_corridas_para_comparar",
       side_effect=lambda ids: [dict(c) for c in CORRIDAS])
class ComparacionCurvasTests(ConUsuarioSimulado):
    def _get(self):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            return client.get("/comparacion?run_id=41&run_id=42")

    @patch("frontend_web.app.routes.resultados.curvas_de_corrida",
           side_effect=lambda token, run_id, correlacion: SERIES[run_id])
    def test_dos_corridas_generan_graficas(self, mock_curvas, mock_corridas, *_):
        resp = self._get()

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"comparacion-casos", resp.data)
        self.assertIn(b"comparacion-hospitalizaciones", resp.data)
        self.assertIn(b"comparacion-fallecimientos", resp.data)
        self.assertIn(b'"casos_activos": 14', resp.data)
        self.assertNotIn("Sin curvas para".encode(), resp.data)

        mock_corridas.assert_called_once_with([41, 42])
        self.assertEqual([c.args[1] for c in mock_curvas.call_args_list], [41, 42])

    @patch("frontend_web.app.routes.resultados.curvas_de_corrida",
           side_effect=lambda token, run_id, correlacion: SERIES[41] if run_id == 41 else None)
    def test_sin_resultados_avisa_que_corrida_no_tiene_curvas(self, *_):
        resp = self._get()

        self.assertEqual(resp.status_code, 200)
        self.assertIn("Sin curvas para SIM-00042".encode(), resp.data)
        self.assertNotIn("SIM-00041:".encode(), resp.data)

    @patch("frontend_web.app.routes.log_audit")
    @patch("frontend_web.app.routes.resultados.curvas_de_corrida")
    def test_403_de_resultados_es_permiso_denegado(self, mock_curvas, mock_audit, *_):
        from backend_web.resultados import SinAcceso
        mock_curvas.side_effect = SinAcceso(403)
        resp = self._get()

        self.assertEqual(resp.status_code, 302)
        self.assertIn("denegado=1", resp.headers["Location"])
        self.assertEqual(mock_audit.call_args.args[1], "PERMISSION_DENIED")


class ComparacionSinSeleccionTests(ConUsuarioSimulado):

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
