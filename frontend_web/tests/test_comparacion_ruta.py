import os
import unittest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend_web.auth import create_token
from frontend_web.app import create_app
from frontend_web.app.permisos import COOKIE_NAME
from frontend_web.app.routes import STUB_ITEMS


class ComparacionRutaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True

    def test_comparacion_ya_no_es_stub(self):
        self.assertNotIn("comparacion", STUB_ITEMS)

    def test_comparacion_requiere_login(self):
        with self.app.test_client() as client:
            resp = client.get("/comparacion", follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/login", resp.headers["Location"])

    def test_comparacion_renderiza_para_usuario_autenticado(self):
        token = create_token({
            "id": 999,
            "username": "prueba",
            "full_name": "Usuario Prueba",
            "roles": ["ANALISTA"],
        })

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, token)
            resp = client.get("/comparacion")

            self.assertEqual(resp.status_code, 200)
            self.assertIn(
                "Comparación de escenarios".encode("utf-8"),
                resp.data,
            )


if __name__ == "__main__":
    unittest.main()
