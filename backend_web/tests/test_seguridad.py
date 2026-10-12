"""
Seguridad, del lado de backend_web:

  - Sin JWT_SECRET_KEY / DATABASE_URL (o con los valores de ejemplo) no se
    firma ni se conecta nada. Y un error de conexion de PostgreSQL en
    espanol (cp1252) llega como OperationalError legible, no como
    UnicodeDecodeError.
  - Cinco contrasenas equivocadas seguidas bloquean la cuenta 15 minutos.
  - El token lleva `sub` como cadena (RFC 7519).

Ejecutar:
    python -m unittest backend_web.tests.test_seguridad -v
"""
import os
import secrets
import unittest
from unittest.mock import patch

import psycopg2

from backend_web.tests.base import escribe, requiere_base
from backend_web import auth, db
from backend_web.db import get_conn, query


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

    def test_error_de_conexion_en_cp1252_llega_legible(self):
        """Lo que manda PostgreSQL de Windows en espanol: el mensaje en cp1252,
        que psycopg2 intenta leer como UTF-8."""
        crudo = ('connection to server at "localhost" (::1), port 5432 failed: '
                 'FATAL:  la autentificación password falló para el usuario '
                 '«epidemia_app»\n').encode("cp1252")
        posicion = crudo.index(b"\xf3")
        falla = UnicodeDecodeError("utf-8", crudo, posicion, posicion + 1,
                                   "invalid continuation byte")
        with patch.object(db, "DATABASE_URL", "postgresql://u:p@localhost/x"), \
                patch.object(db.psycopg2, "connect", side_effect=falla):
            with self.assertRaises(psycopg2.OperationalError) as ctx:
                with get_conn():
                    pass
        mensaje = str(ctx.exception)
        self.assertIn("la autentificación password falló", mensaje)
        self.assertIn("«epidemia_app»", mensaje)
        self.assertIs(ctx.exception.__cause__, falla)

    @requiere_base
    def test_contrasena_equivocada_da_operational_error_de_verdad(self):
        """Contra el PostgreSQL real, sea cual sea su idioma: antes, en uno de
        Windows en espanol, salia UnicodeDecodeError."""
        esquema, resto = db.DATABASE_URL.split("://", 1)
        credenciales, servidor = resto.rsplit("@", 1)
        usuario = credenciales.split(":", 1)[0]
        mala = f"{esquema}://{usuario}:contrasena-equivocada-de-prueba@{servidor}"
        with patch.object(db, "DATABASE_URL", mala):
            with self.assertRaises(psycopg2.OperationalError):
                with get_conn():
                    pass


USUARIO_BLOQUEO = "prueba.bloqueo"


@requiere_base
class BloqueoPorIntentosTests(unittest.TestCase):
    """Cuenta propia, creada y borrada en cada prueba. attempt_login no escribe
    en audit_log (eso lo hace la ruta), asi que se puede borrar sin dejar
    huella. La contrasena se genera al vuelo y no se guarda."""

    def setUp(self):
        self._borra()
        self.password = secrets.token_urlsafe(16)
        escribe(
            """INSERT INTO users (username, email, password_hash, full_name, is_active)
               VALUES (%s, %s, %s, 'Bloqueo de prueba', TRUE)""",
            (USUARIO_BLOQUEO, f"{USUARIO_BLOQUEO}@example.com",
             auth.hash_password(self.password)))

    def tearDown(self):
        self._borra()

    def _borra(self):
        escribe("DELETE FROM users WHERE username = %s", (USUARIO_BLOQUEO,))

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
