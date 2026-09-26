"""
Pruebas del Bloque F (ejecucion, estados y resultados de simulaciones).

Dos grupos, en el mismo archivo:

  - `TraduccionYFormatoTests`: funciones PURAS (sin SQL, sin Flask) de
    backend_web.simulaciones -- identificadores visibles, mapeo de estados y
    la traduccion de una version de escenario a la entrada del motor. No
    requieren PostgreSQL: corren en cualquier maquina.

  - `SimulacionesIntegracionTests`: contra PostgreSQL real, sin mocks (mismo
    criterio que el resto del proyecto -- ver backend_web/tests/test_regiones.py).
    Ejercita crear_corrida(), la corrida en segundo plano (ejecutar_run, con
    demora_seg=0 para no esperar) y la deteccion de reproducibilidad. Usa el
    escenario de demostracion (datos/postgres/semillas/demo_datos_nl.sql:
    "Ola Influenza ZMM - otono 2026", version aprobada) y limpia todo lo que
    inserta en el tearDown.

Ejecutar:
    DATABASE_URL=postgresql://epidemia_app:epidemia_app_pw@localhost:5432/simulador_epidemico \
    JWT_SECRET_KEY=test-secret \
        python -m unittest backend_web.tests.test_simulaciones -v
"""
import os
import unittest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend_web import queries, simulaciones
from backend_web.db import get_conn, query


