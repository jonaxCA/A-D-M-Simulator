"""
Candados por rol de las rutas nuevas del segundo avance (Bloque H, #21).
CAPTURISTA no tiene 'scenarios.read' (010_datos_iniciales.sql): no entra a
escenarios, ni por el menu ni escribiendo la URL.

Ejecutar:
    python -m unittest frontend_web.tests.test_permisos_rutas -v
"""
import os
import secrets
import unittest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend_web.auth import create_token, hash_password
from backend_web.db import get_conn, query
from frontend_web.app import create_app
from frontend_web.app.permisos import COOKIE_NAME

# Mismo usuario que usa test_simulaciones_rutas.py: inactivo y con una
# contrasena al azar; la prueba entra con un token firmado.
CAPTURISTA_PRUEBA = "prueba.capturista"


def _tiene_base():
    try:
        query("SELECT 1", one=True)
        return True
    except Exception:
        return False


@unittest.skipUnless(_tiene_base(), "Requiere PostgreSQL en DATABASE_URL.")
class PermisosRutasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True

    def _token_capturista(self):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO users (username, email, password_hash, full_name, is_active)
                       VALUES (%s, %s, %s, 'Capturista de prueba', FALSE)
                       ON CONFLICT (username) DO NOTHING""",
                    (CAPTURISTA_PRUEBA, f"{CAPTURISTA_PRUEBA}@example.com",
                     hash_password(secrets.token_urlsafe(24))))
                cur.execute(
                    """INSERT INTO user_roles (user_id, role_id)
                       SELECT u.id, r.id FROM users u, roles r
                       WHERE u.username = %s AND r.code = 'CAPTURISTA'
                       ON CONFLICT DO NOTHING""", (CAPTURISTA_PRUEBA,))
            conn.commit()
        user_id = query("SELECT id FROM users WHERE username = %s",
                        (CAPTURISTA_PRUEBA,), one=True)["id"]
        return create_token({"id": user_id, "username": CAPTURISTA_PRUEBA,
                             "full_name": "Capturista de prueba", "roles": ["CAPTURISTA"]})

    def test_capturista_no_entra_a_escenarios(self):
        rutas = ["/escenarios"]
        escenario = query("SELECT id FROM scenarios ORDER BY id LIMIT 1", one=True)
        if escenario:
            rutas.append(f"/escenarios/{escenario['id']}")
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token_capturista())
            for ruta in rutas:
                resp = client.get(ruta, follow_redirects=False)
                self.assertEqual(resp.status_code, 302, ruta)
                self.assertIn("/dashboard", resp.headers["Location"], ruta)
            menu = client.get("/dashboard")
            self.assertNotIn(b'href="/escenarios"', menu.data)

    def test_analista_si_entra_a_escenarios(self):
        with self.app.test_client() as client:
            client.post("/login", data={"usuario": "alex.cavazos",
                                        "password": "Epidemia2026!"})
            resp = client.get("/escenarios")
            self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
