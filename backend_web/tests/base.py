"""
Preparacion comun de las pruebas que usan PostgreSQL.

La importan las pruebas de backend_web y, a traves de
frontend_web/tests/base.py, las de rutas. No contiene pruebas: ningun metodo
se llama test_*, asi que unittest no corre nada de este modulo por si mismo.

Fija JWT_SECRET_KEY al importarse. Tiene que pasar antes de importar
frontend_web.app o backend_web.auth, que se niegan a firmar sin secreto.
"""
import functools
import os
import unittest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend_web import queries, simulaciones  # noqa: E402
from backend_web.auth import create_token  # noqa: E402
from backend_web.contexto import Contexto  # noqa: E402
from backend_web.db import get_conn, query  # noqa: E402

# Escenario de la semilla de demostracion (datos/postgres/semillas/
# demo_datos_nl.sql) que ya viene aprobado: sobre su version se encolan las
# corridas de prueba.
ESCENARIO_DEMO = "Ola Influenza ZMM - otono 2026"
SIN_BASE = ("Requiere la base de pruebas; se crea con "
            "python datos/scripts/prepara_base_pruebas.py")


@functools.lru_cache(maxsize=None)
def tiene_base():
    """True si hay una base a la cual conectarse. Se pregunta una vez por proceso."""
    try:
        query("SELECT 1", one=True)
        return True
    except Exception:
        return False


def requiere_base(clase):
    """Decorador de clase: la salta si no hay PostgreSQL. Lo heredan sus subclases."""
    return unittest.skipUnless(tiene_base(), SIN_BASE)(clase)


def escribe(sql, params=()):
    """Ejecuta y confirma. Para preparar y limpiar datos de prueba."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


def contexto_de_prueba(user_id):
    """El Contexto con que las pruebas llaman a la capa de datos: el mismo que
    armaria una peticion local del cliente de pruebas."""
    return Contexto(user_id, "127.0.0.1", "pytest")


def id_de_usuario(username):
    return query("SELECT id FROM users WHERE username = %s", (username,), one=True)["id"]


def usuario_con_rol(codigo):
    """Id de algun usuario con ese rol, o None si no hay ninguno."""
    fila = query(
        """SELECT u.id FROM users u
           JOIN user_roles ur ON ur.user_id = u.id
           JOIN roles r ON r.id = ur.role_id
           WHERE r.code = %s LIMIT 1""", (codigo,), one=True)
    return fila["id"] if fila else None


def token_de(username):
    """Token firmado para un usuario real de la base, con sus roles de hoy."""
    u = query("SELECT id, username, full_name FROM users WHERE username = %s",
              (username,), one=True)
    roles = [r["code"] for r in query(
        """SELECT r.code FROM roles r JOIN user_roles ur ON ur.role_id = r.id
           WHERE ur.user_id = %s""", (u["id"],))]
    return create_token({"id": u["id"], "username": u["username"],
                         "full_name": u["full_name"], "roles": roles})


def version_demo_aprobada():
    """Id de la version aprobada del escenario de demostracion, o None."""
    fila = query(
        """SELECT sv.id FROM scenario_versions sv
           JOIN scenarios s ON s.id = sv.scenario_id
           WHERE s.name = %s AND sv.status = 'aprobado'""",
        (ESCENARIO_DEMO,), one=True)
    return fila["id"] if fila else None


@requiere_base
class ConCorridasDePrueba(unittest.TestCase):
    """Encola corridas de alex.cavazos sobre la version aprobada de la demo y
    borra sus lotes al terminar cada prueba.

    Borrar el lote arrastra en cascada a sus corridas y resultados. audit_log
    no se limpia: es de solo insercion (fn_solo_insercion), y lo que quede ahi
    son eventos reales de que la prueba uso la app.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.version_id = version_demo_aprobada()
        if cls.version_id is None:
            raise unittest.SkipTest(
                "Falta el escenario de demostracion aprobado; carga "
                "datos/postgres/semillas/demo_datos_nl.sql.")
        cls.user_id = id_de_usuario("alex.cavazos")

    def setUp(self):
        super().setUp()
        self._batches_creados = []

    def tearDown(self):
        for batch_id in self._batches_creados:
            escribe("DELETE FROM simulation_batches WHERE id = %s", (batch_id,))
        super().tearDown()

    def _encola(self, seed):
        run_id, batch_id, error = queries.crear_corrida(
            self.version_id, seed, self.user_id, simulaciones.ENGINE_VERSION)
        self.assertIsNone(error, error)
        self._batches_creados.append(batch_id)
        return run_id
