"""
Candados por rol de las rutas nuevas del segundo avance (Bloque H, #21).
CAPTURISTA no tiene 'scenarios.read' (010_datos_iniciales.sql): no entra a
escenarios, ni por el menu ni escribiendo la URL.

Ejecutar:
    python -m unittest frontend_web.tests.test_permisos_rutas -v
"""
import unittest

from frontend_web.tests.base import (CAPTURISTA_PRUEBA, AppTestCase, capturista_de_prueba,
                                     requiere_base)
from backend_web.db import query
from backend_web.tests.base import token_de
from frontend_web.app.permisos import COOKIE_NAME


@requiere_base
class PermisosRutasTests(AppTestCase):
    def _token_capturista(self):
        capturista_de_prueba()
        return token_de(CAPTURISTA_PRUEBA)

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
