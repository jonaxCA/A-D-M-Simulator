"""
Lo que agregan a la capa de datos los microservicios corridas y simulador:
crear_corrida auditada en la misma transaccion, cancelar_run, y que
ejecutar_run informe su avance y diga como dejo la corrida.

Ejecutar:
    python -m unittest backend_web.tests.test_corridas_servicio -v
"""
from backend_web import queries, simulaciones
from backend_web.contexto import Contexto
from backend_web.db import query
from backend_web.tests.base import ConCorridasDePrueba


def _bitacora(run_id, accion):
    return query("""SELECT data_before, data_after, user_id FROM audit_log
                    WHERE entity_type = 'simulation_run' AND entity_id = %s AND action = %s
                    ORDER BY id""", (str(run_id), accion))


class CorridasDelServicioTests(ConCorridasDePrueba):
    def _encola_auditada(self, seed, forzar_error=False):
        run_id, batch_id, error = queries.crear_corrida(
            self.version_id, seed, self.user_id, simulaciones.ENGINE_VERSION,
            contexto=Contexto(self.user_id, "10.0.0.5", "pruebas"), forzar_error=forzar_error)
        self.assertIsNone(error, error)
        self._batches_creados.append(batch_id)
        return run_id

    def _estado(self, run_id):
        return query("SELECT status, started_at, finished_at FROM simulation_runs WHERE id = %s",
                     (run_id,), one=True)

    def test_crear_corrida_con_contexto_audita_el_encolado(self):
        run_id = self._encola_auditada(401, forzar_error=True)
        filas = _bitacora(run_id, "RUN")
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["user_id"], self.user_id)
        self.assertEqual(filas[0]["data_after"]["estado"], "encolado")
        self.assertEqual(filas[0]["data_after"]["engine"], "python-ref")
        self.assertTrue(filas[0]["data_after"]["forzar_error"])

    def test_el_motor_queda_en_el_lote(self):
        por_omision = self._encola_auditada(404)
        run_id, batch_id, error = queries.crear_corrida(
            self.version_id, 405, self.user_id, None, engine="cuda",
            contexto=Contexto(self.user_id, "10.0.0.5", "pruebas"))
        self.assertIsNone(error, error)
        self._batches_creados.append(batch_id)
        self.assertEqual(queries.get_motor_run(por_omision), "python-ref")
        self.assertEqual(queries.get_motor_run(run_id), "cuda")
        self.assertIsNone(queries.get_motor_run(-1))
        recientes = {r["id"]: r["engine"] for r in queries.get_runs_recientes(100)}
        self.assertEqual((recientes[por_omision], recientes[run_id]), ("python-ref", "cuda"))
        self.assertEqual(_bitacora(run_id, "RUN")[0]["data_after"]["engine"], "cuda")

    def test_cancelar_una_encolada(self):
        run_id = self._encola_auditada(402)
        self.assertTrue(queries.cancelar_run(run_id, contexto=Contexto.sin_peticion(self.user_id)))
        fila = self._estado(run_id)
        self.assertEqual(fila["status"], "cancelado")
        self.assertEqual(fila["started_at"], fila["finished_at"])
        lote = query("""SELECT b.status FROM simulation_batches b
                        JOIN simulation_runs r ON r.batch_id = b.id WHERE r.id = %s""",
                     (run_id,), one=True)
        self.assertEqual(lote["status"], "cancelado")
        cancelaciones = _bitacora(run_id, "CANCEL")
        self.assertEqual(len(cancelaciones), 1)
        self.assertEqual(cancelaciones[0]["data_after"], {"estado": "cancelado"})

    def test_no_cancela_una_que_ya_empezo(self):
        run_id = self._encola_auditada(403)
        self.assertTrue(queries.marcar_run_ejecutando(run_id))
        self.assertFalse(queries.cancelar_run(run_id, contexto=Contexto.sin_peticion(self.user_id)))
        self.assertEqual(self._estado(run_id)["status"], "ejecutando")
        self.assertEqual(_bitacora(run_id, "CANCEL"), [])

    def test_una_cancelada_ya_no_se_ejecuta(self):
        run_id = self._encola_auditada(404)
        queries.cancelar_run(run_id, contexto=Contexto.sin_peticion(self.user_id))
        self.assertIsNone(simulaciones.ejecutar_run(run_id, demora_seg=0))
        self.assertEqual(self._estado(run_id)["status"], "cancelado")

    def test_ejecutar_run_informa_su_avance_y_regresa_completado(self):
        run_id = self._encola_auditada(405)
        avance = []
        estado = simulaciones.ejecutar_run(run_id, demora_seg=0, al_avanzar=avance.append)
        self.assertEqual(estado, "completado")
        self.assertEqual(avance, [10, 30, 90, 100])

    def test_ejecutar_run_forzado_regresa_fallido(self):
        run_id = self._encola_auditada(406)
        avance = []
        estado = simulaciones.ejecutar_run(run_id, forzar_error=True, demora_seg=0,
                                           al_avanzar=avance.append)
        self.assertEqual(estado, "fallido")
        self.assertEqual(avance, [10])

    def test_ejecutar_run_regresa_none_si_otro_la_tomo(self):
        run_id = self._encola_auditada(407)
        self.assertTrue(queries.marcar_run_ejecutando(run_id))
        self.assertIsNone(simulaciones.ejecutar_run(run_id, demora_seg=0))
