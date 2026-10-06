"""
Textos para mostrar (frontend_web/app/presentacion.py).

Ejecutar:
    python -m unittest frontend_web.tests.test_presentacion -v
"""
import unittest
from unittest.mock import patch

from frontend_web.tests.base import AppTestCase, requiere_base
from frontend_web.app.presentacion import monitoreo_insights

TOTALES = {"casos_pct": 15.2}


def _geografica(zonas):
    return monitoreo_insights(zonas, [], TOTALES, 30)["geografica"]


class MonitoreoInsightsTests(unittest.TestCase):
    def test_la_zona_con_mayor_cambio_entre_las_que_tienen_casos(self):
        zonas = [{"zona": "Apodaca", "casos": 5, "variacion": 12.5},
                 {"zona": "Monterrey", "casos": 9, "variacion": 40.0},
                 {"zona": "Juárez", "casos": 0, "variacion": 300.0}]
        self.assertEqual(_geografica(zonas), "El mayor cambio (+40.0%) se registra en "
                                             "Monterrey durante los últimos 7 días.")

    def test_el_signo_del_cambio(self):
        self.assertIn("(-25.0%)", _geografica([{"zona": "García", "casos": 3,
                                                "variacion": -25.0}]))
        self.assertIn("(+0.0%)", _geografica([{"zona": "García", "casos": 3,
                                               "variacion": 0.0}]))

    def test_en_empate_gana_la_primera_zona(self):
        zonas = [{"zona": "Apodaca", "casos": 1, "variacion": 10.0},
                 {"zona": "Escobedo", "casos": 1, "variacion": 10.0}]
        self.assertIn("en Apodaca durante", _geografica(zonas))

    def test_sin_casos_en_ninguna_zona(self):
        self.assertEqual(_geografica([{"zona": "Apodaca", "casos": 0, "variacion": 0.0}]),
                         "Todavía no hay casos capturados en el periodo seleccionado.")

    def test_la_incidencia_general_sube_baja_o_se_mantiene(self):
        casos = [(15.2, 30, "La incidencia general aumentó un 15.2% respecto al periodo "
                            "anterior de 30 días."),
                 (-7.5, 7, "La incidencia general disminuyó un 7.5% respecto al periodo "
                           "anterior de 7 días."),
                 (0.0, 90, "La incidencia general se mantuvo un 0.0% respecto al periodo "
                           "anterior de 90 días.")]
        for pct, dias, esperado in casos:
            with self.subTest(pct=pct):
                self.assertEqual(monitoreo_insights([], [], {"casos_pct": pct}, dias)["global"],
                                 esperado)

    def test_el_grupo_de_edad_con_mas_casos(self):
        edades = [{"grupo": "0-19", "casos": 10}, {"grupo": "20-39", "casos": 1234},
                  {"grupo": "60+", "casos": 0}]
        self.assertEqual(monitoreo_insights([], edades, TOTALES, 30)["critica"],
                         "El grupo con más casos es el de 20-39 años (1,234 casos).")
        self.assertEqual(monitoreo_insights([], [{"grupo": "0-19", "casos": 0}],
                                            TOTALES, 30)["critica"],
                         "Sin casos con edad registrada en el periodo.")


@requiere_base
class MonitoreoMuestraLosTextosTests(AppTestCase):
    @patch("frontend_web.app.routes.presentacion.monitoreo_insights")
    def test_la_pantalla_muestra_lo_que_arma_presentacion(self, mock_insights):
        mock_insights.return_value = {"geografica": "TEXTO-GEO", "global": "TEXTO-GLOBAL",
                                      "critica": "TEXTO-CRITICA"}
        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")
            resp = client.get("/monitoreo?dias=7")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        for texto in ("TEXTO-GEO", "TEXTO-GLOBAL", "TEXTO-CRITICA"):
            self.assertIn(texto, html)
        mock_insights.assert_called_once()
        zonas, edades, totales, dias = mock_insights.call_args.args
        self.assertTrue(zonas)
        self.assertTrue(all({"zona", "casos", "variacion"} <= set(z) for z in zonas))
        self.assertTrue(all({"grupo", "casos"} <= set(e) for e in edades))
        self.assertIn("casos_pct", totales)
        self.assertEqual(dias, 7)


if __name__ == "__main__":
    unittest.main()
