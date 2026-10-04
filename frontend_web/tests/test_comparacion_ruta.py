import os
import unittest
from datetime import datetime
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend_web.auth import create_token
from frontend_web.app import create_app
from frontend_web.app.permisos import COOKIE_NAME


class ComparacionRutaTests(unittest.TestCase):
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

    def _token_analista(self):
        return create_token({
            "id": 999,
            "username": "prueba",
            "full_name": "Usuario Prueba",
            "roles": ["ANALISTA"],
        })

    def test_comparacion_requiere_login(self):
        with self.app.test_client() as client:
            resp = client.get("/comparacion", follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/login", resp.headers["Location"])

    @patch("frontend_web.app.routes.queries.get_runs_completados_para_comparar")
    def test_comparacion_muestra_corridas_completadas(self, mock_runs):
        mock_runs.return_value = [{
            "id": 42,
            "scenario_id": 3,
            "scenario_name": "Escenario de prueba",
            "disease_name": "Influenza",
            "region_name": "Monterrey",
            "version_number": 2,
            "finished_at": datetime(2026, 9, 26, 20, 30),
            "seed": 123,
            "casos_acumulados": 100,
            "hospitalizaciones": 10,
            "fallecimientos": 2,
            "pico_casos_activos": 25,
            "dia_pico": 12,
            "tasa_ataque": 0.10,
        }]

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token_analista())
            resp = client.get("/comparacion")

            self.assertEqual(resp.status_code, 200)
            self.assertIn(b'SIM-00042', resp.data)
            self.assertIn(b'name="run_id"', resp.data)
            self.assertIn(b'value="42"', resp.data)
            self.assertIn(
                "Escenario de prueba".encode("utf-8"),
                resp.data,
            )

    @patch("frontend_web.app.routes.queries.get_runs_completados_para_comparar")
    def test_comparacion_vacia_muestra_mensaje(self, mock_runs):
        mock_runs.return_value = []

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token_analista())
            resp = client.get("/comparacion")

            self.assertEqual(resp.status_code, 200)
            self.assertIn(
                "No hay corridas completadas disponibles".encode("utf-8"),
                resp.data,
            )


if __name__ == "__main__":
    unittest.main()
