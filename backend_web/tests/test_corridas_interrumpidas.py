"""
Corridas que un reinicio del servidor dejo sin hilo (auditoria, bug 6).

Antes se quedaban en 'encolado' o 'ejecutando' para siempre. Ahora el
simulador las reencola o las cierra como 'fallido' al arrancar (D38).

De paso cubre dos cosas del mismo ciclo de vida que la auditoria destapo:
el lote de cada corrida ahora sigue su estado (antes se quedaba 'encolado'
para siempre) y guardar_resultado_run ya no revive como completada una
corrida que otro proceso cerro.

Las pruebas contra la base acotan el barrido a sus propias corridas
(`run_ids`), para no cerrar corridas ajenas de quien las corre.

Ejecutar:
    python -m unittest backend_web.tests.test_corridas_interrumpidas -v
"""
import unittest
from unittest.mock import patch

from microservicios.corridas import datos as corridas_datos
from microservicios.simulador import datos as simulador_datos
from microservicios.simulador import ejecucion
from backend_web.tests.base import ConCorridasDePrueba
from backend_web import queries, simulaciones
from backend_web.contexto import Contexto
from backend_web.db import execute, query
from procesamiento import motores


def _lote_de(run_id):
    return query("""SELECT b.status, b.finished_at FROM simulation_batches b
                    JOIN simulation_runs r ON r.batch_id = b.id
                    WHERE r.id = %s""", (run_id,), one=True)


class _CorridasDePrueba(ConCorridasDePrueba):
    """Corridas propias sobre la version aprobada de la demo; se borran al
    terminar (el lote arrastra a sus corridas y resultados en cascada)."""

    def _estado(self, run_id):
        return query("SELECT status, error_message, finished_at FROM simulation_runs "
                     "WHERE id = %s", (run_id,), one=True)


class MarcaCorridasInterrumpidasTests(_CorridasDePrueba):
    def test_cierra_encoladas_y_ejecutando_con_el_mensaje(self):
        encolada = self._encola(101)
        ejecutando = self._encola(102)
        self.assertTrue(simulador_datos.marcar_run_ejecutando(ejecutando))

        filas = simulador_datos.marca_corridas_interrumpidas(
            ejecucion.MENSAJE_INTERRUMPIDA, run_ids=[encolada, ejecutando])

        self.assertEqual(sorted(f["id"] for f in filas), sorted([encolada, ejecutando]))
        for run_id in (encolada, ejecutando):
            fila = self._estado(run_id)
            self.assertEqual(fila["status"], "fallido")
            self.assertEqual(fila["error_message"], ejecucion.MENSAJE_INTERRUMPIDA)
            self.assertIsNotNone(fila["finished_at"])

    def test_con_engine_solo_cierra_las_de_ese_motor(self):
        # Hay un simulador por motor (D2): el del SEIR que arranca no cierra las del ABM.
        seir = self._encola(110)
        abm = self._encola(111, engine="abm-ref")
        for run_id in (seir, abm):
            self.assertTrue(simulador_datos.marcar_run_ejecutando(run_id))

        filas = simulador_datos.marca_corridas_interrumpidas(
            "x", run_ids=[seir, abm], estados=("ejecutando",), engine="seir-ref")

        self.assertEqual([f["id"] for f in filas], [seir])
        self.assertEqual(self._estado(seir)["status"], "fallido")
        self.assertEqual(self._estado(abm)["status"], "ejecutando")

    def test_corridas_encoladas_de_un_motor_en_orden_de_id(self):
        seir_b = self._encola(121)
        seir_a = self._encola(120)
        abm = self._encola(122, engine="abm-ref")
        ejecutando = self._encola(123)
        self.assertTrue(simulador_datos.marcar_run_ejecutando(ejecutando))

        ids = simulador_datos.corridas_encoladas("seir-ref")

        propios = [i for i in ids if i in (seir_a, seir_b, abm, ejecutando)]
        self.assertEqual(propios, sorted([seir_a, seir_b]))

    def test_con_estados_deja_esperando_a_las_encoladas(self):
        encolada = self._encola(108)
        ejecutando = self._encola(109)
        self.assertTrue(simulador_datos.marcar_run_ejecutando(ejecutando))

        filas = simulador_datos.marca_corridas_interrumpidas(
            "x", run_ids=[encolada, ejecutando], estados=("ejecutando",))

        self.assertEqual([f["id"] for f in filas], [ejecutando])
        self.assertEqual(self._estado(encolada)["status"], "encolado")
        self.assertEqual(self._estado(ejecutando)["status"], "fallido")

    def test_marcar_run_fallido_funciona_desde_encolado(self):
        """ck_simulation_runs_inicio exige started_at fuera de 'encolado'. Antes
        marcar_run_fallido no lo ponia y cerrar una corrida que nunca arranco
        reventaba con CheckViolation, dejandola encolada para siempre."""
        run_id = self._encola(106)
        self.assertTrue(simulador_datos.marcar_run_fallido(run_id, "no llego a arrancar"))
        fila = query("SELECT status, started_at, finished_at FROM simulation_runs "
                     "WHERE id = %s", (run_id,), one=True)
        self.assertEqual(fila["status"], "fallido")
        self.assertEqual(fila["started_at"], fila["finished_at"])

    def test_no_toca_las_que_ya_terminaron(self):
        run_id = self._encola(103)
        self.assertTrue(simulador_datos.marcar_run_fallido(run_id, "fallo original"))
        filas = simulador_datos.marca_corridas_interrumpidas("otro mensaje", run_ids=[run_id])
        self.assertEqual(filas, [])
        self.assertEqual(self._estado(run_id)["error_message"], "fallo original")

    def test_es_idempotente(self):
        run_id = self._encola(104)
        self.assertEqual(len(simulador_datos.marca_corridas_interrumpidas("x", run_ids=[run_id])), 1)
        self.assertEqual(simulador_datos.marca_corridas_interrumpidas("x", run_ids=[run_id]), [])

    def test_tambien_cierra_el_lote(self):
        run_id = self._encola(107)
        simulador_datos.marca_corridas_interrumpidas("x", run_ids=[run_id])
        lote = _lote_de(run_id)
        self.assertEqual(lote["status"], "fallido")
        self.assertIsNotNone(lote["finished_at"])

    def test_una_corrida_cerrada_asi_se_puede_reejecutar(self):
        """El mensaje promete que se puede re-ejecutar: la version sigue
        aprobada y crear_corrida acepta la misma semilla."""
        run_id = self._encola(105)
        simulador_datos.marca_corridas_interrumpidas("x", run_ids=[run_id])
        nuevo, lote, error = corridas_datos.crear_corrida(
            self.version_id, 105, self.user_id, simulaciones.ENGINE_VERSION)
        self.assertIsNone(error, error)
        self._batches_creados.append(lote)
        self.assertEqual(self._estado(nuevo)["status"], "encolado")


