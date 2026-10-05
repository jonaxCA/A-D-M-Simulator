import unittest
from unittest.mock import patch

from frontend_web.tests.base import ConUsuarioSimulado
from backend_web import queries
from frontend_web.app.permisos import COOKIE_NAME


class ComparacionCostosTests(ConUsuarioSimulado):
    def _tipo(self):
        return {
            "id": 7,
            "code": "VACUNACION",
            "name": "Vacunacion",
            "description": "",
            "target_layer": "todas",
            "primitive": "node_attr",
            "param_schema": {},
            "unit_cost": None,
            "cost_unit": "MXN/dosis",
            "cost_source": None,
            "cost_is_assumption": True,
        }

    def test_valida_costo_valido_con_fuente(self):
        datos, errores = queries.valida_costo_intervencion(
            "125.50",
            "Secretaria de Salud",
            False,
        )

        self.assertEqual(errores, [])
        self.assertEqual(datos["unit_cost"], 125.50)
        self.assertEqual(datos["cost_source"], "Secretaria de Salud")
        self.assertFalse(datos["cost_is_assumption"])

    def test_rechaza_costo_negativo(self):
        _, errores = queries.valida_costo_intervencion(
            "-10",
            "",
            True,
        )

        self.assertIn("El importe no puede ser negativo.", errores)

    def test_exige_fuente_si_no_es_supuesto(self):
        _, errores = queries.valida_costo_intervencion(
            "100",
            "",
            False,
        )

        self.assertIn(
            "Un costo que no es supuesto debe incluir una fuente.",
            errores,
        )

    @patch("frontend_web.app.routes.queries.get_tipos_intervencion")
    def test_epidemiologo_puede_ver_pantalla(self, mock_tipos):
        mock_tipos.return_value = [self._tipo()]

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token("EPIDEMIOLOGO"))
            resp = client.get("/comparacion/costos")

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Costos de intervenciones", resp.data)
        self.assertIn(b"VACUNACION", resp.data)

    @patch("backend_web.audit.log_audit")
    def test_analista_no_puede_editar_costos(self, mock_audit):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token("ANALISTA"))
            resp = client.get("/comparacion/costos", follow_redirects=False)

        self.assertEqual(resp.status_code, 302)
        self.assertIn("/dashboard", resp.headers["Location"])
        mock_audit.assert_called_once()

    @patch("frontend_web.app.routes.log_audit")
    @patch("frontend_web.app.routes.queries.actualiza_costo_intervencion")
    @patch("frontend_web.app.routes.queries.get_tipos_intervencion")
    def test_admin_puede_guardar_costo(
        self,
        mock_tipos,
        mock_actualiza,
        mock_audit,
    ):
        mock_tipos.return_value = [self._tipo()]

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token("ADMINISTRADOR"))
            resp = client.post(
                "/comparacion/costos",
                data={
                    "intervention_type_id": "7",
                    "unit_cost": "90.25",
                    "cost_source": "Referencia de prueba",
                },
                follow_redirects=False,
            )

        self.assertEqual(resp.status_code, 302)

        mock_actualiza.assert_called_once_with(
            7,
            {
                "unit_cost": 90.25,
                "cost_source": "Referencia de prueba",
                "cost_is_assumption": False,
            },
        )

        mock_audit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
