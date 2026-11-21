"""La web en contenedor detrás de nginx (F1): su /health, las URL internas de los servicios, la IP
de quien la usa hacia los servicios (D31) y las cookies solo por HTTPS. Sin base ni servicios."""
import os
import unittest
from unittest.mock import patch

# Primero: fija JWT_SECRET_KEY antes de importar la app.
import backend_web.tests.base  # noqa: F401
from backend_web import servicios
from frontend_web.app import create_app, navegador_de_la_peticion

TOKENS = {"access_token": "acceso", "refresh_token": "renovacion"}
FORMULARIO = {"usuario": "ana", "password": "x", "captcha_id": "c", "captcha_respuesta": "r"}


class ContenedorWebTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_health_responde_sin_tocar_la_base_ni_los_servicios(self):
        with patch.object(servicios, "llamar", side_effect=AssertionError("no debe llamar")):
            r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"servicio": "web", "estado": "ok"})

    def test_los_servicios_reciben_la_ip_y_el_navegador_de_la_persona(self):
        with self.app.test_request_context("/", headers={"User-Agent": "Firefox"},
                                           environ_base={"REMOTE_ADDR": "203.0.113.7"}):
            self.assertEqual(navegador_de_la_peticion(),
                             {"User-Agent": "Firefox", "X-Forwarded-For": "203.0.113.7"})
        self.assertEqual(navegador_de_la_peticion(), {})

    def test_cada_peticion_queda_en_el_registro_con_su_correlation_id(self):
        with self.assertLogs("frontend_web.app", "INFO") as registro:
            r = self.client.get("/health", headers={"X-Correlation-ID": "abc-123"})
        self.assertEqual(r.headers["X-Correlation-ID"], "abc-123")
        self.assertTrue(any("GET /health 200" in linea for linea in registro.output), registro.output)

    def test_un_correlation_id_raro_del_navegador_se_cambia_por_uno_nuevo(self):
        r = self.client.get("/health", headers={"X-Correlation-ID": "a b <script>"})
        self.assertRegex(r.headers["X-Correlation-ID"], r"^[0-9a-f-]{36}$")

    def test_los_servicios_reciben_el_correlation_id_de_la_peticion(self):
        with self.app.test_request_context("/", headers={"X-Correlation-ID": "abc-123"}):
            self.app.preprocess_request()
            self.assertEqual(navegador_de_la_peticion()["X-Correlation-ID"], "abc-123")

    def test_url_servicios_lleva_a_la_red_interna_y_la_variable_propia_manda(self):
        with patch.dict(os.environ, {"URL_SERVICIOS": "http://{servicio}:8000"}):
            os.environ.pop("SERVICIO_ESCENARIOS_URL", None)
            self.assertEqual(servicios.url_base("tipos-intervencion"), "http://tipos-intervencion:8000")
            os.environ["SERVICIO_ESCENARIOS_URL"] = "https://ejemplo/escenarios/"
            self.assertEqual(servicios.url_base("escenarios"), "https://ejemplo/escenarios")
        with patch.dict(os.environ, clear=False):
            os.environ.pop("URL_SERVICIOS", None)
            os.environ.pop("SERVICIO_AUTH_URL", None)
            self.assertEqual(servicios.url_base("auth"), "http://localhost:5201")

    def _cookies_del_login(self, base_url):
        with patch("frontend_web.app.sesion_servicios.iniciar", return_value=TOKENS):
            r = self.client.post("/login", data=FORMULARIO, base_url=base_url)
        self.assertEqual(r.status_code, 302)
        return r.headers.getlist("Set-Cookie")

    def test_por_https_las_cookies_de_la_sesion_solo_viajan_cifradas(self):
        cookies = self._cookies_del_login("https://localhost")
        self.assertEqual(len(cookies), 2)
        self.assertTrue(all("Secure" in c for c in cookies), cookies)

    def test_por_http_en_local_las_cookies_siguen_funcionando(self):
        cookies = self._cookies_del_login("http://localhost")
        self.assertTrue(cookies and not any("Secure" in c for c in cookies), cookies)

    def test_detras_de_nginx_la_cookie_de_flask_es_segura(self):
        self.assertFalse(self.app.config["SESSION_COOKIE_SECURE"])
        with patch.dict(os.environ, {"DETRAS_DE_PROXY": "1"}):
            self.assertTrue(create_app().config["SESSION_COOKIE_SECURE"])


if __name__ == "__main__":
    unittest.main()
