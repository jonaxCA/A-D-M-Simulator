"""
La web abre la sesion en Redis al entrar, la verifica en cada peticion y la
revoca al salir (I3), con el mismo mecanismo de epidemia_comun.sesiones.

Para saber si hay sesion se pide GET /login: con sesion redirige al dashboard,
sin ella muestra el formulario.

Ejecutar:
    python -m unittest frontend_web.tests.test_sesion_redis -v
"""
from unittest.mock import patch

from frontend_web.app.permisos import COOKIE_NAME
from frontend_web.app.sesion_redis import MENSAJE_SIN_REDIS
from frontend_web.tests.base import ConUsuarioSimulado

USUARIO = {"id": 999, "username": "prueba", "full_name": "Usuario Prueba",
           "roles": ["ANALISTA"]}


class SesionRedisTests(ConUsuarioSimulado):
    sesion_real = True

    def setUp(self):
        super().setUp()
        for destino, valor in (("attempt_login", (USUARIO, None)), ("log_audit", None)):
            parche = patch(f"frontend_web.app.routes.{destino}", return_value=valor)
            parche.start()
            self.addCleanup(parche.stop)

    def _entra(self, client):
        resp = client.post("/login", data={"usuario": "prueba", "password": "x"})
        self.assertEqual(resp.status_code, 302)
        return client.get_cookie(COOKIE_NAME).value

    def _hay_sesion(self, client):
        resp = client.get("/login")
        return resp.status_code == 302

    def test_login_abre_sesion_en_redis(self):
        with self.app.test_client() as client:
            self._entra(client)
            self.assertTrue(self._hay_sesion(client))
        self.assertEqual(len([k for k in self.redis.keys() if k.startswith("session:")]), 1)

    def test_logout_revoca_y_la_cookie_vieja_ya_no_sirve(self):
        with self.app.test_client() as client:
            token = self._entra(client)
            client.get("/logout")
            client.set_cookie(COOKIE_NAME, token)
            self.assertFalse(self._hay_sesion(client))

    def test_token_sin_sesion_en_redis_no_entra(self):
        with self.app.test_client() as client:
            token = self._entra(client)
            self.redis.flushall()
            client.set_cookie(COOKIE_NAME, token)
            self.assertFalse(self._hay_sesion(client))

    def test_token_viejo_sin_sid_no_entra(self):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            self.assertFalse(self._hay_sesion(client))

    def test_redis_caido_con_sesion_abierta_sigue_funcionando(self):
        with self.app.test_client() as client:
            self._entra(client)
            self.servidor_redis.connected = False
            self.assertTrue(self._hay_sesion(client))

    def test_redis_caido_no_puede_revocar_pero_el_logout_responde(self):
        with self.app.test_client() as client:
            self._entra(client)
            self.servidor_redis.connected = False
            resp = client.get("/logout")
            self.assertEqual(resp.status_code, 302)

    def test_redis_caido_en_el_login_da_un_mensaje_claro(self):
        self.servidor_redis.connected = False
        with self.app.test_client() as client:
            resp = client.post("/login", data={"usuario": "prueba", "password": "x"})
            self.assertEqual(resp.status_code, 503)
            self.assertIn(MENSAJE_SIN_REDIS, resp.get_data(as_text=True))
            self.assertIsNone(client.get_cookie(COOKIE_NAME))
