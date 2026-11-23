import unittest
from unittest.mock import patch

from backend_web.servicios import ErrorServicio
from frontend_web.tests.base import ConUsuarioSimulado
from frontend_web.app.permisos import COOKIE_NAME

# Lo que regresa el servicio pareto (D36): la frontera en personas-día y los pesos aparte (D3).
PARETO = {
    "metrica": "fallecimientos",
    "filas": [
        {"id": 41, "nombre": "SIM-00041 - Escenario A", "costo": 1000.0, "costo_pesos": 15000.0,
         "impacto": 20, "dominado": False, "dias": 120, "poblacion": 500000,
         "engine_version": "seir-ref-0.1", "explicacion": {"texto": "En la frontera."}},
        {"id": 42, "nombre": "SIM-00042 - Escenario B", "costo": 1500.0, "costo_pesos": None,
         "impacto": 12, "dominado": False, "dias": 120, "poblacion": 500000,
         "engine_version": "seir-ref-0.1", "explicacion": {"texto": "En la frontera."}},
    ],
    "frontera": [41, 42],
    "trazabilidad_costos": [{"tipo": "VACUNACION", "valor": 0.5, "unidad": "personas_dia_por_dosis",
                             "fuente": None, "estado": "supuesto"}],
    "modelo_costo": "personas-dia",
    "avisos": [],
}


def corridas():
    return [{"id": i, "scenario_id": i - 40, "version_number": 1, "scenario_name": "Escenario",
             "fallecimientos": 1, "pico_casos_activos": 1, "dia_pico": 1, "tasa_ataque": 0.1,
             "serie": []} for i in (41, 42)]


@patch("backend_web.servicios.corridas", return_value=[])
@patch("backend_web.servicios.comparacion", side_effect=lambda token, ids: corridas())
class ComparacionParetoTests(ConUsuarioSimulado):
    def _get(self):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            return client.get("/comparacion?run_id=41&run_id=42")

    def test_muestra_grafica_pareto_en_personas_dia_y_pesos_aparte(self, *_):
        with patch("backend_web.servicios.pareto", return_value=PARETO) as mock_pareto:
            resp = self._get()

        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_pareto.call_args.args[1], [41, 42])
        self.assertIn("comparacion-pareto", html)
        self.assertIn("Frontera de Pareto", html)
        self.assertIn("Costo en personas-día vs fallecimientos", html)
        self.assertIn("Costo de intervención (personas-día)", html)
        self.assertIn("Costo en pesos (aparte)", html)
        self.assertIn("$ 15,000.00", html)
        self.assertIn("De dónde sale cada costo", html)
        self.assertIn("La decisión final corresponde al usuario", html)

    def test_muestra_error_si_faltan_costos(self, *_):
        with patch("backend_web.servicios.pareto",
                   side_effect=ErrorServicio("pareto", 422, "DATOS_INVALIDOS",
                                             "Falta el costo unitario de 'VACUNACION'.")):
            resp = self._get()

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"No se pudo calcular", resp.data)
        self.assertIn(b"VACUNACION", resp.data)


if __name__ == "__main__":
    unittest.main()
