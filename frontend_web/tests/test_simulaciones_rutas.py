"""
Pruebas de integracion de rutas HTTP (Flask test client) contra PostgreSQL
real, de simulaciones. Mismo requisito de base que
backend_web/tests/test_regiones_rutas.py: necesita el escenario de
demostracion cargado (datos/postgres/semillas/demo_datos_nl.sql).

Desde D4 la web solo consulta las corridas: las lanza la app de escritorio por
medio de `corridas` y las ejecuta el simulador. Estas pruebas las crean por ese
mismo camino (RutasConCorridas._corre) y revisan lo que la web muestra.

Ejecutar:
    python -m unittest frontend_web.tests.test_simulaciones_rutas -v
"""
import unittest

from frontend_web.tests.base import CAPTURISTA_PRUEBA, capturista_de_prueba, RutasConCorridas
from backend_web import simulaciones
from backend_web.auth import create_token
from backend_web.db import query
from frontend_web.app.permisos import COOKIE_NAME


class SimulacionesRutasTests(RutasConCorridas):
    def test_capturista_no_ve_simulaciones(self):
        """CAPTURISTA no tiene 'simulations.read' (010): ni la lista, ni el
        detalle de una corrida, ni su estado. Cada intento queda en la bitacora."""
        user_id = capturista_de_prueba()
        run_id = self._encola(1)

        token = create_token({"id": user_id, "username": CAPTURISTA_PRUEBA,
                              "full_name": "Capturista de prueba", "roles": ["CAPTURISTA"]})
        antes = query("""SELECT count(*) AS n FROM audit_log
                         WHERE user_id = %s AND action = 'PERMISSION_DENIED'
                           AND entity_type = 'simulations'""",
                      (user_id,), one=True)["n"]
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, token)
            for ruta in ("/simulaciones", f"/simulaciones/corridas/{run_id}",
                         f"/simulaciones/corridas/{run_id}/estado"):
                resp = client.get(ruta, follow_redirects=False)
                self.assertEqual(resp.status_code, 302, ruta)
                self.assertIn("/dashboard", resp.headers["Location"], ruta)

            menu = client.get("/dashboard")
            self.assertNotIn(b'href="/simulaciones"', menu.data)

        despues = query("""SELECT count(*) AS n FROM audit_log
                           WHERE user_id = %s AND action = 'PERMISSION_DENIED'
                             AND entity_type = 'simulations'""",
                        (user_id,), one=True)["n"]
        self.assertGreaterEqual(despues - antes, 3)

    def test_la_lista_es_de_consulta_para_todos(self):
        """Nadie lanza corridas desde la web (D4), ni quien puede lanzarlas en
        el escritorio."""
        for usuario, clave in (("alex.cavazos", "Epidemia2026!"),    # ANALISTA
                               ("diana.flores", "Epidemia2026!"),    # EPIDEMIOLOGO
                               ("admin", "Admin2026!")):
            with self.app.test_client() as client:
                self._login(client, usuario, clave)
                resp = client.get("/simulaciones")
                self.assertEqual(resp.status_code, 200, usuario)
                html = " ".join(resp.data.decode("utf-8").split())
                self.assertIn(" ".join(simulaciones.AVISO_SIMULACION.split()), html, usuario)
                self.assertIn("se lanzan desde la app de escritorio", html, usuario)
                self.assertNotIn("Ejecutar simulación", html, usuario)
                self.assertNotIn('name="seed"', html, usuario)

    def test_lanzar_y_reejecutar_ya_no_existen(self):
        run_id = self._corre(424241)
        antes = query("SELECT count(*) AS n FROM simulation_runs", one=True)["n"]
        with self.app.test_client() as client:
            self._login(client, "admin", "Admin2026!")
            for ruta in (f"/simulaciones/{self.version_id}/ejecutar",
                         f"/simulaciones/corridas/{run_id}/reejecutar"):
                resp = client.post(ruta, data={"seed": "1"}, follow_redirects=False)
                self.assertEqual(resp.status_code, 404, ruta)
        despues = query("SELECT count(*) AS n FROM simulation_runs", one=True)["n"]
        self.assertEqual(despues, antes, "la web no debe encolar nada")

    def test_detalle_de_una_corrida_completada(self):
        run_id = self._corre(424242)
        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")
            estado = client.get(f"/simulaciones/corridas/{run_id}/estado").get_json()
            self.assertTrue(estado["terminal"])
            self.assertEqual(estado["status"], "completado")

            detalle = client.get(f"/simulaciones/corridas/{run_id}")
            self.assertEqual(detalle.status_code, 200)
            self.assertIn(b"CASOS ACUMULADOS", detalle.data)
            self.assertIn(f"SIM-{run_id:05d}".encode(), detalle.data)
            self.assertIn(simulaciones.AVISO_SIMULACION.encode("utf-8"), detalle.data)
            self.assertIn("Parámetros usados".encode("utf-8"), detalle.data)
            self.assertIn(b"COMPLETADO", detalle.data)
            self.assertNotIn("Re-ejecutar".encode("utf-8"), detalle.data)

    def test_estado_de_una_corrida_fallida(self):
        run_id = self._corre(1, usuario="admin", forzar_error=True)
        with self.app.test_client() as client:
            self._login(client, "diana.flores", "Epidemia2026!")
            estado = client.get(f"/simulaciones/corridas/{run_id}/estado").get_json()
            self.assertEqual(estado["status"], "fallido")
            self.assertIn("Error forzado de prueba", estado["error_message"])

    def test_marca_la_reproducibilidad_de_la_misma_semilla(self):
        run_id_1 = self._corre(909090)
        run_id_2 = self._corre(909090)
        with self.app.test_client() as client:
            self._login(client, "diana.flores", "Epidemia2026!")
            detalle = client.get(f"/simulaciones/corridas/{run_id_2}")
            self.assertIn(f"Coincide con SIM-{run_id_1:05d}".encode("utf-8"), detalle.data)


if __name__ == "__main__":
    unittest.main()
