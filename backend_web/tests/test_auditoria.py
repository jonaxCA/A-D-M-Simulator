"""
Pruebas de la bitacora de auditoria (backend_web.queries), especificamente
del caso RUN (ciclo de vida de una simulacion).

Motivo del archivo: bug de UAT donde admin abre /auditoria despues de una
corrida real y no puede distinguir "solicitada" de "ejecutando", "completada"
o "fallida" -- las 4 etapas quedan en audit_log con la MISMA action='RUN'
(ver backend_web/simulaciones.py y backend_web/audit.py); lo que las
distingue es data_after['estado']. get_auditoria_lista()/get_acciones_auditoria()
tenian que abrir ese JSON en vez de mirar solo `action`.

Dos grupos, igual que test_simulaciones.py:
  - `DescribeEventoAuditoriaTests`: la funcion pura _describe_evento_auditoria
    (sin SQL). Corre en cualquier maquina.
  - `AuditoriaIntegracionTests`: contra PostgreSQL real, corriendo una
    simulacion de verdad (demora_seg=0) y verificando que las 4 etapas
    aparecen en get_auditoria_lista() con etiquetas distintas y que el
    filtro compuesto 'RUN::<etapa>' aisla cada una.

Ejecutar:
    DATABASE_URL=postgresql://epidemia_app:epidemia_app_pw@localhost:5432/simulador_epidemico \
    JWT_SECRET_KEY=test-secret \
        python -m unittest backend_web.tests.test_auditoria -v
"""
import unittest

from backend_web.tests.base import ConCorridasDePrueba
from backend_web import queries, simulaciones


# ---------------------------------------------------------------------------
# Funcion pura: _describe_evento_auditoria (sin SQL, sin Flask)
# ---------------------------------------------------------------------------
class DescribeEventoAuditoriaTests(unittest.TestCase):
    def test_las_4_etapas_de_run_dan_descripcion_y_estado_distintos(self):
        casos = {
            "encolado": "Pendiente",
            "ejecutando": "Pendiente",
            "completado": "Correcto",
            "fallido": "Fallido",
        }
        descripciones = set()
        for etapa, estado_esperado in casos.items():
            descripcion, estado = queries._describe_evento_auditoria(
                "RUN", "42", {"estado": etapa}
            )
            self.assertEqual(estado, estado_esperado, etapa)
            descripciones.add(descripcion)
        # Las 4 etapas deben producir 4 textos DIFERENTES -- ese era el bug:
        # las 4 se veian igual ("Ejecucion"/"Correcto").
        self.assertEqual(len(descripciones), 4, descripciones)

    def test_run_fallido_no_se_ve_correcto(self):
        # El bug concreto que reporto UAT: una corrida que SI fallo (forzar
        # error como ADMINISTRADOR) se mostraba con estado "Correcto" porque
        # 'RUN' no estaba en ACCIONES_FALLIDAS. Ahora debe mirar data_after.
        _descripcion, estado = queries._describe_evento_auditoria(
            "RUN", "176", {"estado": "fallido", "error": "boom"}
        )
        self.assertEqual(estado, "Fallido")

    def test_run_fallido_incluye_el_mensaje_de_error(self):
        descripcion, _estado = queries._describe_evento_auditoria(
            "RUN", "176", {"estado": "fallido", "error": "Error forzado de prueba"}
        )
        self.assertIn("Error forzado de prueba", descripcion)

    def test_run_completado_incluye_indicadores(self):
        descripcion, estado = queries._describe_evento_auditoria(
            "RUN", "174",
            {"estado": "completado", "indicadores": {
                "tasa_ataque": 0.475, "casos_acumulados": 237546, "fallecimientos": 113,
            }},
        )
        self.assertEqual(estado, "Correcto")
        self.assertIn("47.5%", descripcion)
        self.assertIn("237546", descripcion)
        self.assertIn("113", descripcion)

    def test_run_etapa_desconocida_no_truena(self):
        descripcion, estado = queries._describe_evento_auditoria(
            "RUN", "1", {"estado": "algo_nuevo_que_no_existe_todavia"}
        )
        self.assertTrue(descripcion)
        self.assertEqual(estado, "Correcto")

    def test_run_sin_data_after_no_truena(self):
        descripcion, estado = queries._describe_evento_auditoria("RUN", "1", None)
        self.assertTrue(descripcion)
        self.assertEqual(estado, "Correcto")

    def test_acciones_no_run_se_comportan_igual_que_antes(self):
        descripcion, estado = queries._describe_evento_auditoria("LOGIN_FAILED", "9", None)
        self.assertEqual(estado, "Fallido")
        descripcion, estado = queries._describe_evento_auditoria("LOGIN", "9", None)
        self.assertEqual(estado, "Correcto")
        
    def test_envio_aprobacion_y_rechazo_de_version_se_distinguen(self):
        descripciones = set()
        for etapa in ("en_revision", "aprobado", "rechazado"):
            descripcion, estado = queries._describe_evento_auditoria(
                "UPDATE", "7", {"status": etapa, "version_number": 2},
                "scenario_versions")
            self.assertEqual(estado, "Correcto", etapa)
            self.assertIn("(v2)", descripcion)
            descripciones.add(descripcion)
        self.assertEqual(len(descripciones), 3, descripciones)

    def test_update_de_otro_modulo_no_cambia(self):
        descripcion, _estado = queries._describe_evento_auditoria(
            "UPDATE", "7", {"status": "aprobado"}, "users")
        self.assertEqual(descripcion, "Modificacion de registro")



