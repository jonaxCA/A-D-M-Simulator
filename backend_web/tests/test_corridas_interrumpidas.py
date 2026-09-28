"""
Corridas que un reinicio del servidor dejo sin hilo (auditoria, bug 6).

Antes se quedaban en 'encolado' o 'ejecutando' para siempre. Ahora
frontend_web/run.py llama a simulaciones.recupera_corridas_interrumpidas()
al arrancar y las cierra como 'fallido' con un mensaje que lo explica.

Las pruebas contra la base acotan el barrido a sus propias corridas
(`run_ids`), para no cerrar corridas ajenas de quien las corre.

Ejecutar:
    python -m unittest backend_web.tests.test_corridas_interrumpidas -v
"""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend_web import queries, simulaciones
from backend_web.db import get_conn, query


def _tiene_base():
    try:
        query("SELECT 1", one=True)
        return True
    except Exception:
        return False


class RecuperaCorridasTests(unittest.TestCase):
    """La orquestacion, sin base: audita cada corrida cerrada."""

    def test_audita_cada_corrida_cerrada_como_fallida(self):
        cerradas = [{"id": 7, "requested_by": 5, "seed": 11},
                    {"id": 8, "requested_by": 5, "seed": 12}]
        with patch.object(queries, "marca_corridas_interrumpidas",
                          return_value=cerradas) as marca, \
                patch.object(simulaciones, "log_audit") as audita:
            self.assertEqual(simulaciones.recupera_corridas_interrumpidas(), 2)
        marca.assert_called_once_with(simulaciones.MENSAJE_INTERRUMPIDA)
        self.assertEqual(audita.call_count, 2)
        for llamada, fila in zip(audita.call_args_list, cerradas):
            args, kwargs = llamada
            self.assertEqual(args[:3], (5, "RUN", "simulation_run"))
            self.assertEqual(kwargs["entity_id"], str(fila["id"]))
            self.assertEqual(kwargs["data_after"]["estado"], "fallido")

    def test_sin_corridas_huerfanas_no_audita_nada(self):
        with patch.object(queries, "marca_corridas_interrumpidas", return_value=[]), \
                patch.object(simulaciones, "log_audit") as audita:
            self.assertEqual(simulaciones.recupera_corridas_interrumpidas(), 0)
        audita.assert_not_called()

    def test_si_la_bitacora_falla_las_demas_se_auditan_igual(self):
        cerradas = [{"id": 1, "requested_by": 5, "seed": 1},
                    {"id": 2, "requested_by": 5, "seed": 2}]
        with patch.object(queries, "marca_corridas_interrumpidas", return_value=cerradas), \
                patch.object(simulaciones, "log_audit",
                             side_effect=[RuntimeError("sin conexion"), None]) as audita, \
                self.assertLogs("backend_web.simulaciones", level="ERROR"):
            self.assertEqual(simulaciones.recupera_corridas_interrumpidas(), 2)
        self.assertEqual(audita.call_count, 2)


@unittest.skipUnless(_tiene_base(), "Requiere PostgreSQL en DATABASE_URL.")
class MarcaCorridasInterrumpidasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        version = query(
            """SELECT sv.id FROM scenario_versions sv
               JOIN scenarios s ON s.id = sv.scenario_id
               WHERE s.name = 'Ola Influenza ZMM - otono 2026' AND sv.status = 'aprobado'""",
            one=True)
        if not version:
            raise unittest.SkipTest("Falta el escenario de demostracion aprobado "
                                    "(datos/postgres/semillas/demo_datos_nl.sql).")
        cls.version_id = version["id"]
        cls.user_id = query("SELECT id FROM users WHERE username = 'alex.cavazos'",
                            one=True)["id"]

    def setUp(self):
        self._lotes = []

    def tearDown(self):
        # simulation_batches -> simulation_runs en cascada.
        for lote in self._lotes:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM simulation_batches WHERE id = %s", (lote,))
                conn.commit()

    def _encola(self, seed):
        run_id, lote, error = queries.crear_corrida(
            self.version_id, seed, self.user_id, simulaciones.ENGINE_VERSION)
        self.assertIsNone(error, error)
        self._lotes.append(lote)
        return run_id

    def _estado(self, run_id):
        return query("SELECT status, error_message, finished_at FROM simulation_runs "
                     "WHERE id = %s", (run_id,), one=True)

    def test_cierra_encoladas_y_ejecutando_con_el_mensaje(self):
        encolada = self._encola(101)
        ejecutando = self._encola(102)
        self.assertTrue(queries.marcar_run_ejecutando(ejecutando))

        filas = queries.marca_corridas_interrumpidas(
            simulaciones.MENSAJE_INTERRUMPIDA, run_ids=[encolada, ejecutando])

        self.assertEqual(sorted(f["id"] for f in filas), sorted([encolada, ejecutando]))
        for run_id in (encolada, ejecutando):
            fila = self._estado(run_id)
            self.assertEqual(fila["status"], "fallido")
            self.assertEqual(fila["error_message"], simulaciones.MENSAJE_INTERRUMPIDA)
            self.assertIsNotNone(fila["finished_at"])

    def test_marcar_run_fallido_funciona_desde_encolado(self):
        """ck_simulation_runs_inicio exige started_at fuera de 'encolado'. Antes
        marcar_run_fallido no lo ponia y cerrar una corrida que nunca arranco
        reventaba con CheckViolation, dejandola encolada para siempre."""
        run_id = self._encola(106)
        self.assertTrue(queries.marcar_run_fallido(run_id, "no llego a arrancar"))
        fila = query("SELECT status, started_at, finished_at FROM simulation_runs "
                     "WHERE id = %s", (run_id,), one=True)
        self.assertEqual(fila["status"], "fallido")
        self.assertEqual(fila["started_at"], fila["finished_at"])

    def test_no_toca_las_que_ya_terminaron(self):
        run_id = self._encola(103)
        self.assertTrue(queries.marcar_run_fallido(run_id, "fallo original"))
        filas = queries.marca_corridas_interrumpidas("otro mensaje", run_ids=[run_id])
        self.assertEqual(filas, [])
        self.assertEqual(self._estado(run_id)["error_message"], "fallo original")

    def test_es_idempotente(self):
        run_id = self._encola(104)
        self.assertEqual(len(queries.marca_corridas_interrumpidas("x", run_ids=[run_id])), 1)
        self.assertEqual(queries.marca_corridas_interrumpidas("x", run_ids=[run_id]), [])

    def test_una_corrida_cerrada_asi_se_puede_reejecutar(self):
        """El mensaje promete que se puede re-ejecutar: la version sigue
        aprobada y crear_corrida acepta la misma semilla."""
        run_id = self._encola(105)
        queries.marca_corridas_interrumpidas("x", run_ids=[run_id])
        nuevo, lote, error = queries.crear_corrida(
            self.version_id, 105, self.user_id, simulaciones.ENGINE_VERSION)
        self.assertIsNone(error, error)
        self._lotes.append(lote)
        self.assertEqual(self._estado(nuevo)["status"], "encolado")


if __name__ == "__main__":
    unittest.main()
