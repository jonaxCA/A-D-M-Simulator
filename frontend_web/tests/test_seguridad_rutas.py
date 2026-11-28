"""
Seguridad, del lado de las rutas:

  - `/login?next=` no redirige fuera del sitio.
  - `run.py` no arranca con el depurador abierto a la red.
  - Desactivar una cuenta o quitarle un rol surte efecto en la siguiente
    peticion, aunque su token siga vigente.
  - El alta de una enfermedad solo fija parametros si quien la da de alta
    puede editarlos (EPIDEMIOLOGO / ADMINISTRADOR).
  - Sin JWT_SECRET_KEY la app no arranca.

Ejecutar:
    python -m unittest frontend_web.tests.test_seguridad_rutas -v
"""
import os
import secrets
import unittest
from unittest.mock import patch

from frontend_web.tests.base import AppTestCase
from backend_web.auth import create_token, decode_token, hash_password
from backend_web.db import query
from backend_web.tests.base import escribe, requiere_base, token_de
from frontend_web.app import create_app
from frontend_web.app.permisos import COOKIE_NAME
from frontend_web.app.routes import destino_seguro
from frontend_web.run import opciones_arranque


# ---------------------------------------------------------------------------
# 1. Redireccion abierta
# ---------------------------------------------------------------------------
class DestinoSeguroTests(unittest.TestCase):
    def test_acepta_rutas_locales(self):
        for ruta in ("/dashboard", "/escenarios/3?version=2", "/simulaciones/corridas/7"):
            self.assertEqual(destino_seguro(ruta), ruta)

    def test_rechaza_otros_dominios(self):
        for malo in ("https://sitio-falso.example/robo", "http://x.example",
                     "//sitio-falso.example", "/\\sitio-falso.example",
                     "\\\\sitio-falso.example", "javascript:alert(1)",
                     "sitio-falso.example", "/ok\\..\\otro", "/\t/sitio-falso.example",
                     "", None):
            self.assertIsNone(destino_seguro(malo), repr(malo))


class LoginRedireccionTests(AppTestCase):
    """El POST de login con un `next` hostil termina en el dashboard."""

    def setUp(self):
        super().setUp()
        # Sin auth ni captcha reales (D36): lo que se prueba es a donde manda el redirect, no
        # la autenticacion.
        for objetivo, valor in (
            ("frontend_web.app.sesion_servicios.iniciar",
             {"access_token": "a", "refresh_token": "r",
              "usuario": {"id": 5, "username": "prueba", "full_name": "Prueba",
                          "roles": ["ANALISTA"]}}),
            ("frontend_web.app.sesion_servicios.captcha", None),
        ):
            simulado = patch(objetivo, return_value=valor)
            simulado.start()
            self.addCleanup(simulado.stop)

    def _destino(self, siguiente):
        with self.app.test_client() as client:
            resp = client.post("/login", query_string={"next": siguiente},
                               data={"usuario": "prueba", "password": "x"})
        self.assertEqual(resp.status_code, 302)
        return resp.headers["Location"]

    def test_next_externo_va_al_dashboard(self):
        for malo in ("https://sitio-malicioso.example/robo", "//sitio-malicioso.example",
                     "/\\sitio-malicioso.example"):
            self.assertEqual(self._destino(malo), "/dashboard", malo)

    def test_next_local_se_respeta(self):
        self.assertEqual(self._destino("/escenarios"), "/escenarios")


