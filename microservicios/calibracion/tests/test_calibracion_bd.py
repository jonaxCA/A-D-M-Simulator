import unittest

from epidemia_comun.bd import query
from microservicios.calibracion import datos
from microservicios.pruebas_bd import contexto_de_prueba, escribe, tiene_base

CONFIG = {"muestras": 100, "semillas": 1, "cuantil": 0.1, "semilla_muestreo": 1}


# Contra la base de pruebas. Cada prueba borra sus calibraciones al terminar (el rol de la app
# puede; svc_calibracion no). La bitácora se queda: es de solo inserción.
@unittest.skipUnless(tiene_base(), "Requiere la base de pruebas")
class CalibracionBdTests(unittest.TestCase):
    def setUp(self):
        self.user_id = query("SELECT min(id) AS id FROM users", one=True)["id"]
        self.contexto = contexto_de_prueba(self.user_id)
        self.conjunto = query("SELECT id FROM observed_datasets WHERE code = 'COVID19_NL_2020_SINTOMAS' "
                              "AND version = 1", one=True)["id"]
        self.creadas = []
        self.addCleanup(lambda: self.creadas and escribe(
            "DELETE FROM calibrations WHERE id = ANY(%s)", (self.creadas,)))

    def crea(self):
        cal_id = datos.crear(self.conjunto, "seir-ref", "seir-ref-0.1", "abc-rechazo", "calibracion-0.1",
                             CONFIG, self.user_id, contexto=self.contexto)
        self.creadas.append(cal_id)
        return cal_id

    def test_la_serie_de_d50_sirve_para_calibrar(self):
        base, errores = datos.base(datos.conjunto(self.conjunto))
        self.assertEqual(errores, [])
        self.assertEqual(sum(base["poblacion"].values()) + base["poblacion_edad_desconocida"], 5784442)
        self.assertEqual(base["politica_edad_desconocida"], "prorratear")
        puntos = datos.puntos(self.conjunto)
        self.assertEqual((len(puntos), puntos[0], sum(p["valor"] for p in puntos)),
                         (22, {"inicio": "2020-03-01", "valor": 7}, 22259))

    def test_alta_y_bitacora(self):
        cal_id = self.crea()
        fila = datos.get(cal_id, con_resultado=True)
        self.assertEqual((fila["status"], fila["attempts"], fila["config"], fila["dataset_code"], fila["result"]),
                         ("encolado", 0, CONFIG, "COVID19_NL_2020_SINTOMAS", None))
        self.assertIn(cal_id, datos.encoladas())
        asiento = query("""SELECT user_id, data_after FROM audit_log WHERE action = 'RUN'
                           AND entity_type = 'calibration' AND entity_id = %s""", (str(cal_id),), one=True)
        self.assertEqual((asiento["user_id"], asiento["data_after"]["estado"]), (self.user_id, "encolado"))
        self.assertEqual([f["id"] for f in datos.listar(100, "encolado", self.conjunto) if f["id"] == cal_id],
                         [cal_id])
        self.assertEqual(datos.listar(100, regiones={-1}), [])

    def test_ejecutar_completar_y_no_repetir(self):
        cal_id = self.crea()
        self.assertTrue(datos.marcar_ejecutando(cal_id, contexto=self.contexto))
        self.assertFalse(datos.marcar_ejecutando(cal_id, contexto=self.contexto))
        resultado = {"parametros": [], "metricas": {}, "semanas": []}
        self.assertTrue(datos.completar(cal_id, resultado, contexto=self.contexto))
        self.assertFalse(datos.completar(cal_id, resultado, contexto=self.contexto))
        fila = datos.get(cal_id, con_resultado=True)
        self.assertEqual((fila["status"], fila["attempts"], fila["progress"], fila["result"]),
                         ("completado", 1, 100, resultado))
        self.assertIsNotNone(fila["finished_at"])
        self.assertFalse(datos.cancelar(cal_id, contexto=self.contexto))

    def test_cancelar_en_ejecucion_deja_el_estado_anterior_en_la_bitacora(self):
        cal_id = self.crea()
        datos.marcar_ejecutando(cal_id, contexto=self.contexto)
        self.assertTrue(datos.cancelar(cal_id, contexto=self.contexto))
        self.assertEqual(datos.estado(cal_id), "cancelado")
        self.assertFalse(datos.completar(cal_id, {"parametros": [], "metricas": {}}, contexto=self.contexto))
        asiento = query("""SELECT data_before FROM audit_log WHERE action = 'CANCEL'
                           AND entity_type = 'calibration' AND entity_id = %s""", (str(cal_id),), one=True)
        self.assertEqual(asiento["data_before"], {"estado": "ejecutando"})

    def test_al_arrancar_se_reencolan_las_interrumpidas(self):
        viva, agotada, vieja = self.crea(), self.crea(), self.crea()
        for cal_id in (viva, agotada, vieja):
            datos.marcar_ejecutando(cal_id, contexto=self.contexto)
        escribe("UPDATE calibrations SET attempts = 3 WHERE id = %s", (agotada,))
        escribe("UPDATE calibrations SET engine_version = 'seir-ref-0.0' WHERE id = %s", (vieja,))
        reencoladas, cerradas = datos.reencola_interrumpidas("seir-ref-0.1", contexto_de_prueba)
        self.assertIn(viva, reencoladas)
        self.assertLessEqual({agotada, vieja}, set(cerradas))
        self.assertEqual([datos.estado(i) for i in (viva, agotada, vieja)], ["encolado", "fallido", "fallido"])
        self.assertTrue(datos.marcar_ejecutando(viva, contexto=self.contexto))
        self.assertEqual(datos.get(viva)["attempts"], 2)

    def test_la_base_exige_resultado_al_completar(self):
        cal_id = self.crea()
        with self.assertRaises(Exception):
            escribe("UPDATE calibrations SET status = 'completado', finished_at = now() WHERE id = %s",
                    (cal_id,))
