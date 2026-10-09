"""
Candados por rol de las rutas (issue #21).
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

    def test_cada_candado_registra_el_modulo_de_su_pantalla(self):
        """El modulo del PERMISSION_DENIED es lo que permite rastrear intentos
        en la bitacora. Incluye los dos valores por omision, que no son el
        mismo: "users" en admin_required y "diseases" en roles_required."""
        enfermedad = query("SELECT min(id) AS v FROM diseases", one=True)["v"]
        municipio = query("SELECT min(id) AS v FROM regions WHERE level = 'municipio'",
                          one=True)["v"]
        casos = [
            ("/usuarios", "users"),                          # admin_required
            ("/auditoria", "users"),                         # admin_required
            (f"/enfermedades/{enfermedad}/editar", "diseases"),  # roles_required
            (f"/regiones/{municipio}/editar", "regions"),
            ("/escenarios", "scenarios"),
            ("/revisiones", "scenario_versions"),
            ("/simulaciones", "simulations"),
            ("/comparacion/costos", "intervention_types"),
        ]
        capturista = capturista_de_prueba()
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, token_de(CAPTURISTA_PRUEBA))
            for ruta, modulo in casos:
                with self.subTest(ruta=ruta):
                    resp = client.get(ruta, follow_redirects=False)
                    self.assertEqual(resp.status_code, 302)
                    self.assertIn("/dashboard", resp.headers["Location"])
                    fila = query(
                        """SELECT entity_type FROM audit_log
                           WHERE action = 'PERMISSION_DENIED' AND entity_id = %s
                             AND user_id = %s
                           ORDER BY id DESC LIMIT 1""",
                        (ruta, capturista), one=True)
                    self.assertEqual(fila["entity_type"], modulo)


if __name__ == "__main__":
    unittest.main()