# ---------------------------------------------------------------------------
# 2 y 5. Arranque
# ---------------------------------------------------------------------------
class ArranqueTests(unittest.TestCase):
    def test_por_omision_solo_local_y_sin_depurador(self):
        self.assertEqual(opciones_arranque({}), ("127.0.0.1", 5000, False))

    def test_depurador_en_local_si(self):
        self.assertEqual(opciones_arranque({"FLASK_DEBUG": "1"}), ("127.0.0.1", 5000, True))

    def test_red_local_sin_depurador_si(self):
        self.assertEqual(opciones_arranque({"EPIDEMIA_HOST": "0.0.0.0",
                                            "EPIDEMIA_PORT": "5001"}),
                         ("0.0.0.0", 5001, False))

    def test_depurador_abierto_a_la_red_no(self):
        with self.assertRaises(SystemExit):
            opciones_arranque({"FLASK_DEBUG": "1", "EPIDEMIA_HOST": "0.0.0.0"})

    def test_puerto_invalido(self):
        with self.assertRaises(SystemExit):
            opciones_arranque({"EPIDEMIA_PORT": "cinco mil"})

    def test_sin_secreto_la_app_no_arranca(self):
        for valor in (None, "", "dev-secret-cambiar-en-despliegue",
                      "CAMBIAR_POR_UNA_CADENA_LARGA_Y_ALEATORIA"):
            entorno = {k: v for k, v in os.environ.items() if k != "JWT_SECRET_KEY"}
            if valor is not None:
                entorno["JWT_SECRET_KEY"] = valor
            with patch.dict(os.environ, entorno, clear=True):
                with self.assertRaises(RuntimeError, msg=repr(valor)):
                    create_app()


# ---------------------------------------------------------------------------
# 3. Revocacion
# ---------------------------------------------------------------------------
USUARIO_REVOCACION = "prueba.revocacion"


