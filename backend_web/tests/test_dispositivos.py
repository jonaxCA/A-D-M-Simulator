"""
Dispositivos de backend_web/dispositivos.py, que escribe el microservicio
dispositivos y lee casos.

Ejecutar:
    python -m unittest backend_web.tests.test_dispositivos -v
"""
import unittest
import uuid

from backend_web import dispositivos
from backend_web.db import query
from backend_web.tests.base import contexto_de_prueba, escribe, id_de_usuario, requiere_base


class ValidaDispositivoTests(unittest.TestCase):
    def test_uno_valido_no_tiene_errores(self):
        self.assertEqual(dispositivos.valida_dispositivo(
            {"device_uid": "3f2a9c1e-77b0-4d2e-a1f5-0c9b8e6d4a21", "platform": "android",
             "model": "Pixel 7", "app_version": "0.1.0", "push_token": None}), [])

    def test_errores_de_cada_campo(self):
        errores = dispositivos.valida_dispositivo(
            {"device_uid": "corto", "platform": "windows", "model": "x" * 81, "app_version": 3,
             "imei": "123"})
        self.assertEqual(len(errores), 5)

    def test_device_uid_obligatorio_y_sin_espacios_dentro(self):
        self.assertEqual(len(dispositivos.valida_dispositivo({})), 1)
        self.assertEqual(len(dispositivos.valida_dispositivo({"device_uid": "con espacio 123"})), 1)


@requiere_base
class DispositivosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dueno = id_de_usuario("karla.trevino")
        cls.otro = id_de_usuario("alex.cavazos")

    def setUp(self):
        self.creados = []

    def tearDown(self):
        for device_id in self.creados:
            escribe("DELETE FROM devices WHERE id = %s", (device_id,))

    def _registra(self, uid=None, user_id=None, **campos):
        datos = {"device_uid": uid or str(uuid.uuid4()), **campos}
        self.assertEqual(dispositivos.valida_dispositivo(datos), [])
        fila, creado, conflicto = dispositivos.registrar_dispositivo(
            user_id or self.dueno, datos, contexto=contexto_de_prueba(user_id or self.dueno))
        if fila and creado:
            self.creados.append(fila["id"])
        return fila, creado, conflicto

    def _bitacora(self, device_id):
        return query("""SELECT action, data_before, data_after FROM audit_log
                        WHERE entity_type = 'devices' AND entity_id = %s ORDER BY id""",
                     (str(device_id),))

    def test_registrar_uno_nuevo(self):
        fila, creado, conflicto = self._registra(model="  Pixel 7 ", push_token="token-de-push")
        self.assertTrue(creado)
        self.assertIsNone(conflicto)
        self.assertEqual((fila["user_id"], fila["platform"], fila["model"]),
                         (self.dueno, "android", "Pixel 7"))
        self.assertTrue(fila["has_push_token"])
        self.assertIsNotNone(fila["last_seen_at"])
        self.assertNotIn("push_token", fila)
        [evento] = self._bitacora(fila["id"])
        self.assertEqual(evento["action"], "CREATE")
        self.assertTrue(evento["data_after"]["has_push_token"])
        self.assertNotIn("token-de-push", str(evento))

    def test_volver_a_registrarse_actualiza_version_y_ultima_conexion(self):
        primero, _, _ = self._registra(app_version="0.1.0", platform="ios")
        segundo, creado, conflicto = self._registra(primero["device_uid"], app_version="0.2.0",
                                                    platform="android")
        self.assertFalse(creado)
        self.assertIsNone(conflicto)
        self.assertEqual(segundo["id"], primero["id"])
        self.assertEqual(segundo["app_version"], "0.2.0")
        # La plataforma solo cuenta al registrarlo.
        self.assertEqual(segundo["platform"], "ios")
        self.assertGreaterEqual(segundo["last_seen_at"], primero["last_seen_at"])
        eventos = self._bitacora(primero["id"])
        self.assertEqual([e["action"] for e in eventos], ["CREATE", "UPDATE"])
        self.assertEqual(eventos[1]["data_before"]["app_version"], "0.1.0")

    def test_el_identificador_de_otra_cuenta_no_se_registra(self):
        fila, _, _ = self._registra()
        ajeno, creado, conflicto = self._registra(fila["device_uid"], user_id=self.otro)
        self.assertIsNone(ajeno)
        self.assertIn("otra cuenta", conflicto)
        self.assertEqual(dispositivos.get_dispositivo(fila["id"])["user_id"], self.dueno)

    def test_revocar_es_para_siempre(self):
        fila, _, _ = self._registra()
        revocado, error = dispositivos.revocar_dispositivo(
            fila["id"], contexto=contexto_de_prueba(self.dueno), user_id=self.dueno)
        self.assertIsNone(error)
        self.assertTrue(revocado["is_revoked"])
        self.assertEqual(self._bitacora(fila["id"])[-1]["data_after"], {"is_revoked": True})
        _, error = dispositivos.revocar_dispositivo(
            fila["id"], contexto=contexto_de_prueba(self.dueno), user_id=self.dueno)
        self.assertIn("ya estaba", error)
        _, _, conflicto = self._registra(fila["device_uid"])
        self.assertIn("revocado", conflicto)

    def test_solo_el_dueno_o_administracion_revocan(self):
        fila, _, _ = self._registra()
        _, error = dispositivos.revocar_dispositivo(
            fila["id"], contexto=contexto_de_prueba(self.otro), user_id=self.otro)
        self.assertTrue(error.startswith("No existe"))
        self.assertFalse(dispositivos.get_dispositivo(fila["id"])["is_revoked"])
        # ADMINISTRADOR pasa user_id None.
        revocado, error = dispositivos.revocar_dispositivo(
            fila["id"], contexto=contexto_de_prueba(self.otro))
        self.assertIsNone(error)
        self.assertTrue(revocado["is_revoked"])
        _, error = dispositivos.revocar_dispositivo(-1, contexto=contexto_de_prueba(self.otro))
        self.assertTrue(error.startswith("No existe"))

    def test_listar_los_de_una_persona_o_todos(self):
        mio, _, _ = self._registra()
        suyo, _, _ = self._registra(user_id=self.otro)
        propios = {d["id"] for d in dispositivos.listar_dispositivos(self.dueno, 200)}
        todos = {d["id"] for d in dispositivos.listar_dispositivos(None, 200)}
        self.assertIn(mio["id"], propios)
        self.assertNotIn(suyo["id"], propios)
        self.assertLessEqual({mio["id"], suyo["id"]}, todos)

    def test_estado_para_captura(self):
        fila, _, _ = self._registra()
        self.assertEqual(dispositivos.estado_para_captura(fila["id"], self.dueno), "ok")
        self.assertEqual(dispositivos.estado_para_captura(fila["id"], self.otro), "ajeno")
        self.assertEqual(dispositivos.estado_para_captura(-1, self.dueno), "ajeno")
        dispositivos.revocar_dispositivo(fila["id"], contexto=contexto_de_prueba(self.dueno))
        self.assertEqual(dispositivos.estado_para_captura(fila["id"], self.dueno), "revocado")


if __name__ == "__main__":
    unittest.main()