# ---------------------------------------------------------------------------
# Funciones puras: identificadores, estados, traduccion del escenario
# ---------------------------------------------------------------------------
class TraduccionYFormatoTests(unittest.TestCase):
    def test_id_simulacion_rellena_con_ceros(self):
        self.assertEqual(simulaciones.id_simulacion(42), "SIM-00042")
        self.assertEqual(simulaciones.id_simulacion(1), "SIM-00001")

    def test_id_simulacion_no_truncase_con_numeros_grandes(self):
        self.assertEqual(simulaciones.id_simulacion(123456), "SIM-123456")

    def test_id_escenario_rellena_con_ceros(self):
        self.assertEqual(simulaciones.id_escenario(3), "ESC-003")
        self.assertEqual(simulaciones.id_escenario(1234), "ESC-1234")

    def test_estado_visible_mapea_los_cinco_estados_de_la_base(self):
        self.assertEqual(simulaciones.estado_visible("encolado"), "PENDIENTE")
        self.assertEqual(simulaciones.estado_visible("ejecutando"), "EJECUTANDO")
        self.assertEqual(simulaciones.estado_visible("completado"), "COMPLETADA")
        self.assertEqual(simulaciones.estado_visible("fallido"), "ERROR")
        self.assertEqual(simulaciones.estado_visible("cancelado"), "CANCELADA")

    def test_estado_visible_desconocido_no_truena(self):
        self.assertEqual(simulaciones.estado_visible("algo_nuevo"), "ALGO_NUEVO")

    def test_clase_badge_estado_cubre_los_estados_conocidos(self):
        for estado in ("encolado", "ejecutando", "completado", "fallido", "cancelado"):
            self.assertTrue(simulaciones.clase_badge_estado(estado).startswith("badge-"))

    # -- construir_escenario: la traduccion pura -----------------------------
    ENFERMEDAD_COMPLETA = {
        "r0": {"valor": 1.3, "fuente": "lit.", "supuesto": False},
        "incubacion_dias": {"valor": 2.0, "fuente": "lit.", "supuesto": False},
        "infeccioso_dias": {"valor": 5.0, "fuente": "lit.", "supuesto": False},
        "dias_hospitalizacion": {"valor": 5.0, "fuente": "lit.", "supuesto": False},
        "tasa_hospitalizacion": {"valor": 0.01, "fuente": "lit.", "supuesto": False},
        "letalidad": {"valor": 0.001, "fuente": "lit.", "supuesto": False},
    }
    ESTRUCTURA_EDAD = {"0-19": 40, "20-39": 40, "40-59": 15, "60-79": 4, "80+": 1}

    def test_construir_escenario_reparte_poblacion_exacto(self):
        escenario, errores = simulaciones.construir_escenario(
            population_size=1000,
            horizon_days=90,
            initial_infected=5,
            estructura_edad=self.ESTRUCTURA_EDAD,
            default_params=self.ENFERMEDAD_COMPLETA,
        )
        self.assertEqual(errores, [])
        self.assertIsNotNone(escenario)
        # La suma tiene que cuadrar EXACTO con population_size, sin importar
        # el redondeo de cada grupo (el residuo se le suma al grupo mayor).
        self.assertEqual(sum(escenario["poblacion"].values()), 1000)
        self.assertEqual(escenario["poblacion"]["0-19"], 400)  # 40% de 1000
        self.assertEqual(escenario["dias"], 90)
        self.assertEqual(escenario["infectados_iniciales"], 5)
        self.assertEqual(escenario["intervenciones"], [])
        self.assertEqual(escenario["enfermedad"], self.ENFERMEDAD_COMPLETA)

    def test_construir_escenario_conserva_intervenciones(self):
        intervenciones = [{"tipo": "CIERRE_ESCUELAS", "dia_inicio": 7, "dia_fin": 45,
                           "cobertura": 1.0, "cumplimiento": 0.9, "params": {"reduccion": 1.0}}]
        escenario, errores = simulaciones.construir_escenario(
            population_size=1000, horizon_days=90, initial_infected=5,
            estructura_edad=self.ESTRUCTURA_EDAD, default_params=self.ENFERMEDAD_COMPLETA,
            intervenciones=intervenciones,
        )
        self.assertEqual(errores, [])
        self.assertEqual(escenario["intervenciones"], intervenciones)

    def test_construir_escenario_sin_parametros_de_enfermedad_da_error_claro(self):
        escenario, errores = simulaciones.construir_escenario(
            population_size=1000, horizon_days=90, initial_infected=5,
            estructura_edad=self.ESTRUCTURA_EDAD, default_params={},
        )
        self.assertIsNone(escenario)
        self.assertEqual(len(errores), 1)
        self.assertIn("parametros de simulacion", errores[0])

    def test_construir_escenario_sin_estructura_de_edad_da_error_claro(self):
        escenario, errores = simulaciones.construir_escenario(
            population_size=1000, horizon_days=90, initial_infected=5,
            estructura_edad={}, default_params=self.ENFERMEDAD_COMPLETA,
        )
        self.assertIsNone(escenario)
        self.assertEqual(len(errores), 1)
        self.assertIn("poblacion por grupo de edad", errores[0])

    def test_construir_escenario_da_los_dos_errores_juntos(self):
        # Ninguno de los dos: la funcion no se detiene en el primero, junta
        # todos los errores -- igual que motor.parametros.EscenarioInvalido.
        escenario, errores = simulaciones.construir_escenario(
            population_size=1000, horizon_days=90, initial_infected=5,
            estructura_edad={}, default_params=None,
        )
        self.assertIsNone(escenario)
        self.assertEqual(len(errores), 2)

    def test_construir_escenario_produce_una_entrada_que_el_motor_acepta(self):
        """Prueba de contrato: lo que construye simulaciones.construir_escenario
        tiene que ser justo lo que motor.simular() espera. No repite las
        validaciones internas del motor -- solo confirma que la corrida no
        truena y que el resultado tiene la forma esperada."""
        escenario, errores = simulaciones.construir_escenario(
            population_size=5000, horizon_days=30, initial_infected=10,
            estructura_edad=self.ESTRUCTURA_EDAD, default_params=self.ENFERMEDAD_COMPLETA,
        )
        self.assertEqual(errores, [])
        resultado = simulaciones.simular(escenario, semilla=123)
        self.assertEqual(resultado["engine_version"], simulaciones.ENGINE_VERSION)
        self.assertIn("casos_acumulados", resultado["resumen"])
        self.assertEqual(len(resultado["serie"]), 31)  # dia 0 + 30 dias

    def test_misma_semilla_mismo_resultado(self):
        """Reproducibilidad a nivel motor: la base de lo que la pantalla de
        detalle demuestra con dos corridas reales."""
        escenario, _ = simulaciones.construir_escenario(
            population_size=5000, horizon_days=30, initial_infected=10,
            estructura_edad=self.ESTRUCTURA_EDAD, default_params=self.ENFERMEDAD_COMPLETA,
        )
        r1 = simulaciones.simular(escenario, semilla=7)
        r2 = simulaciones.simular(escenario, semilla=7)
        self.assertEqual(r1["resumen"], r2["resumen"])
        self.assertEqual(r1["huella_escenario"], r2["huella_escenario"])


