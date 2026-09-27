import os
import unittest
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend_web.auth import create_token
from frontend_web.app import create_app
from frontend_web.app.permisos import COOKIE_NAME


class ComparacionTablaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True

    def _token(self):
        return create_token({
            "id": 999,
            "username": "prueba",
            "full_name": "Usuario Prueba",
            "roles": ["ANALISTA"],
        })

    @patch("frontend_web.app.routes.queries.get_runs_completados_para_comparar")
    @patch("frontend_web.app.routes.queries.get_corridas_para_comparar")
    def test_tabla_muestra_indicadores_comparativos(self, mock_corridas, mock_lista):
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
