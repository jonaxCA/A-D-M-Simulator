"""
Arreglos de la auditoria del segundo avance, del lado de las rutas:

  1. `/login?next=` ya no redirige fuera del sitio.
  2. `run.py` no arranca con el depurador abierto a la red.
  3. Desactivar una cuenta o quitarle un rol surte efecto en la siguiente
     peticion, aunque su token siga vigente.
  4. El alta de una enfermedad solo fija parametros si quien la da de alta
     puede editarlos (EPIDEMIOLOGO / ADMINISTRADOR).
  5. Sin JWT_SECRET_KEY la app no arranca.
  8. Una intervencion invalida ya no borra el historial de versiones.

Ejecutar:
    python -m unittest frontend_web.tests.test_seguridad_rutas -v
"""
import os
import re
import secrets
import unittest
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend_web import queries
from backend_web.auth import create_token, decode_token, hash_password
from backend_web.db import get_conn, query
from frontend_web.app import create_app
from frontend_web.app.permisos import COOKIE_NAME
from frontend_web.app.routes import destino_seguro
from frontend_web.run import opciones_arranque


def _tiene_base():
    try:
        query("SELECT 1", one=True)
        return True
    except Exception:
        return False


def _escribe(sql, params=()):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


def _token_de(username):
    """Token firmado para un usuario real de la base, con sus roles de hoy."""
    u = query("SELECT id, username, full_name FROM users WHERE username = %s",
              (username,), one=True)
    roles = [r["code"] for r in query(
        """SELECT r.code FROM roles r JOIN user_roles ur ON ur.role_id = r.id
           WHERE ur.user_id = %s""", (u["id"],))]
    return create_token({"id": u["id"], "username": u["username"],
                         "full_name": u["full_name"], "roles": roles})


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


class LoginRedireccionTests(unittest.TestCase):
    """El POST de login con un `next` hostil termina en el dashboard."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True

    def setUp(self):
        # Sin credenciales reales ni filas de bitacora: lo que se prueba es a
        # donde manda el redirect, no la autenticacion.
        for objetivo, valor in (
            ("frontend_web.app.routes.attempt_login",
             ({"id": 5, "username": "prueba", "full_name": "Prueba",
               "roles": ["ANALISTA"]}, None)),
            ("frontend_web.app.routes.log_audit", None),
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


@unittest.skipUnless(_tiene_base(), "Requiere PostgreSQL en DATABASE_URL.")
class RevocacionTests(unittest.TestCase):
    """Cuenta de prueba propia: activa con EPIDEMIOLOGO durante la prueba e
    inactiva al terminar. No se borra porque los intentos denegados la dejan
    en audit_log, que es de solo insercion. Su contrasena es aleatoria y no se
    guarda en ningun lado."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True

    def setUp(self):
        _escribe(
            """INSERT INTO users (username, email, password_hash, full_name, is_active)
               VALUES (%s, %s, %s, 'Revocacion de prueba', TRUE)
               ON CONFLICT (username) DO UPDATE SET is_active = TRUE""",
            (USUARIO_REVOCACION, f"{USUARIO_REVOCACION}@example.com",
             hash_password(secrets.token_urlsafe(24))))
        self.user_id = query("SELECT id FROM users WHERE username = %s",
                             (USUARIO_REVOCACION,), one=True)["id"]
        self._pon_rol("EPIDEMIOLOGO")
        self.token = _token_de(USUARIO_REVOCACION)

    def tearDown(self):
        _escribe("UPDATE users SET is_active = FALSE WHERE id = %s", (self.user_id,))
        self._pon_rol("EPIDEMIOLOGO")

    def _pon_rol(self, codigo):
        _escribe("DELETE FROM user_roles WHERE user_id = %s", (self.user_id,))
        _escribe("""INSERT INTO user_roles (user_id, role_id)
                    SELECT %s, id FROM roles WHERE code = %s""", (self.user_id, codigo))

    def _get(self, ruta):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self.token)
            return client.get(ruta, follow_redirects=False)

    def test_con_la_cuenta_vigente_entra(self):
        self.assertEqual(self._get("/revisiones").status_code, 200)

    def test_cuenta_desactivada_ya_no_entra_con_su_token(self):
        _escribe("UPDATE users SET is_active = FALSE WHERE id = %s", (self.user_id,))
        resp = self._get("/revisiones")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_rol_retirado_deja_de_valer_aunque_el_token_lo_traiga(self):
        self._pon_rol("ANALISTA")
        self.assertIn("EPIDEMIOLOGO", decode_token(self.token)["roles"])
        resp = self._get("/revisiones")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/dashboard", resp.headers["Location"])

    def test_token_de_una_cuenta_que_no_existe(self):
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
        self.assertEqual(decode_token(self.token)["sub"], str(self.user_id))
        with self.app.test_request_context(
                headers={"Cookie": f"{COOKIE_NAME}={self.token}"}):
            self.assertEqual(get_current_user()["sub"], self.user_id)