class LoteSigueASuCorridaTests(_CorridasDePrueba):
    """Antes el lote nacia 'encolado' y ahi se quedaba: una corrida completada
    dejaba su lote encolado para siempre y sin finished_at."""

    def test_recorre_el_ciclo_completo_junto_con_su_corrida(self):
        run_id = self._encola(201)
        self.assertEqual(_lote_de(run_id)["status"], "encolado")

        ejecucion.ejecutar_run(run_id, demora_seg=0)

        self.assertEqual(self._estado(run_id)["status"], "completado")
        lote = _lote_de(run_id)
        self.assertEqual(lote["status"], "completado")
        self.assertIsNotNone(lote["finished_at"])

    def test_ejecutando(self):
        run_id = self._encola(202)
        self.assertTrue(simulador_datos.marcar_run_ejecutando(run_id))
        lote = _lote_de(run_id)
        self.assertEqual(lote["status"], "ejecutando")
        self.assertIsNone(lote["finished_at"])

    def test_fallido(self):
        run_id = self._encola(203)
        self.assertTrue(simulador_datos.marcar_run_ejecutando(run_id))
        self.assertTrue(simulador_datos.marcar_run_fallido(run_id, "fallo de prueba"))
        lote = _lote_de(run_id)
        self.assertEqual(lote["status"], "fallido")
        self.assertIsNotNone(lote["finished_at"])

    def test_si_la_transicion_no_ocurre_el_lote_no_se_toca(self):
        run_id = self._encola(204)
        self.assertTrue(simulador_datos.marcar_run_fallido(run_id, "cerrada"))
        antes = _lote_de(run_id)
        self.assertFalse(simulador_datos.marcar_run_ejecutando(run_id))
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
        return query("SELECT count(*) AS n FROM simulation_runs"
                     " WHERE id = %s AND resumen IS NOT NULL", (run_id,), one=True)["n"]

    def test_no_guarda_sobre_una_corrida_que_ya_no_esta_ejecutando(self):
        run_id = self._encola(301)
        self.assertTrue(simulador_datos.marcar_run_ejecutando(run_id))
        simulador_datos.marca_corridas_interrumpidas("cerrada por otro proceso", run_ids=[run_id])

        guardo = simulador_datos.guardar_resultado_run(run_id, self._resultado(301))

        self.assertFalse(guardo)
        fila = self._estado(run_id)
        self.assertEqual(fila["status"], "fallido")
        self.assertEqual(fila["error_message"], "cerrada por otro proceso")
        self.assertEqual(self._resultados_guardados(run_id), 0)
        self.assertEqual(_lote_de(run_id)["status"], "fallido")

    def test_tampoco_sobre_una_encolada(self):
        run_id = self._encola(302)
        self.assertFalse(simulador_datos.guardar_resultado_run(run_id, self._resultado(302)))
        self.assertEqual(self._estado(run_id)["status"], "encolado")
        self.assertEqual(self._resultados_guardados(run_id), 0)

    def test_el_camino_normal_sigue_guardando(self):
        run_id = self._encola(303)
        self.assertTrue(simulador_datos.marcar_run_ejecutando(run_id))
        self.assertTrue(simulador_datos.guardar_resultado_run(run_id, self._resultado(303)))
        self.assertEqual(self._estado(run_id)["status"], "completado")
        self.assertEqual(self._resultados_guardados(run_id), 1)

    def test_ejecutar_run_no_audita_un_completado_que_no_ocurrio(self):
        """De punta a punta: el motor termina, pero mientras corria alguien
        cerro la corrida. No debe quedar un 'completado' en la bitacora."""
        run_id = self._encola(304)
        seir = motores.IMPLEMENTADOS["seir-ref"]

        def simular_y_que_la_cierren(escenario, semilla):
            resultado = seir.simular(escenario, semilla)
            simulador_datos.marca_corridas_interrumpidas("cerrada a media corrida",
                                                 run_ids=[run_id])
            return resultado

        # ejecutar_run toma el motor del registro (procesamiento/motores.py).
        cambiado = motores.Motor(seir.nombre, seir.version, simular_y_que_la_cierren,
                                 seir.simplificaciones)
        with patch.object(ejecucion, "del_nombre", return_value=cambiado), \
                self.assertLogs("microservicios.simulador.ejecucion", level="WARNING"):
            ejecucion.ejecutar_run(run_id, demora_seg=0)

        self.assertEqual(self._estado(run_id)["status"], "fallido")
        completados = query(
            """SELECT count(*) AS n FROM audit_log
               WHERE entity_type = 'simulation_run' AND entity_id = %s
                 AND data_after->>'estado' = 'completado'""",
            (str(run_id),), one=True)["n"]
        self.assertEqual(completados, 0)


