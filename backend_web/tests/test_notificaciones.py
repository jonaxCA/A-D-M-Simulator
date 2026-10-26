"""
Avisos de backend_web/notificaciones.py, que escribe el microservicio
notificaciones.

Ejecutar:
    python -m unittest backend_web.tests.test_notificaciones -v
"""
import unittest

from backend_web import notificaciones
from backend_web.contexto import Contexto
from backend_web.db import query
from backend_web.tests.base import escribe, id_de_usuario, requiere_base


class ValidaNotificacionTests(unittest.TestCase):
    def test_una_valida_no_tiene_errores(self):
        self.assertEqual(notificaciones.valida_notificacion(
            {"user_id": 3, "type": "RUN_FINISHED", "title": "Terminó", "payload": {"run_id": 1}}), [])

    def test_errores_de_cada_campo(self):
        errores = notificaciones.valida_notificacion(
            {"user_id": True, "type": "OTRO", "title": " ", "body": 5, "payload": [1]})
        self.assertEqual(len(errores), 5)

    def test_titulo_demasiado_largo(self):
        errores = notificaciones.valida_notificacion(
            {"user_id": 3, "type": "SYSTEM", "title": "x" * (notificaciones.TITULO_MAX + 1)})
        self.assertEqual(len(errores), 1)


@requiere_base
class NotificacionesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dueno = id_de_usuario("alex.cavazos")
        cls.otro = query("SELECT id FROM users WHERE id <> %s ORDER BY id LIMIT 1",
                         (cls.dueno,), one=True)["id"]
        cls.servicio = Contexto(None, "127.0.0.1", "servicio pruebas")

    def setUp(self):
        self.creadas = []

    def tearDown(self):
        for notificacion_id in self.creadas:
            escribe("DELETE FROM notifications WHERE id = %s", (notificacion_id,))

    def _crea(self, **cambios):
        datos = {"user_id": self.dueno, "type": "RUN_FINISHED", "title": "  Terminó  ",
                 "body": "La corrida terminó.", "payload": {"run_id": 9}}
        datos.update(cambios)
        notificacion_id, error = notificaciones.crear_notificacion(datos, contexto=self.servicio)
        self.assertIsNone(error, error)
        self.creadas.append(notificacion_id)
        return notificacion_id

    def test_crear_guarda_y_audita(self):
        notificacion_id = self._crea()
        fila = query("SELECT title, payload, read_at FROM notifications WHERE id = %s",
                     (notificacion_id,), one=True)
        self.assertEqual(fila["title"], "Terminó")
        self.assertEqual(fila["payload"], {"run_id": 9})
        self.assertIsNone(fila["read_at"])
        bitacora = query("""SELECT action FROM audit_log WHERE entity_type = 'notifications'
                            AND entity_id = %s""", (str(notificacion_id),))
        self.assertEqual([b["action"] for b in bitacora], ["CREATE"])

    def test_acepta_scenario_approved(self):
        self._crea(type="SCENARIO_APPROVED")

    def test_destinatario_inexistente(self):
        notificacion_id, error = notificaciones.crear_notificacion(
            {"user_id": 99999999, "type": "SYSTEM", "title": "x"}, contexto=self.servicio)
        self.assertIsNone(notificacion_id)
        self.assertIn("No existe", error)

    def test_listar_solo_las_propias_con_no_leidas(self):
        mia = self._crea()
        self._crea(user_id=self.otro)
        filas, no_leidas = notificaciones.listar_notificaciones(self.dueno)
        ids = [f["id"] for f in filas]
        self.assertIn(mia, ids)
        self.assertTrue(all(f["user_id"] == self.dueno for f in filas))
        self.assertGreaterEqual(no_leidas, 1)

    def test_marcar_leida_una_vez(self):
        notificacion_id = self._crea()
        contexto = Contexto(self.dueno, "127.0.0.1", "pytest")
        fila, error = notificaciones.marcar_leida(notificacion_id, self.dueno, contexto=contexto)
        self.assertIsNone(error)
        self.assertIsNotNone(fila["read_at"])
        otra_vez, error = notificaciones.marcar_leida(notificacion_id, self.dueno, contexto=contexto)
        self.assertEqual(otra_vez["read_at"], fila["read_at"])
        cambios = query("""SELECT count(*) AS n FROM audit_log WHERE entity_type = 'notifications'
                           AND entity_id = %s AND action = 'UPDATE'""",
                        (str(notificacion_id),), one=True)["n"]
        self.assertEqual(cambios, 1)
        filas, _ = notificaciones.listar_notificaciones(self.dueno, solo_no_leidas=True)
        self.assertNotIn(notificacion_id, [f["id"] for f in filas])

    def test_la_de_otra_persona_no_existe(self):
        notificacion_id = self._crea(user_id=self.otro)
        fila, error = notificaciones.marcar_leida(
            notificacion_id, self.dueno, contexto=Contexto(self.dueno, "127.0.0.1", "pytest"))
        self.assertIsNone(fila)
        self.assertIn("No existe", error)
