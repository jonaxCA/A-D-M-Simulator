"""
Pruebas de integracion de rutas HTTP (Flask test client) contra PostgreSQL
real, del Bloque F (simulaciones). Mismo requisito de base que
backend_web/tests/test_regiones_rutas.py: necesita el escenario de
demostracion cargado (datos/postgres/semillas/demo_datos_nl.sql).

Todas las corridas que crean estos tests usan demora_seg=0 via el parametro
`?demora=0` -- NO, la ruta no expone ese parametro a proposito (no es del
usuario decidir la demora de otra persona), asi que estas pruebas esperan
la corrida real con su pequena pausa. Por eso hacen polling corto en vez de
asumir que ya termino en la primera consulta.

Ejecutar:
    DATABASE_URL=postgresql://epidemia_app:epidemia_app_pw@localhost:5432/simulador_epidemico \
    JWT_SECRET_KEY=test-secret \
        python -m unittest frontend_web.tests.test_simulaciones_rutas -v
"""
import os
import time
import unittest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend_web.db import get_conn, query
from frontend_web.app import create_app


def _tiene_base():
    try:
        query("SELECT 1", one=True)
        return True
    except Exception:
        return False


@unittest.skipUnless(_tiene_base(), "Requiere PostgreSQL en DATABASE_URL.")
class SimulacionesRutasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True
        fila = query(
            """
            SELECT sv.id FROM scenario_versions sv
            JOIN scenarios s ON s.id = sv.scenario_id
            WHERE s.name = 'Ola Influenza ZMM - otono 2026' AND sv.status = 'aprobado'
            """,
            one=True,
        )
        if not fila:
            raise unittest.SkipTest("Falta el escenario de demostracion aprobado.")
        cls.version_id = fila["id"]

    def setUp(self):
        self._batches_creados = []

    def tearDown(self):
        for batch_id in self._batches_creados:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM simulation_batches WHERE id = %s", (batch_id,))
                conn.commit()

    def _login(self, client, usuario, password):
        resp = client.post("/login", data={"usuario": usuario, "password": password},
                            follow_redirects=False)
        self.assertEqual(resp.status_code, 302, f"login de {usuario} fallo: {resp.data}")

    def _run_id_del_redirect(self, resp):
        loc = resp.headers["Location"]
        return int(loc.rstrip("/").split("/")[-1])

    def _batch_del_run(self, run_id):
        fila = query("SELECT batch_id FROM simulation_runs WHERE id = %s", (run_id,), one=True)
        return fila["batch_id"]

    def _espera_terminal(self, client, run_id, intentos=40):
        for _ in range(intentos):
            datos = client.get(f"/simulaciones/corridas/{run_id}/estado").get_json()
            if datos["terminal"]:
                return datos
            time.sleep(0.25)
        self.fail(f"La corrida {run_id} no termino a tiempo para la prueba.")

    def test_lista_muestra_boton_ejecutar_solo_para_quien_puede(self):
        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")  # ANALISTA
            resp = client.get("/simulaciones")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Ejecutar simulación".encode("utf-8"), resp.data)

        with self.app.test_client() as client:
            self._login(client, "diana.flores", "Epidemia2026!")  # EPIDEMIOLOGO
            resp = client.get("/simulaciones")
            self.assertEqual(resp.status_code, 200)
            self.assertNotIn("Ejecutar simulación".encode("utf-8"), resp.data)

    def test_epidemiologo_no_puede_ejecutar_ni_por_post_directo(self):
        with self.app.test_client() as client:
            self._login(client, "diana.flores", "Epidemia2026!")
            resp = client.post(f"/simulaciones/{self.version_id}/ejecutar",
                               data={"seed": "1"}, follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/dashboard", resp.headers["Location"])

            evento = query(
                """SELECT action FROM audit_log
                   WHERE entity_type = 'simulations' AND action = 'PERMISSION_DENIED'
                   ORDER BY occurred_at DESC LIMIT 1""",
                one=True,
            )
            self.assertIsNotNone(evento, "el intento denegado debe quedar en audit_log")

    def test_analista_ejecuta_y_llega_a_completado(self):
        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")
            resp = client.post(f"/simulaciones/{self.version_id}/ejecutar",
                               data={"seed": "424242"}, follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            run_id = self._run_id_del_redirect(resp)
            self._batches_creados.append(self._batch_del_run(run_id))

            datos = self._espera_terminal(client, run_id)
            self.assertEqual(datos["status"], "completado")

            detalle = client.get(f"/simulaciones/corridas/{run_id}")
            self.assertEqual(detalle.status_code, 200)
            self.assertIn(b"CASOS ACUMULADOS", detalle.data)
            self.assertIn(f"SIM-{run_id:05d}".encode(), detalle.data)

    def test_forzar_error_solo_tiene_efecto_para_administrador(self):
        with self.app.test_client() as client:
            self._login(client, "admin", "Admin2026!")
            resp = client.post(f"/simulaciones/{self.version_id}/ejecutar",
                               data={"seed": "1", "forzar_error": "1"}, follow_redirects=False)
            run_id = self._run_id_del_redirect(resp)
            self._batches_creados.append(self._batch_del_run(run_id))
            datos = self._espera_terminal(client, run_id)
            self.assertEqual(datos["status"], "fallido")
            self.assertIn("Error forzado de prueba", datos["error_message"])

        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")
            resp = client.post(f"/simulaciones/{self.version_id}/ejecutar",
                               data={"seed": "2", "forzar_error": "1"}, follow_redirects=False)
            run_id = self._run_id_del_redirect(resp)
            self._batches_creados.append(self._batch_del_run(run_id))
            datos = self._espera_terminal(client, run_id)
            # ANALISTA no es ADMINISTRADOR: la casilla se ignora y la
            # corrida completa con normalidad.
            self.assertEqual(datos["status"], "completado")

    def test_reejecutar_usa_la_misma_semilla_y_marca_reproducibilidad(self):
        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")
            resp = client.post(f"/simulaciones/{self.version_id}/ejecutar",
                               data={"seed": "909090"}, follow_redirects=False)
            run_id_1 = self._run_id_del_redirect(resp)
            self._batches_creados.append(self._batch_del_run(run_id_1))
            self._espera_terminal(client, run_id_1)

            resp = client.post(f"/simulaciones/corridas/{run_id_1}/reejecutar",
                               follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            run_id_2 = self._run_id_del_redirect(resp)
            self._batches_creados.append(self._batch_del_run(run_id_2))
            self._espera_terminal(client, run_id_2)

            self.assertNotEqual(run_id_1, run_id_2)
            seeds = query(
                "SELECT DISTINCT seed FROM simulation_runs WHERE id IN (%s, %s)",
                (run_id_1, run_id_2),
            )
            self.assertEqual(len(seeds), 1, "las dos corridas deben tener la misma semilla")

            detalle = client.get(f"/simulaciones/corridas/{run_id_2}")
            self.assertIn(f"Coincide con SIM-{run_id_1:05d}".encode("utf-8"), detalle.data)


if __name__ == "__main__":
    unittest.main()