if __name__ == "__main__":
    unittest.main()


class PrioridadEstimacionYReintentoTests(_CorridasDePrueba):
    def _prioridad(self, seed, prioridad):
        run_id = self._encola(seed)
        execute("UPDATE simulation_runs SET priority = %s WHERE id = %s", (prioridad, run_id))
        return run_id

    def test_prioridades_de_las_corridas(self):
        alta, normal = self._prioridad(130, "alta"), self._encola(131)
        self.assertEqual(simulador_datos.prioridades([alta, normal]), {alta: "alta", normal: "normal"})
        self.assertEqual(simulador_datos.prioridades([]), {})

    def test_la_posicion_cuenta_las_altas_y_las_anteriores_de_su_prioridad(self):
        normal_a, normal_b = self._encola(132), self._encola(133)
        alta = self._prioridad(134, "alta")
        antes = corridas_datos.estimar_corrida(alta)["queue_position"]
        self.assertEqual(corridas_datos.estimar_corrida(normal_b)["queue_position"],
                         corridas_datos.estimar_corrida(normal_a)["queue_position"] + 1)
        self.assertLess(antes, corridas_datos.estimar_corrida(normal_a)["queue_position"])

    def test_sin_historial_no_hay_cifra_y_se_dice_por_que(self):
        run_id = self._encola(135)
        est = corridas_datos.estimar_corrida(run_id)
        if est["estimate_samples"] == 0:
            self.assertIsNone(est["estimated_seconds"])
            self.assertTrue(est["estimate_reason"])
        else:
            self.assertIsNone(est["estimate_reason"])
            self.assertGreaterEqual(est["estimated_seconds"], 0)

    def test_reintentar_solo_una_fallida_y_una_sola_vez(self):
        run_id = self._encola(136)
        contexto = Contexto.sin_peticion(self.user_id)
        self.assertIsNone(corridas_datos.reintentar_run(run_id, contexto=contexto))
        simulador_datos.marcar_run_fallido(run_id, "x")
        self.assertEqual(corridas_datos.reintentar_run(run_id, contexto=contexto), "normal")
        fila = query("SELECT status, error_message, started_at, attempts, seed FROM simulation_runs"
                     " WHERE id = %s", (run_id,), one=True)
        self.assertEqual((fila["status"], fila["error_message"], fila["started_at"], fila["attempts"],
                          fila["seed"]), ("encolado", None, None, 0, 136))
        self.assertEqual(_lote_de(run_id)["status"], "encolado")
        self.assertIsNone(corridas_datos.reintentar_run(run_id, contexto=contexto))

    def test_con_historial_la_estimacion_es_la_mediana_medida(self):
        hechas = [self._encola(140 + i) for i in range(3)]
        for run_id, segundos in zip(hechas, (10, 20, 60)):
            self.assertTrue(simulador_datos.marcar_run_ejecutando(run_id))
            execute("UPDATE simulation_runs SET status = 'completado', progress = 100,"
                    " resumen = '{}'::jsonb, finished_at = started_at"
                    " + make_interval(secs => %s) WHERE id = %s", (segundos, run_id))
        espera = self._encola(143)
        est = corridas_datos.estimar_corrida(espera)
        self.assertGreaterEqual(est["estimate_samples"], 3)
        self.assertIsNone(est["estimate_reason"])
        self.assertGreater(est["estimated_seconds"], 0)
        self.assertEqual(corridas_datos.estimar_corrida(hechas[0])["estimated_seconds"], None)