# ---------------------------------------------------------------------------
# 4. Alta de enfermedad
# ---------------------------------------------------------------------------
CODIGO_ANALISTA = "ZZZ_ALTA_ANALISTA"
CODIGO_EPIDEMIOLOGO = "ZZZ_ALTA_EPIDEMIOLOGO"


@unittest.skipUnless(_tiene_base(), "Requiere PostgreSQL en DATABASE_URL.")
class AltaEnfermedadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True

    def setUp(self):
        self._borra()

    def tearDown(self):
        self._borra()

    def _borra(self):
        _escribe("DELETE FROM diseases WHERE code IN (%s, %s)",
                 (CODIGO_ANALISTA, CODIGO_EPIDEMIOLOGO))

    def _alta(self, usuario, codigo):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, _token_de(usuario))
            resp = client.post("/enfermedades/nueva", data={
                "code": codigo, "name": f"Prueba {codigo}",
                "p_r0_valor": "2.5", "p_r0_fuente": "Fuente de prueba"})
        self.assertEqual(resp.status_code, 302, resp.data[:500])
        return query("SELECT default_params FROM diseases WHERE code = %s",
                     (codigo,), one=True)["default_params"]

    def test_analista_da_de_alta_pero_sin_parametros(self):
        params = self._alta("alex.cavazos", CODIGO_ANALISTA)
        self.assertNotIn("r0", params or {})

    def test_epidemiologo_si_fija_parametros_en_el_alta(self):
        params = self._alta("diana.flores", CODIGO_EPIDEMIOLOGO)
        self.assertEqual(params["r0"]["valor"], 2.5)
        self.assertEqual(params["r0"]["fuente"], "Fuente de prueba")

    def test_el_formulario_solo_muestra_parametros_a_quien_los_fija(self):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, _token_de("alex.cavazos"))
            analista = client.get("/enfermedades/nueva").data.decode("utf-8")
            client.set_cookie(COOKIE_NAME, _token_de("diana.flores"))
            epidemiologo = client.get("/enfermedades/nueva").data.decode("utf-8")
        self.assertNotIn('name="p_r0_valor"', analista)
        self.assertIn("epidemiólogo", analista)
        self.assertIn('name="p_r0_valor"', epidemiologo)


# ---------------------------------------------------------------------------
# 8. Historial tras una intervencion invalida
# ---------------------------------------------------------------------------
NOMBRE_HISTORIAL = "ZZZ historial tras error de captura"


@unittest.skipUnless(_tiene_base(), "Requiere PostgreSQL en DATABASE_URL.")
class HistorialTrasErrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True

    def setUp(self):
        self._borra()
        regiones = queries.get_regiones_para_escenario()
        enfermedades = queries.get_enfermedades_para_escenario()
        mty = next((r for r in regiones if r["code"] == "19039"), None)
        enfermedad = next((e for e in enfermedades if e["simulable"]), None)
        if not mty or not enfermedad:
            self.skipTest("la base no tiene Monterrey o una enfermedad simulable")
        self.token = _token_de("alex.cavazos")
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self.token)
            resp = client.post("/escenarios/nuevo", data={
                "name": NOMBRE_HISTORIAL, "disease_id": str(enfermedad["id"]),
                "region_id": str(mty["id"]), "population_size": "1000",
                "initial_infected": "5", "horizon_days": "90", "notes": "v1"})
        self.assertEqual(resp.status_code, 302, resp.data[:500])
        self.sid = query("SELECT id FROM scenarios WHERE name = %s",
                         (NOMBRE_HISTORIAL,), one=True)["id"]

    def tearDown(self):
        self._borra()

    def _borra(self):
        _escribe("""DELETE FROM scenario_versions WHERE scenario_id IN
                    (SELECT id FROM scenarios WHERE name = %s)""", (NOMBRE_HISTORIAL,))
        _escribe("DELETE FROM scenarios WHERE name = %s", (NOMBRE_HISTORIAL,))

    def test_el_historial_sigue_ahi_cuando_la_intervencion_es_invalida(self):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self.token)
            antes = client.get(f"/escenarios/{self.sid}").data.decode("utf-8")
            resp = client.post(f"/escenarios/{self.sid}/intervenciones",
                               data={"tipo": "CUBREBOCAS", "start_day": "999"})
        self.assertEqual(resp.status_code, 400)
        despues = resp.data.decode("utf-8")
        patron = r"Historial de versiones \((\d+)\)"
        self.assertEqual(re.search(patron, antes).group(1), "1")
        self.assertEqual(re.search(patron, despues).group(1), "1")


if __name__ == "__main__":
    unittest.main()
