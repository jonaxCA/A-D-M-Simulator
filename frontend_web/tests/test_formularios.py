"""
Lectura de la peticion (frontend_web/app/formularios.py) y la ruta que reparte
la lista de corridas ya convertida.

Ejecutar:
    python -m unittest frontend_web.tests.test_formularios -v
"""
import unittest
from unittest.mock import patch

from frontend_web.tests.base import ConUsuarioSimulado
from frontend_web.app import formularios
from frontend_web.app.permisos import COOKIE_NAME


class EsperadoTests(unittest.TestCase):
    def test_distingue_ausente_vacio_y_entero(self):
        self.assertEqual(formularios.esperado({}, "e"), (None, False))
        self.assertEqual(formularios.esperado({"e": "basura"}, "e"), (None, False))
        self.assertEqual(formularios.esperado({"e": "  "}, "e"), (None, True))
        self.assertEqual(formularios.esperado({"e": " 42 "}, "e"), (42, True))


class SemillaTests(unittest.TestCase):
    def test_vacia_es_aleatoria_dentro_del_rango(self):
        for vacia in (None, "", "   "):
            seed, error = formularios.semilla(vacia)
            self.assertIsNone(error)
            self.assertTrue(0 <= seed <= formularios.SEED_MAX)

    def test_con_valor_debe_ser_entero_no_negativo(self):
        self.assertEqual(formularios.semilla(" 7 "), (7, None))
        self.assertEqual(formularios.semilla("0"), (0, None))
        self.assertEqual(formularios.semilla("abc"),
                         (None, "La semilla debe ser un número entero."))
        self.assertEqual(formularios.semilla("-1"),
                         (None, "La semilla debe ser un número entero mayor o igual a 0."))


class IdsDeTests(unittest.TestCase):
    def test_enteros_sin_repetir_en_el_orden_de_llegada(self):
        self.assertEqual(formularios.ids_de(["42", "x", "41", "42", "", None, " 7 "]),
                         [42, 41, 7])
        self.assertEqual(formularios.ids_de([]), [])


class ComparacionRecibeEnterosTests(ConUsuarioSimulado):
    @patch("frontend_web.app.routes.simulaciones.construir_comparacion_costo_impacto")
    @patch("frontend_web.app.routes.queries.get_runs_completados_para_comparar")
    @patch("frontend_web.app.routes.queries.get_corridas_para_comparar")
    def test_la_ruta_convierte_una_vez_y_pasa_enteros_a_las_dos(
        self, mock_corridas, mock_runs, mock_pareto
    ):
        mock_corridas.return_value = []
        mock_runs.return_value = []
        mock_pareto.return_value = (None, ["sin costos"])

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            resp = client.get("/comparacion?run_id=42&run_id=x&run_id=41&run_id=42")

        self.assertEqual(resp.status_code, 200)
        mock_corridas.assert_called_once_with([42, 41])
        mock_pareto.assert_called_once_with([42, 41])


if __name__ == "__main__":
    unittest.main()