@requiere_base
class RevocacionTests(AppTestCase):
    """D36: la sesion la llevan auth y sesiones. La cuenta entra con su login real, y desactivarla
    (usuarios) o cambiarle el rol (roles) cierra sus sesiones: la web deja de aceptarla.

    Cuenta de prueba propia: activa con EPIDEMIOLOGO durante la prueba e inactiva al terminar.
    No se borra porque los intentos denegados la dejan en audit_log, que es de solo insercion.
    Su contrasena es aleatoria y no se guarda en ningun lado."""

    sesion_real = True

    def setUp(self):
        super().setUp()
        self.password = secrets.token_urlsafe(24)
        escribe(
            """INSERT INTO users (username, email, password_hash, full_name, is_active)
               VALUES (%s, %s, %s, 'Revocacion de prueba', TRUE)
               ON CONFLICT (username) DO UPDATE SET is_active = TRUE, password_hash = EXCLUDED.password_hash""",
            (USUARIO_REVOCACION, f"{USUARIO_REVOCACION}@example.com", hash_password(self.password)))
        self.user_id = query("SELECT id FROM users WHERE username = %s",
                             (USUARIO_REVOCACION,), one=True)["id"]
        self._pon_rol("EPIDEMIOLOGO")
        self.client = self.app.test_client()
        self._login(self.client, USUARIO_REVOCACION, self.password)

    def tearDown(self):
        escribe("UPDATE users SET is_active = FALSE WHERE id = %s", (self.user_id,))
        self._pon_rol("EPIDEMIOLOGO")

    def _pon_rol(self, codigo):
        escribe("DELETE FROM user_roles WHERE user_id = %s", (self.user_id,))
        escribe("""INSERT INTO user_roles (user_id, role_id)
                    SELECT %s, id FROM roles WHERE code = %s""", (self.user_id, codigo))

    def _como_admin(self, servicio, metodo, ruta, cuerpo=None):
        admin = query("""SELECT u.username FROM users u JOIN user_roles ur ON ur.user_id = u.id
                         JOIN roles r ON r.id = ur.role_id
                         WHERE r.code = 'ADMINISTRADOR' AND u.is_active LIMIT 1""", one=True)
        token = self.puente._con_sesion(token_de(admin["username"]), forzar=True)
        return self.puente(servicio, metodo, ruta, token=token, cuerpo=cuerpo)

    def _get(self, ruta):
        return self.client.get(ruta, follow_redirects=False)

    def test_con_la_cuenta_vigente_entra(self):
        self.assertEqual(self._get("/revisiones").status_code, 200)

    def test_cuenta_desactivada_ya_no_entra_con_su_token(self):
        self._como_admin("usuarios", "POST", "/api/v1/users/%d/deactivate" % self.user_id)
        resp = self._get("/revisiones")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_cambiar_el_rol_cierra_la_sesion(self):
        analista = query("SELECT id FROM roles WHERE code = 'ANALISTA'", one=True)["id"]
        self._como_admin("roles", "PUT", "/api/v1/roles/assignments/%d" % self.user_id,
                         {"role_id": analista})
        resp = self._get("/revisiones")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_token_sin_sesion_no_entra(self):
        fantasma = create_token({"id": 987654321, "username": "nadie",
                                 "full_name": "Nadie", "roles": ["ADMINISTRADOR"]})
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, fantasma)
            resp = client.get("/usuarios", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_sub_viaja_como_cadena_pero_la_app_lo_recibe_entero(self):
        """RFC 7519 pide `sub` como cadena (PyJWT >= 2.10 rechaza un entero);
        la app lo compara con ids de la base, asi que lo recibe como int."""
        from frontend_web.app.permisos import get_current_user
        token = self.client.get_cookie(COOKIE_NAME).value
        self.assertEqual(decode_token(token)["sub"], str(self.user_id))
        with self.app.test_request_context(headers={"Cookie": f"{COOKIE_NAME}={token}"}):
            self.assertEqual(get_current_user()["sub"], self.user_id)


# ---------------------------------------------------------------------------
# 4. Alta de enfermedad
# ---------------------------------------------------------------------------
CODIGO_ANALISTA = "ZZZ_ALTA_ANALISTA"
CODIGO_EPIDEMIOLOGO = "ZZZ_ALTA_EPIDEMIOLOGO"


@requiere_base
class AltaEnfermedadTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self._borra()

    def tearDown(self):
        self._borra()

    def _borra(self):
        escribe("DELETE FROM diseases WHERE code IN (%s, %s)",
                 (CODIGO_ANALISTA, CODIGO_EPIDEMIOLOGO))

    def _alta(self, usuario, codigo):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, token_de(usuario))
            resp = client.post("/enfermedades/nueva", data={
                "code": codigo, "name": f"Prueba {codigo}",
                "p_r0_valor": "2.5", "p_r0_fuente": "Fuente de prueba"})
        self.assertEqual(resp.status_code, 302, resp.data[:500])
        return query("SELECT default_params FROM diseases WHERE code = %s",
                     (codigo,), one=True)["default_params"]

    def test_el_analista_no_da_de_alta(self):
        # D1: catalogs.create es de EPIDEMIOLOGO y ADMINISTRADOR.
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, token_de("alex.cavazos"))
            resp = client.post("/enfermedades/nueva", data={
                "code": CODIGO_ANALISTA, "name": f"Prueba {CODIGO_ANALISTA}"})
        self.assertEqual(resp.status_code, 403)
        self.assertIsNone(query("SELECT id FROM diseases WHERE code = %s", (CODIGO_ANALISTA,),
                                one=True))

    def test_epidemiologo_si_fija_parametros_en_el_alta(self):
        params = self._alta("diana.flores", CODIGO_EPIDEMIOLOGO)
        self.assertEqual(params["r0"]["valor"], 2.5)
        self.assertEqual(params["r0"]["fuente"], "Fuente de prueba")

    def test_el_formulario_es_de_quien_da_de_alta_y_trae_los_parametros(self):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, token_de("alex.cavazos"))
            self.assertEqual(client.get("/enfermedades/nueva").status_code, 403)
            client.set_cookie(COOKIE_NAME, token_de("diana.flores"))
            epidemiologo = client.get("/enfermedades/nueva").data.decode("utf-8")
        self.assertIn('name="p_r0_valor"', epidemiologo)


if __name__ == "__main__":
    unittest.main()
