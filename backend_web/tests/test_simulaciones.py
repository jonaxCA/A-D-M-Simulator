"""
Pruebas del Bloque F (ejecucion, estados y resultados de simulaciones).

Dos grupos, en el mismo archivo:

  - `TraduccionYFormatoTests`: funciones PURAS (sin SQL, sin Flask) --
    identificadores visibles, estados y la traduccion de una version de
    escenario a la entrada del motor (queries.escenario_de_version). No
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
import copy
import json
import unittest

from backend_web.tests.base import ConCorridasDePrueba
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

    def test_estado_visible_muestra_el_estado_de_la_base(self):
        # Regla 7 de AGENTS.md: nada de PENDIENTE/COMPLETADA/ERROR.
        self.assertEqual(simulaciones.estado_visible("encolado"), "ENCOLADO")
        self.assertEqual(simulaciones.estado_visible("ejecutando"), "EJECUTANDO")
        self.assertEqual(simulaciones.estado_visible("completado"), "COMPLETADO")
        self.assertEqual(simulaciones.estado_visible("fallido"), "FALLIDO")
        self.assertEqual(simulaciones.estado_visible("cancelado"), "CANCELADO")

    def test_estado_visible_desconocido_no_truena(self):
        self.assertEqual(simulaciones.estado_visible("algo_nuevo"), "ALGO_NUEVO")

    def test_clase_badge_estado_cubre_los_estados_conocidos(self):
        for estado in ("encolado", "ejecutando", "completado", "fallido", "cancelado"):
            self.assertTrue(simulaciones.clase_badge_estado(estado).startswith("badge-"))

    # -- escenario_de_version: la traduccion pura ----------------------------
    ENFERMEDAD_COMPLETA = {
        "r0": {"valor": 1.3, "fuente": "lit.", "supuesto": False},
        "incubacion_dias": {"valor": 2.0, "fuente": "lit.", "supuesto": False},
        "infeccioso_dias": {"valor": 5.0, "fuente": "lit.", "supuesto": False},
        "dias_hospitalizacion": {"valor": 5.0, "fuente": "lit.", "supuesto": False},
        "tasa_hospitalizacion": {"valor": 0.01, "fuente": "lit.", "supuesto": False},
        "letalidad": {"valor": 0.001, "fuente": "lit.", "supuesto": False},
    }
    POR_EDAD = {"0-19": 400, "20-39": 400, "40-59": 150, "60-79": 40, "80+": 10}

    def _detalle(self, **version):
        """Lo minimo de queries.get_escenario_detalle() que usa la traduccion."""
        base = {"population_by_age": None, "population_size": 5000,
                "population_age_unknown": 0, "age_unknown_policy": None,
                "initial_infected": 10, "horizon_days": 30}
        base.update(version)
        return {"version": base, "parametros_enfermedad": self.ENFERMEDAD_COMPLETA,
                "intervenciones": []}

    def test_escenario_de_version_usa_la_poblacion_por_edad_de_la_version(self):
        detalle = self._detalle(population_by_age=self.POR_EDAD, population_size=1007,
                                population_age_unknown=7, age_unknown_policy="excluir")
        escenario = queries.escenario_de_version(detalle)
        self.assertEqual(escenario["poblacion"], self.POR_EDAD)
        self.assertEqual(escenario["poblacion_edad_desconocida"], 7)
        self.assertEqual(escenario["politica_edad_desconocida"], "excluir")
        self.assertEqual(escenario["enfermedad"], self.ENFERMEDAD_COMPLETA)

    def test_escenario_de_version_sin_estratificar_pasa_el_total(self):
        escenario = queries.escenario_de_version(self._detalle())
        self.assertEqual(escenario["poblacion"], 5000)
        self.assertNotIn("politica_edad_desconocida", escenario)

    def test_escenario_de_version_traduce_las_intervenciones(self):
        detalle = self._detalle()
        detalle["intervenciones"] = [{
            "code": "CIERRE_ESCUELAS", "start_day": 7, "end_day": 20,
            "coverage": 1, "compliance": 0.9, "params": {"reduccion": 1.0}}]
        escenario = queries.escenario_de_version(detalle)
        self.assertEqual(escenario["intervenciones"], [{
            "tipo": "CIERRE_ESCUELAS", "dia_inicio": 7, "dia_fin": 20,
            "cobertura": 1.0, "cumplimiento": 0.9, "params": {"reduccion": 1.0}}])

    def test_la_entrada_la_acepta_el_motor(self):
        """Prueba de contrato: lo que arma escenario_de_version es justo lo que
        motor.simular() espera."""
        escenario = queries.escenario_de_version(self._detalle(population_by_age=self.POR_EDAD,
                                                               population_size=1000))
        resultado = simulaciones.simular(escenario, semilla=123)
        self.assertEqual(resultado["engine_version"], simulaciones.ENGINE_VERSION)
        self.assertIn("casos_acumulados", resultado["resumen"])
        self.assertEqual(len(resultado["serie"]), 31)  # dia 0 + 30 dias

    def test_misma_semilla_mismo_resultado(self):
        """Reproducibilidad a nivel motor: la base de lo que la pantalla de
        detalle demuestra con dos corridas reales."""
        escenario = queries.escenario_de_version(self._detalle())
        r1 = simulaciones.simular(escenario, semilla=7)
        r2 = simulaciones.simular(escenario, semilla=7)
        self.assertEqual(r1["resumen"], r2["resumen"])
        self.assertEqual(r1["huella_escenario"], r2["huella_escenario"])


# ---------------------------------------------------------------------------
# Integracion contra PostgreSQL real
# ---------------------------------------------------------------------------
class SimulacionesIntegracionTests(ConCorridasDePrueba):
    def test_construir_escenario_desde_version_del_demo_no_da_errores(self):
        escenario, version, errores = simulaciones.construir_escenario_desde_version(
            self.version_id
        )
        self.assertEqual(errores, [], errores)
        self.assertIsNotNone(escenario)
        # La version de demostracion no se estratifica: se simula el total.
        self.assertEqual(escenario["poblacion"], version["population_size"])
        self.assertEqual(escenario["dias"], version["horizon_days"])

    def _version_aprobada(self, disease_params):
        """Version aprobada del escenario de demostracion con poblacion por
        edad, gente sin edad excluida y parametros congelados. Devuelve su id;
        el llamador la borra."""
        por_edad = {"0-19": 3000, "20-39": 3000, "40-59": 2000, "60-79": 1500, "80+": 500}
        fila = query("SELECT scenario_id FROM scenario_versions WHERE id = %s",
                     (self.version_id,), one=True)
        revisor = query("SELECT id FROM users WHERE username = 'diana.flores'", one=True)["id"]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scenario_versions
                        (scenario_id, version_number, is_current, population_size,
                         horizon_days, initial_infected, created_by, status,
                         submitted_at, reviewed_by, reviewed_at,
                         population_by_age, population_age_unknown, age_unknown_policy,
                         disease_params)
                    VALUES (%s, 998, FALSE, 10007, 30, 10, %s, 'aprobado',
                            now(), %s, now(), %s::jsonb, 7, 'excluir', %s::jsonb)
                    RETURNING id
                    """,
                    (fila["scenario_id"], self.user_id, revisor,
                     json.dumps(por_edad), json.dumps(disease_params)),
                )
                version_id = cur.fetchone()[0]
            conn.commit()
        return version_id, por_edad

    def _borra_version(self, version_id):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM scenario_versions WHERE id = %s", (version_id,))
            conn.commit()

    def _parametros_del_catalogo(self):
        return copy.deepcopy(query(
            """SELECT d.default_params FROM scenario_versions sv
               JOIN scenarios s ON s.id = sv.scenario_id
               JOIN diseases d ON d.id = s.disease_id
               WHERE sv.id = %s""", (self.version_id,), one=True)["default_params"])

    def test_la_corrida_simula_lo_que_se_aprobo(self):
        """La corrida tiene que usar la poblacion por edad y los parametros
        congelados de la version, no las bandas actuales de la region ni los
        parametros vivos del catalogo."""
        congelados = self._parametros_del_catalogo()
        congelados["r0"] = {"valor": 1.11, "fuente": "congelado en la prueba", "supuesto": False}
        version_id, por_edad = self._version_aprobada(congelados)
        try:
            escenario, _version, errores = simulaciones.construir_escenario_desde_version(version_id)
            self.assertEqual(errores, [], errores)
            self.assertEqual(escenario["poblacion"], por_edad)
            self.assertEqual(escenario["politica_edad_desconocida"], "excluir")
            self.assertEqual(escenario["enfermedad"]["r0"]["valor"], 1.11)

            detalle = queries.get_escenario_detalle(_version["scenario_id"], 998)
            self.assertEqual(escenario, queries.escenario_de_version(detalle),
                             "la corrida y la revision deben armar la misma entrada")
        finally:
            self._borra_version(version_id)

    def test_no_simula_parametros_sin_fuente(self):
        """Regla 8: un parametro sin fuente ni marca de supuesto impide simular,
        aunque la version ya este aprobada."""
        congelados = self._parametros_del_catalogo()
        congelados["incubacion_dias"] = {"media": 2.0}   # formato de la 010, sin fuente
        version_id, _ = self._version_aprobada(congelados)
        try:
            escenario, _version, errores = simulaciones.construir_escenario_desde_version(version_id)
            self.assertIsNone(escenario)
            self.assertEqual(len(errores), 1)
            self.assertIn("no tienen fuente ni marca de supuesto", errores[0])
        finally:
            self._borra_version(version_id)

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
