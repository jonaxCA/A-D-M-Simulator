"""
Corridas que un reinicio del servidor dejo sin hilo (auditoria, bug 6).

Antes se quedaban en 'encolado' o 'ejecutando' para siempre. Ahora
frontend_web/run.py llama a simulaciones.recupera_corridas_interrumpidas()
al arrancar y las cierra como 'fallido' con un mensaje que lo explica.

De paso cubre dos cosas del mismo ciclo de vida que la auditoria destapo:
el lote de cada corrida ahora sigue su estado (antes se quedaba 'encolado'
para siempre) y guardar_resultado_run ya no revive como completada una
corrida que otro proceso cerro.

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


def _lote_de(run_id):
    return query("""SELECT b.status, b.finished_at FROM simulation_batches b
                    JOIN simulation_runs r ON r.batch_id = b.id
                    WHERE r.id = %s""", (run_id,), one=True)


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
class _CorridasDePrueba(unittest.TestCase):
    """Corridas propias sobre la version aprobada de la demo; se borran al
    terminar (el lote arrastra a sus corridas y resultados en cascada)."""

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


class MarcaCorridasInterrumpidasTests(_CorridasDePrueba):
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

    def test_tambien_cierra_el_lote(self):
        run_id = self._encola(107)
        queries.marca_corridas_interrumpidas("x", run_ids=[run_id])
        lote = _lote_de(run_id)
        self.assertEqual(lote["status"], "fallido")
        self.assertIsNotNone(lote["finished_at"])

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


class LoteSigueASuCorridaTests(_CorridasDePrueba):
    """Antes el lote nacia 'encolado' y ahi se quedaba: una corrida completada
    dejaba su lote encolado para siempre y sin finished_at."""

    def test_recorre_el_ciclo_completo_junto_con_su_corrida(self):
        run_id = self._encola(201)
        self.assertEqual(_lote_de(run_id)["status"], "encolado")

        simulaciones.ejecutar_run(run_id, demora_seg=0)

        self.assertEqual(self._estado(run_id)["status"], "completado")
        lote = _lote_de(run_id)
        self.assertEqual(lote["status"], "completado")
        self.assertIsNotNone(lote["finished_at"])

    def test_ejecutando(self):
        run_id = self._encola(202)
        self.assertTrue(queries.marcar_run_ejecutando(run_id))
        lote = _lote_de(run_id)
        self.assertEqual(lote["status"], "ejecutando")
        self.assertIsNone(lote["finished_at"])

    def test_fallido(self):
        run_id = self._encola(203)
        self.assertTrue(queries.marcar_run_ejecutando(run_id))
        self.assertTrue(queries.marcar_run_fallido(run_id, "fallo de prueba"))
        lote = _lote_de(run_id)
        self.assertEqual(lote["status"], "fallido")
        self.assertIsNotNone(lote["finished_at"])

    def test_si_la_transicion_no_ocurre_el_lote_no_se_toca(self):
        run_id = self._encola(204)
        self.assertTrue(queries.marcar_run_fallido(run_id, "cerrada"))
        antes = _lote_de(run_id)
        self.assertFalse(queries.marcar_run_ejecutando(run_id))
        self.assertEqual(_lote_de(run_id), antes)


class GuardadoBlindadoTests(_CorridasDePrueba):
    """guardar_resultado_run ya no "revive" como completada una corrida que
    otro proceso cerro mientras el motor trabajaba."""

    def _resultado(self, seed):
        escenario, _, errores = simulaciones.construir_escenario_desde_version(
            self.version_id)
        self.assertEqual(errores, [])
        return simulaciones.simular(escenario, seed)

    def _resultados_guardados(self, run_id):
        return query("SELECT count(*) AS n FROM simulation_results WHERE run_id = %s",
                     (run_id,), one=True)["n"]

    def test_no_guarda_sobre_una_corrida_que_ya_no_esta_ejecutando(self):
        run_id = self._encola(301)
        self.assertTrue(queries.marcar_run_ejecutando(run_id))
        queries.marca_corridas_interrumpidas("cerrada por otro proceso", run_ids=[run_id])

        guardo = queries.guardar_resultado_run(run_id, self._resultado(301))

        self.assertFalse(guardo)
        fila = self._estado(run_id)
        self.assertEqual(fila["status"], "fallido")
        self.assertEqual(fila["error_message"], "cerrada por otro proceso")
        self.assertEqual(self._resultados_guardados(run_id), 0)
        self.assertEqual(_lote_de(run_id)["status"], "fallido")

    def test_tampoco_sobre_una_encolada(self):
        run_id = self._encola(302)
        self.assertFalse(queries.guardar_resultado_run(run_id, self._resultado(302)))
        self.assertEqual(self._estado(run_id)["status"], "encolado")
        self.assertEqual(self._resultados_guardados(run_id), 0)

    def test_el_camino_normal_sigue_guardando(self):
        run_id = self._encola(303)
        self.assertTrue(queries.marcar_run_ejecutando(run_id))
        self.assertTrue(queries.guardar_resultado_run(run_id, self._resultado(303)))
        self.assertEqual(self._estado(run_id)["status"], "completado")
        self.assertEqual(self._resultados_guardados(run_id), 1)

    def test_ejecutar_run_no_audita_un_completado_que_no_ocurrio(self):
        """De punta a punta: el motor termina, pero mientras corria alguien
        cerro la corrida. No debe quedar un 'completado' en la bitacora."""
        run_id = self._encola(304)
        simular_real = simulaciones.simular

        def simular_y_que_la_cierren(escenario, semilla):
            resultado = simular_real(escenario, semilla)
            queries.marca_corridas_interrumpidas("cerrada a media corrida",
                                                 run_ids=[run_id])
            return resultado

        with patch.object(simulaciones, "simular", side_effect=simular_y_que_la_cierren), \
                self.assertLogs("backend_web.simulaciones", level="WARNING"):
            simulaciones.ejecutar_run(run_id, demora_seg=0)

        self.assertEqual(self._estado(run_id)["status"], "fallido")
        completados = query(
            """SELECT count(*) AS n FROM audit_log
               WHERE entity_type = 'simulation_run' AND entity_id = %s
                 AND data_after->>'estado' = 'completado'""",
            (str(run_id),), one=True)["n"]
        self.assertEqual(completados, 0)


if __name__ == "__main__":
    unittest.main()
