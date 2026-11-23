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

    def test_rechaza_importes_no_finitos(self):
        """float() acepta "nan" e "inf", y la columna numeric los guardaria."""
        for texto in ("nan", "inf", "-inf", "1e400"):
            with self.subTest(texto=texto):
                datos, errores = queries.valida_costo_intervencion(texto, "fuente", False)
                self.assertIsNone(datos)
                self.assertEqual(errores, ["El importe debe ser numerico."])

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

    # La pantalla pide el catálogo a tipos-intervencion y guarda por intervenciones, que valida y
    # audita (D36): aquí se simulan esas dos llamadas.

    @patch("backend_web.servicios.tipos_intervencion")
    def test_epidemiologo_puede_ver_pantalla(self, mock_tipos):
        mock_tipos.return_value = [dict(self._tipo(), cost_unit="por_dosis")]

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token("EPIDEMIOLOGO"))
            resp = client.get("/comparacion/costos")

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Costos de intervenciones", resp.data)
        self.assertIn(b"VACUNACION", resp.data)
        self.assertIn("Personas-día por dosis".encode("utf-8"), resp.data)

    @patch("frontend_web.app.permisos._audita_negado")
    def test_analista_no_puede_editar_costos(self, mock_audit):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token("ANALISTA"))
            resp = client.get("/comparacion/costos", follow_redirects=False)

        self.assertEqual(resp.status_code, 403)
        mock_audit.assert_called_once_with("catalogs.update", "intervention_types")

    @patch("backend_web.servicios.fija_costo_tipo")
    @patch("backend_web.servicios.tipos_intervencion")
    def test_admin_puede_guardar_costo(self, mock_tipos, mock_fija):
        mock_tipos.return_value = [self._tipo()]

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token("ADMINISTRADOR"))
            resp = client.post(
                "/comparacion/costos",
                data={"intervention_type_id": "7", "unit_cost": "90.25",
                      "cost_source": "Referencia de prueba"},
                follow_redirects=False,
            )

        self.assertEqual(resp.status_code, 302)
        token, tipo, valor, fuente, supuesto = mock_fija.call_args[0]
        self.assertEqual((tipo, valor, fuente, supuesto), (7, "90.25", "Referencia de prueba", False))

    @patch("backend_web.servicios.fija_personas_dia_tipo")
    @patch("backend_web.servicios.tipos_intervencion")
    def test_epidemiologo_fija_personas_dia_por_dosis(self, mock_tipos, mock_fija):
        mock_tipos.return_value = [dict(self._tipo(), cost_unit="por_dosis")]
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token("EPIDEMIOLOGO"))
            resp = client.post("/comparacion/costos", data={
                "campo": "personas_dia", "intervention_type_id": "7",
                "person_days_per_unit": "0.5", "person_days_is_assumption": "1"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(mock_fija.call_args[0][1:], (7, "0.5", None, True))

    @patch("backend_web.servicios.fija_costo_tipo")
    @patch("backend_web.servicios.tipos_intervencion")
    def test_el_rechazo_de_intervenciones_se_muestra_y_no_se_guarda(self, mock_tipos, mock_fija):
        from backend_web.servicios import ErrorServicio
        mock_tipos.return_value = [self._tipo()]
        mock_fija.side_effect = ErrorServicio("intervenciones", 422, "DATOS_INVALIDOS",
                                              "El importe no puede ser negativo.")
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token("ADMINISTRADOR"))
            resp = client.post("/comparacion/costos", data={
                "intervention_type_id": "7", "unit_cost": "-1", "cost_source": "x"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("El importe no puede ser negativo.".encode("utf-8"), resp.data)


if __name__ == "__main__":
    unittest.main()