# ---------------------------------------------------------------------------
# Integracion contra PostgreSQL real
# ---------------------------------------------------------------------------
class AuditoriaIntegracionTests(ConCorridasDePrueba):
    def test_corrida_completa_deja_las_3_etapas_visibles_y_distintas(self):
        run_id = self._encola(seed=910001)
        from backend_web.audit import log_audit
        from backend_web.contexto import Contexto
        log_audit(Contexto.sin_peticion(self.user_id), "RUN", "simulation_run",
                  entity_id=str(run_id),
                  data_after={"estado": "encolado", "seed": 910001,
                              "scenario_version_id": self.version_id,
                              "forzar_error": False})
        simulaciones.ejecutar_run(run_id, demora_seg=0)

        eventos = queries.get_auditoria_lista(modulo="simulation_run", limit=500)
        propios = [e for e in eventos if e["accion"] == "RUN"
                   and f"SIM-{run_id:05d}" in e["descripcion"]]
        etapas_vistas = {e["descripcion"].split(" SIM-")[0] for e in propios}

        self.assertIn("Simulacion solicitada", etapas_vistas)
        self.assertIn("Simulacion en ejecucion (inicio)", etapas_vistas)
        self.assertIn("Simulacion completada", etapas_vistas)
        # La fila 'completada' debe traer indicadores, no solo el rotulo.
        completada = next(e for e in propios if e["descripcion"].startswith("Simulacion completada"))
        self.assertIn("casos acumulados", completada["descripcion"])
        self.assertEqual(completada["estado"], "Correcto")

    def test_corrida_fallida_forzada_se_ve_fallida_no_correcta(self):
        run_id = self._encola(seed=910002)
        simulaciones.ejecutar_run(run_id, forzar_error=True, demora_seg=0)

        eventos = queries.get_auditoria_lista(modulo="simulation_run", limit=500)
        fallida = next(e for e in eventos if e["accion"] == "RUN"
                        and f"SIM-{run_id:05d}" in e["descripcion"]
                        and e["descripcion"].startswith("Simulacion fallida"))
        self.assertEqual(fallida["estado"], "Fallido")
        self.assertIn("Error forzado de prueba", fallida["descripcion"])

    def test_filtro_compuesto_run_fallido_aisla_solo_las_fallidas(self):
        run_id = self._encola(seed=910003)
        simulaciones.ejecutar_run(run_id, forzar_error=True, demora_seg=0)

        eventos = queries.get_auditoria_lista(accion="RUN::fallido", limit=500)
        self.assertTrue(eventos)
        for e in eventos:
            self.assertEqual(e["estado"], "Fallido")
            self.assertTrue(e["descripcion"].startswith("Simulacion fallida"))

    def test_get_acciones_auditoria_incluye_las_etapas_de_run(self):
        run_id = self._encola(seed=910004)
        simulaciones.ejecutar_run(run_id, demora_seg=0)

        opciones = {o["valor"]: o["etiqueta"] for o in queries.get_acciones_auditoria()}
        self.assertIn("RUN::encolado", opciones)
        self.assertIn("RUN::ejecutando", opciones)
        self.assertIn("RUN::completado", opciones)
        self.assertEqual(opciones["RUN::completado"], "Simulacion completada")
        # RUN "plano" ya no debe listarse: solo sus etapas.
        self.assertNotIn("RUN", opciones)


if __name__ == "__main__":
    unittest.main()
