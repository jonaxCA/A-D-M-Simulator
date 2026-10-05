"""
Preparacion comun de las pruebas de rutas (Flask test client).

Se apoya en backend_web/tests/base.py, que fija JWT_SECRET_KEY antes de que
aqui se importe la app. No contiene pruebas: ningun metodo se llama test_*.
"""
import secrets
import time
import unittest
from unittest.mock import patch

# Primero: fija JWT_SECRET_KEY antes de que db.py cargue el .env.
from backend_web.tests.base import (escribe, id_de_usuario, requiere_base,
                                    version_demo_aprobada)
from backend_web.auth import create_token, hash_password
from backend_web.db import query
from frontend_web.app import create_app

# Cuenta CAPTURISTA de prueba. Activa, porque permisos.get_current_user
# rechaza cuentas inactivas aunque el token sea valido, y con una contrasena
# al azar que no se guarda en ningun lado: solo se entra con un token firmado.
# Se queda en la base para que los PERMISSION_DENIED que genera sigan
# atribuidos a alguien.
CAPTURISTA_PRUEBA = "prueba.capturista"


def capturista_de_prueba():
    """Id de la cuenta CAPTURISTA de prueba; la crea o la reactiva."""
    escribe(
        """INSERT INTO users (username, email, password_hash, full_name, is_active)
           VALUES (%s, %s, %s, 'Capturista de prueba', TRUE)
           ON CONFLICT (username) DO UPDATE SET is_active = TRUE""",
        (CAPTURISTA_PRUEBA, f"{CAPTURISTA_PRUEBA}@example.com",
         hash_password(secrets.token_urlsafe(24))))
    escribe(
        """INSERT INTO user_roles (user_id, role_id)
           SELECT u.id, r.id FROM users u, roles r
           WHERE u.username = %s AND r.code = 'CAPTURISTA'
           ON CONFLICT DO NOTHING""", (CAPTURISTA_PRUEBA,))
    return id_de_usuario(CAPTURISTA_PRUEBA)


class AppTestCase(unittest.TestCase):
    """La app se crea una vez por clase."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = create_app()
        cls.app.testing = True

    def _login(self, client, usuario, password):
        resp = client.post("/login", data={"usuario": usuario, "password": password},
                           follow_redirects=False)
        self.assertEqual(resp.status_code, 302, f"login de {usuario} fallo: {resp.data}")


class ConUsuarioSimulado(AppTestCase):
    """Para pruebas con las consultas simuladas: el token es de un usuario
    inventado (id 999), asi que la revalidacion contra `users` tambien se
    simula. Devuelve el usuario del token tal cual, con `sub` como entero,
    igual que backend_web.auth.usuario_vigente con una cuenta activa."""

    def setUp(self):
        super().setUp()
        simulado = patch("frontend_web.app.permisos.usuario_vigente",
                         side_effect=lambda u: {**u, "sub": int(u["sub"])})
        simulado.start()
        self.addCleanup(simulado.stop)

    def _token(self, rol="ANALISTA"):
        return create_token({
            "id": 999,
            "username": "prueba",
            "full_name": "Usuario Prueba",
            "roles": [rol],
        })


@requiere_base
class RutasConCorridas(AppTestCase):
    """Rutas que lanzan corridas reales sobre la version aprobada de la demo.
    Los lotes que las pruebas registran en `_batches_creados` se borran al
    terminar cada una (en cascada, con sus corridas y resultados)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.version_id = version_demo_aprobada()
        if cls.version_id is None:
            raise unittest.SkipTest("Falta el escenario de demostracion aprobado.")

    def setUp(self):
        super().setUp()
        self._batches_creados = []

    def tearDown(self):
        for batch_id in self._batches_creados:
            escribe("DELETE FROM simulation_batches WHERE id = %s", (batch_id,))
        super().tearDown()

    def _run_id_del_redirect(self, resp):
        loc = resp.headers["Location"]
        return int(loc.rstrip("/").split("/")[-1])

    def _batch_del_run(self, run_id):
        fila = query("SELECT batch_id FROM simulation_runs WHERE id = %s", (run_id,), one=True)
        return fila["batch_id"]

    def _espera_terminal(self, client, run_id, intentos=40):
        for _ in range(intentos):
            datos = client.get(f"/simulaciones/corridas/{run_id}/estado").get_json()
            if datos["terminal"]:
                return datos
            time.sleep(0.25)
        self.fail(f"La corrida {run_id} no termino a tiempo para la prueba.")
