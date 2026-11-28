import unittest
from unittest.mock import patch

from backend_web.servicios import ErrorServicio
from frontend_web.tests.base import ConUsuarioSimulado
from frontend_web.app.permisos import COOKIE_NAME


# Lo que regresa el servicio comparacion (D36): cada corrida con la serie que le pidió a
# resultados (D28); serie None si resultados no la tuvo.
SERIES = {
    41: [{"dia": 0, "casos_activos": 10, "H": 2, "D": 0},
         {"dia": 1, "casos_activos": 14, "H": 3, "D": 1}],
    42: [{"dia": 0, "casos_activos": 8, "H": 1, "D": 0},
         {"dia": 1, "casos_activos": 11, "H": 2, "D": 0}],
}


def corridas(series):
    return [{"id": i, "scenario_id": i - 40, "version_number": 1, "scenario_name": "Escenario %d" % i,
             "serie": serie, "fallecimientos": 1, "pico_casos_activos": 14, "dia_pico": 1,
             "tasa_ataque": 0.1} for i, serie in series.items()]


@patch("backend_web.servicios.pareto", return_value=None)
@patch("backend_web.servicios.corridas", return_value=[])
class ComparacionCurvasTests(ConUsuarioSimulado):
    def _get(self):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            return client.get("/comparacion?run_id=41&run_id=42")

    def test_dos_corridas_generan_graficas(self, *_):
        with patch("backend_web.servicios.comparacion", return_value=corridas(SERIES)) as mock:
            resp = self._get()

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"comparacion-casos", resp.data)
        self.assertIn(b"comparacion-hospitalizaciones", resp.data)
        self.assertIn(b"comparacion-fallecimientos", resp.data)
        self.assertIn(b'"casos_activos": 14', resp.data)
        self.assertNotIn("Sin curvas para".encode(), resp.data)
        self.assertEqual(mock.call_args.args[1], [41, 42])

    def test_sin_resultados_avisa_que_corrida_no_tiene_curvas(self, *_):
        with patch("backend_web.servicios.comparacion",
                   return_value=corridas({41: SERIES[41], 42: None})):
            resp = self._get()

        self.assertEqual(resp.status_code, 200)
        self.assertIn("Sin curvas para SIM-00042".encode(), resp.data)
        self.assertNotIn("SIM-00041:".encode(), resp.data)

    def test_403_de_comparacion_es_permiso_denegado(self, *_):
        with patch("backend_web.servicios.comparacion",
                   side_effect=ErrorServicio("comparacion", 403, "PERMISO_INSUFICIENTE")):
            resp = self._get()

        self.assertEqual(resp.status_code, 403)


class ComparacionSinSeleccionTests(ConUsuarioSimulado):

    @patch("backend_web.servicios.comparacion")
    @patch("backend_web.servicios.corridas", return_value=[])
    def test_sin_seleccion_no_muestra_graficas(self, _lista, mock_comparacion):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            resp = client.get("/comparacion")

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(b"comparacion-casos", resp.data)
        mock_comparacion.assert_not_called()


if __name__ == "__main__":
    unittest.main()
