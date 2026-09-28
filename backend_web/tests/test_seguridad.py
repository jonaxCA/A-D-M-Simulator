"""
Arreglos de la auditoria del segundo avance, del lado de backend_web:

  5. Sin JWT_SECRET_KEY / DATABASE_URL (o con los valores de ejemplo) no se
     firma ni se conecta nada.
  7. Cinco contrasenas equivocadas seguidas bloquean la cuenta 15 minutos.
  +  El token lleva `sub` como cadena (RFC 7519).

Ejecutar:
    python -m unittest backend_web.tests.test_seguridad -v
"""
import os
import secrets
import unittest
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend_web import auth, db
from backend_web.db import get_conn, query


def _tiene_base():
    try:
        query("SELECT 1", one=True)
        return True
    except Exception:
        return False


class SecretoTests(unittest.TestCase):
    def test_sin_secreto_o_con_el_de_ejemplo_no_firma(self):
        for valor in ("", "   ", "dev-secret-cambiar-en-despliegue",
                      "CAMBIAR_POR_UNA_CADENA_LARGA_Y_ALEATORIA",
                      "pon-aqui-cualquier-cadena-larga-y-aleatoria"):
            with patch.dict(os.environ, {"JWT_SECRET_KEY": valor}):
                with self.assertRaises(RuntimeError, msg=repr(valor)):
                    auth.create_token({"id": 1, "username": "u", "full_name": "U",
                                       "roles": []})

    def test_un_token_firmado_con_otro_secreto_no_vale(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "otro-secreto-cualquiera"}):
            ajeno = auth.create_token({"id": 1, "username": "u", "full_name": "U",
                                       "roles": ["ADMINISTRADOR"]})
        self.assertIsNone(auth.decode_token(ajeno))

    def test_sub_va_como_cadena(self):
        token = auth.create_token({"id": 42, "username": "u", "full_name": "U",
                                   "roles": []})
        self.assertEqual(auth.decode_token(token)["sub"], "42")

    def test_usuario_vigente_rechaza_un_sub_que_no_es_numero(self):
        self.assertIsNone(auth.usuario_vigente({"sub": "admin"}))
        self.assertIsNone(auth.usuario_vigente({}))


class ConexionTests(unittest.TestCase):
    def test_sin_database_url_no_conecta(self):
        with patch.object(db, "DATABASE_URL", ""):
            with self.assertRaisesRegex(RuntimeError, "Falta DATABASE_URL"):
                with get_conn():
                    pass

    def test_con_la_contrasena_de_ejemplo_no_conecta(self):
        ejemplo = "postgresql://epidemia_app:CAMBIAR_CONTRASENA@localhost:5432/x"
        with patch.object(db, "DATABASE_URL", ejemplo):
            with self.assertRaisesRegex(RuntimeError, "valor de ejemplo"):
                with get_conn():
                    pass


USUARIO_BLOQUEO = "prueba.bloqueo"


@unittest.skipUnless(_tiene_base(), "Requiere PostgreSQL en DATABASE_URL.")
class BloqueoPorIntentosTests(unittest.TestCase):
    """Cuenta propia, creada y borrada en cada prueba. attempt_login no escribe
    en audit_log (eso lo hace la ruta), asi que se puede borrar sin dejar
    huella. La contrasena se genera al vuelo y no se guarda."""

    def setUp(self):
        self._borra()
        self.password = secrets.token_urlsafe(16)
        self._escribe(
            """INSERT INTO users (username, email, password_hash, full_name, is_active)
               VALUES (%s, %s, %s, 'Bloqueo de prueba', TRUE)""",
            (USUARIO_BLOQUEO, f"{USUARIO_BLOQUEO}@example.com",
             auth.hash_password(self.password)))

    def tearDown(self):
        self._borra()

    def _escribe(self, sql, params=()):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()

    def _borra(self):
        self._escribe("DELETE FROM users WHERE username = %s", (USUARIO_BLOQUEO,))

    def _intentos(self):
        return query("SELECT failed_attempts FROM users WHERE username = %s",
                     (USUARIO_BLOQUEO,), one=True)["failed_attempts"]

    def _falla(self, veces):
        mensajes = []
        for _ in range(veces):
            usuario, error = auth.attempt_login(USUARIO_BLOQUEO, "no-es-la-contrasena")
            self.assertIsNone(usuario)
            mensajes.append(error)
        return mensajes

    def test_cada_fallo_suma_y_un_acierto_lo_pone_en_cero(self):
        self._falla(2)
        self.assertEqual(self._intentos(), 2)
        usuario, error = auth.attempt_login(USUARIO_BLOQUEO, self.password)
        self.assertIsNone(error)
        self.assertEqual(usuario["username"], USUARIO_BLOQUEO)
        self.assertEqual(self._intentos(), 0)

    def test_al_quinto_fallo_se_bloquea_y_lo_dice(self):
        mensajes = self._falla(auth.INTENTOS_MAXIMOS)
        self.assertTrue(all(m == auth.MENSAJE_CREDENCIALES for m in mensajes[:-1]))
        self.assertIn("bloqueada", mensajes[-1])

    def test_bloqueada_no_entra_ni_con_la_contrasena_correcta(self):
        self._falla(auth.INTENTOS_MAXIMOS)
        usuario, error = auth.attempt_login(USUARIO_BLOQUEO, self.password)
        self.assertIsNone(usuario)
        self.assertIn("Demasiados intentos", error)

    def test_pasado_el_plazo_vuelve_a_entrar(self):
        self._falla(auth.INTENTOS_MAXIMOS)
        # No se puede fechar updated_at hacia atras (el trigger lo pone en
        # now()); se acorta el plazo en su lugar.
        with patch.object(auth, "MINUTOS_BLOQUEO", 0):
            usuario, error = auth.attempt_login(USUARIO_BLOQUEO, self.password)
        self.assertIsNone(error)
        self.assertEqual(self._intentos(), 0)

    def test_una_cuenta_que_no_existe_da_el_mensaje_generico(self):
        usuario, error = auth.attempt_login("nadie.nunca.existio", "x")
        self.assertIsNone(usuario)
        self.assertEqual(error, auth.MENSAJE_CREDENCIALES)


if __name__ == "__main__":
    unittest.main()