# ---------------------------------------------------------------------------
# Integracion contra PostgreSQL real
# ---------------------------------------------------------------------------
def _tiene_base():
    try:
        query("SELECT 1", one=True)
        return True
    except Exception:
        return False


@unittest.skipUnless(_tiene_base(), "Requiere PostgreSQL en DATABASE_URL (ver docstring del modulo).")
class SimulacionesIntegracionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.version_aprobada = query(
            """
            SELECT sv.id FROM scenario_versions sv
            JOIN scenarios s ON s.id = sv.scenario_id
            WHERE s.name = 'Ola Influenza ZMM - otono 2026' AND sv.status = 'aprobado'
            """,
            one=True,
        )
        if not cls.version_aprobada:
            raise unittest.SkipTest(
                "No se encontro el escenario de demostracion aprobado; "
                "carga datos/postgres/semillas/demo_datos_nl.sql."
            )
        cls.version_id = cls.version_aprobada["id"]
        cls.user_id = query(
            "SELECT id FROM users WHERE username = 'alex.cavazos'", one=True
        )["id"]

    def setUp(self):
        self._batches_creados = []

    def tearDown(self):
        # Cascada: simulation_batches -> simulation_runs -> simulation_results.
        # audit_log es de solo insercion (trigger fn_solo_insercion) y no se
        # limpia -- son eventos reales de que este test uso la app, igual que
        # cualquier corrida real.
        for batch_id in self._batches_creados:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM simulation_batches WHERE id = %s", (batch_id,))
                conn.commit()

    def _encola(self, seed):
        run_id, batch_id, error = queries.crear_corrida(
            self.version_id, seed, self.user_id, simulaciones.ENGINE_VERSION,
        )
        self.assertIsNone(error, error)
        self._batches_creados.append(batch_id)
        return run_id

    def test_construir_escenario_desde_version_del_demo_no_da_errores(self):
        escenario, version, errores = simulaciones.construir_escenario_desde_version(
            self.version_id
        )
        self.assertEqual(errores, [], errores)
        self.assertIsNotNone(escenario)
        self.assertEqual(sum(escenario["poblacion"].values()), version["population_size"])
        self.assertEqual(escenario["dias"], version["horizon_days"])

    def test_construir_escenario_desde_version_inexistente(self):
        escenario, version, errores = simulaciones.construir_escenario_desde_version(999999999)
        self.assertIsNone(escenario)
        self.assertIsNone(version)
        self.assertEqual(errores, ["La version de escenario no existe."])

    def test_crear_corrida_rechaza_version_no_aprobada(self):
        # Se crea una version 'borrador' del MISMO escenario de demo: no hay
        # que inventar catalogos nuevos, solo un estado distinto.
        fila = query(
            "SELECT scenario_id, population_size, horizon_days FROM scenario_versions WHERE id = %s",
            (self.version_id,), one=True,
        )
        # query() no hace commit (ver backend_web/db.py): para un INSERT hay
        # que abrir la conexion y confirmarla a mano, igual que el resto de
        # las escrituras de queries.py.
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scenario_versions
                        (scenario_id, version_number, is_current, population_size,
                         horizon_days, initial_infected, created_by, status)
                    VALUES (%s, 999, FALSE, %s, %s, 10, %s, 'borrador')
                    RETURNING id
                    """,
                    (fila["scenario_id"], fila["population_size"], fila["horizon_days"], self.user_id),
                )
                nueva_id = cur.fetchone()[0]
            conn.commit()
        nueva = {"id": nueva_id}
        try:
            run_id, batch_id, error = queries.crear_corrida(
                nueva["id"], 1, self.user_id, simulaciones.ENGINE_VERSION,
            )
            self.assertIsNone(run_id)
            self.assertIsNotNone(error)
            self.assertIn("no está aprobada", error)
        finally:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM scenario_versions WHERE id = %s", (nueva["id"],))
                conn.commit()

    def test_ejecutar_run_completa_con_el_escenario_de_demo(self):
        run_id = self._encola(seed=55555)
        simulaciones.ejecutar_run(run_id, demora_seg=0)

        run = queries.get_run(run_id)
        self.assertEqual(run["status"], "completado")
        self.assertIsNotNone(run["started_at"])
        self.assertIsNotNone(run["finished_at"])

        resultado = queries.get_resultado_run(run_id)
        self.assertIsNotNone(resultado)
        for clave in ("casos_acumulados", "casos_activos_final", "pico_casos_activos",
                     "dia_pico", "hospitalizaciones", "fallecimientos", "tasa_ataque"):
            self.assertIn(clave, resultado["resumen"])
        self.assertEqual(len(resultado["serie"]), run["horizon_days"] + 1)

    def test_ejecutar_run_forzado_queda_en_error_con_mensaje(self):
        run_id = self._encola(seed=55556)
        simulaciones.ejecutar_run(run_id, forzar_error=True, demora_seg=0)

        run = queries.get_run(run_id)
        self.assertEqual(run["status"], "fallido")
        self.assertIsNotNone(run["error_message"])
        self.assertIn("Error forzado de prueba", run["error_message"])
        self.assertIsNone(queries.get_resultado_run(run_id))

    def test_misma_semilla_produce_run_equivalente(self):
        seed = 55557
        run_id_1 = self._encola(seed=seed)
        simulaciones.ejecutar_run(run_id_1, demora_seg=0)
        resultado_1 = queries.get_resultado_run(run_id_1)

        run_id_2 = self._encola(seed=seed)
        simulaciones.ejecutar_run(run_id_2, demora_seg=0)
        resultado_2 = queries.get_resultado_run(run_id_2)

        self.assertEqual(resultado_1["scenario_checksum"], resultado_2["scenario_checksum"])
        self.assertEqual(resultado_1["resumen"], resultado_2["resumen"])

        equivalente = queries.buscar_run_equivalente(
            run_id_2, self.version_id, seed, resultado_2["scenario_checksum"],
        )
        self.assertIsNotNone(equivalente)
        self.assertEqual(equivalente["id"], run_id_1)
        self.assertEqual(equivalente["resumen"], resultado_2["resumen"])

    def test_distinta_semilla_no_se_marca_como_equivalente(self):
        run_id_1 = self._encola(seed=1111)
        simulaciones.ejecutar_run(run_id_1, demora_seg=0)
        resultado_1 = queries.get_resultado_run(run_id_1)

        run_id_2 = self._encola(seed=2222)
        simulaciones.ejecutar_run(run_id_2, demora_seg=0)
        resultado_2 = queries.get_resultado_run(run_id_2)

        equivalente = queries.buscar_run_equivalente(
            run_id_2, self.version_id, 2222, resultado_2["scenario_checksum"],
        )
        # Semillas distintas -> ninguna otra corrida coincide en (version, seed).
        self.assertIsNone(equivalente)
        self.assertNotEqual(resultado_1["resumen"], resultado_2["resumen"])

    # -- Revision de codigo: marcar_run_ejecutando/marcar_run_fallido con -----
    # -- rowcount, y que guardar_resultado_run nunca deje una corrida a medias
    def test_marcar_run_ejecutando_da_false_si_la_corrida_ya_no_esta_encolada(self):
        run_id = self._encola(seed=90001)
        self.assertTrue(queries.marcar_run_ejecutando(run_id))  # 1a vez: encolado -> ejecutando
        # 2a vez: ya no esta 'encolado' (esto es lo que evita que dos hilos
        # corran la misma simulation_run a la vez).
        self.assertFalse(queries.marcar_run_ejecutando(run_id))
        self.assertEqual(queries.get_run(run_id)["status"], "ejecutando")

    def test_marcar_run_fallido_no_pisa_un_estado_terminal(self):
        run_id = self._encola(seed=90002)
        queries.marcar_run_ejecutando(run_id)
        self.assertTrue(queries.marcar_run_fallido(run_id, "primer error"))
        self.assertEqual(queries.get_run(run_id)["error_message"], "primer error")

        # La corrida ya quedo en 'fallido' (estado terminal): una segunda
        # llamada no debe pisar el mensaje ni reportar que hizo la transicion.
        self.assertFalse(queries.marcar_run_fallido(run_id, "segundo error, no deberia aplicar"))
        self.assertEqual(queries.get_run(run_id)["error_message"], "primer error")

    def test_ejecutar_run_no_hace_nada_si_otro_hilo_ya_la_arranco(self):
        """Cubre el hallazgo de revision de codigo sobre marcar_run_ejecutando:
        si el UPDATE no afecta ninguna fila (porque la corrida ya no esta
        'encolado'), ejecutar_run tiene que abortar sin auditar 'ejecutando'
        ni tocar el resultado -- no seguir de largo como si nada."""
        run_id = self._encola(seed=90003)
        self.assertTrue(queries.marcar_run_ejecutando(run_id))  # simula que otro hilo la arranco primero

        simulaciones.ejecutar_run(run_id, demora_seg=0)  # ya no esta 'encolado' -> debe abortar

        run = queries.get_run(run_id)
        self.assertEqual(run["status"], "ejecutando")  # sin cambios: ni completado ni fallido
        self.assertIsNone(run["finished_at"])
        self.assertIsNone(queries.get_resultado_run(run_id))

    def test_guardar_resultado_run_hace_rollback_si_el_insert_falla(self):
        """ck_simulation_results_checksum exige un sha256 hexadecimal (o NULL);
        un huella_escenario invalido tiene que tronar el INSERT SIN dejar la
        corrida marcada 'completado' (ver el fix de guardar_resultado_run en
        queries.py: rollback explicito antes de relanzar)."""
        run_id = self._encola(seed=90004)
        queries.marcar_run_ejecutando(run_id)
        resultado_invalido = {
            "engine_version": simulaciones.ENGINE_VERSION,
            "huella_escenario": "esto-no-es-un-checksum-sha256",
            "resumen": {"casos_acumulados": 1},
            "serie": [],
            "trazabilidad_parametros": [],
        }
        with self.assertRaises(Exception):
            queries.guardar_resultado_run(run_id, resultado_invalido)

        self.assertIsNone(queries.get_resultado_run(run_id))
        self.assertEqual(queries.get_run(run_id)["status"], "ejecutando")

    def test_ejecutar_run_marca_fallido_si_guardar_resultado_run_truena(self):
        """Ninguna corrida debe quedar atascada en 'ejecutando' -- ni siquiera
        si el fallo ocurre DESPUES de que el motor ya calculo el resultado.
        Se reemplaza queries.guardar_resultado_run (no hay mocks en el resto
        del proyecto, pero forzar esta falla real por otra via requeriria
        romper el propio motor) y se restaura siempre en el finally."""
        run_id = self._encola(seed=90005)
        original = queries.guardar_resultado_run

        def _guardar_roto(run_id, resultado):
            raise RuntimeError("fallo simulado de guardar_resultado_run (prueba)")

        queries.guardar_resultado_run = _guardar_roto
        try:
            simulaciones.ejecutar_run(run_id, demora_seg=0)
        finally:
            queries.guardar_resultado_run = original

        run = queries.get_run(run_id)
        self.assertEqual(run["status"], "fallido")
        self.assertIn("fallo simulado de guardar_resultado_run", run["error_message"])
        self.assertIsNone(queries.get_resultado_run(run_id))


if __name__ == "__main__":
    unittest.main()
