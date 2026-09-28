import os
import unittest
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend_web.auth import create_token
from frontend_web.app import create_app
from frontend_web.app.permisos import COOKIE_NAME


class ComparacionParetoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True

    def setUp(self):
        # El token es de un usuario inventado (id 999) y las consultas estan
        # simuladas, asi que la revalidacion contra `users` tambien: devuelve
        # el usuario del token tal cual, con `sub` como entero, igual que
        # backend_web.auth.usuario_vigente con una cuenta activa.
        simulado = patch("frontend_web.app.permisos.usuario_vigente",
                         side_effect=lambda u: {**u, "sub": int(u["sub"])})
        simulado.start()
        self.addCleanup(simulado.stop)

    def _token(self):
        return create_token({
            "id": 999,
            "username": "prueba",
            "full_name": "Usuario Prueba",
            "roles": ["ANALISTA"],
        })

    def _corridas(self):
        return [
            {
                "id": 41,
                "scenario_id": 1,
                "version_number": 1,
                "scenario_name": "Escenario A",
                "fallecimientos": 20,
                "pico_casos_activos": 150,
                "dia_pico": 15,
                "tasa_ataque": 0.20,
                "serie": [],
            },
            {
                "id": 42,
                "scenario_id": 2,
                "version_number": 1,
                "scenario_name": "Escenario B",
                "fallecimientos": 12,
                "pico_casos_activos": 100,
                "dia_pico": 18,
                "tasa_ataque": 0.15,
                "serie": [],
            },
        ]

    @patch("frontend_web.app.routes.simulaciones.construir_comparacion_costo_impacto")
    @patch("frontend_web.app.routes.queries.get_runs_completados_para_comparar")
    @patch("frontend_web.app.routes.queries.get_corridas_para_comparar")
    def test_muestra_grafica_pareto(
        self, mock_corridas, mock_runs, mock_pareto
    ):
        mock_runs.return_value = []
        mock_corridas.return_value = self._corridas()
        mock_pareto.return_value = ({
            "metrica": "fallecimientos",
            "filas": [
                {
                    "id": 41,
                    "nombre": "SIM-00041 - Escenario A",
                    "costo": 1000.0,
                    "impacto": 20,
                    "dominado": False,
                },
                {
                    "id": 42,
                    "nombre": "SIM-00042 - Escenario B",
                    "costo": 1500.0,
                    "impacto": 12,
                    "dominado": False,
                },
            ],
            "frontera": [41, 42],
            "avisos": [],
        }, [])

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            resp = client.get("/comparacion?run_id=41&run_id=42")

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"comparacion-pareto", resp.data)
        self.assertIn(b"Frontera de Pareto", resp.data)
        self.assertIn(b"Costo total vs fallecimientos", resp.data)
        self.assertIn(
            "La decisión final corresponde al usuario".encode("utf-8"),
            resp.data,
        )

    @patch("frontend_web.app.routes.simulaciones.construir_comparacion_costo_impacto")
    @patch("frontend_web.app.routes.queries.get_runs_completados_para_comparar")
    @patch("frontend_web.app.routes.queries.get_corridas_para_comparar")
    def test_muestra_error_si_faltan_costos(
        self, mock_corridas, mock_runs, mock_pareto
    ):
        mock_runs.return_value = []
        mock_corridas.return_value = self._corridas()
        mock_pareto.return_value = (
            None,
            ["Falta el costo unitario de 'VACUNACION'."],
        )

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            resp = client.get("/comparacion?run_id=41&run_id=42")

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"No se pudo calcular", resp.data)
        self.assertIn(b"VACUNACION", resp.data)


if __name__ == "__main__":
    unittest.main()
