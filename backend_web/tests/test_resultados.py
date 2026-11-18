import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

import fakeredis

from backend_web.tests.base import contexto_de_prueba  # noqa: F401  fija JWT_SECRET_KEY
from backend_web import resultados
from backend_web.auth import create_token, decode_token
from epidemia_comun import llaves, sesiones
from epidemia_comun.ajustes import cargar_ajustes
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.seguridad import verificar_token


class Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def http(codigo):
    return urllib.error.HTTPError("http://r", codigo, "x", {}, io.BytesIO(b""))


class CurvasDeCorridaTests(unittest.TestCase):
    def setUp(self):
        parche = patch.dict("os.environ", {"SERVICIO_RESULTADOS_URL": "http://r:8000/"})
        parche.start()
        self.addCleanup(parche.stop)

    def test_reenvia_el_token_y_la_correlacion(self):
        cuerpo = json.dumps({"serie": [{"dia": 0}]}).encode()
        with patch("urllib.request.urlopen", return_value=Respuesta(cuerpo)) as abre:
            serie = resultados.curvas_de_corrida("tok", 7, "abc")
        peticion = abre.call_args[0][0]
        self.assertEqual(serie, [{"dia": 0}])
        self.assertEqual(peticion.full_url, "http://r:8000/api/v1/runs/7/results")
        self.assertEqual(peticion.get_header("Authorization"), "Bearer tok")
        self.assertEqual(peticion.get_header("X-correlation-id"), "abc")
        self.assertEqual(peticion.get_header("Accept"), "application/json")

    def test_sin_url_no_llama(self):
        with patch.dict("os.environ", {"SERVICIO_RESULTADOS_URL": ""}), \
                patch("urllib.request.urlopen") as abre:
            self.assertIsNone(resultados.curvas_de_corrida("tok", 7))
        abre.assert_not_called()

    def test_caida_o_5xx_devuelve_none(self):
        for error in (OSError("sin red"), http(500), http(503), http(404)):
            with patch("urllib.request.urlopen", side_effect=error):
                self.assertIsNone(resultados.curvas_de_corrida("tok", 7))

    def test_401_y_403_no_caen_a_postgres(self):
        for codigo in (401, 403):
            with patch("urllib.request.urlopen", side_effect=http(codigo)):
                with self.assertRaises(resultados.SinAcceso):
                    resultados.curvas_de_corrida("tok", 7)


class TokenDeLaWebEnLosServiciosTests(unittest.TestCase):
    def setUp(self):
        self.redis = fakeredis.FakeRedis(decode_responses=True)
        patron = patch("epidemia_comun.redis_compartido.cliente", return_value=self.redis)
        patron.start()
        self.addCleanup(patron.stop)
        self.ajustes = cargar_ajustes("resultados", {
            "JWT_SECRET_KEY": os.environ["JWT_SECRET_KEY"],
            "REDIS_URL": "redis://x"})

    def _token(self):
        sesion = sesiones.abrir(5, ["ANALISTA"], 600)
        user = {"id": 5, "username": "u", "full_name": "U", "roles": ["ANALISTA"]}
        return create_token(user, sid=sesion["sid"], jti="j1")

    def test_el_servicio_acepta_el_token_de_la_web(self):
        token = self._token()
        self.assertIsNotNone(decode_token(token))
        payload = verificar_token(token, self.ajustes, self.redis, ("ANALISTA",))
        self.assertEqual(payload["sub"], "5")

    def test_el_servicio_aplica_la_revocacion_y_los_roles(self):
        token = self._token()
        with self.assertRaises(ErrorAPI) as e:
            verificar_token(token, self.ajustes, self.redis, ("ADMINISTRADOR",))
        self.assertEqual(e.exception.estado, 403)
        self.redis.set(llaves.revocado("j1"), 1)
        with self.assertRaises(ErrorAPI):
            verificar_token(token, self.ajustes, self.redis, ())
