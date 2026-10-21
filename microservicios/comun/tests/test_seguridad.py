import sys
import time
from pathlib import Path
from uuid import uuid4

import jwt
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.seguridad import identificador_sesion, token_servicio as emitir_servicio, verificar_token

AJUSTES = {
    "JWT_SECRET_KEY": "pruebas-unitarias-no-usar-en-produccion",
    "JWT_ISSUER": "epidemia-auth",
    "JWT_AUDIENCE": "epidemia-api",
    "JWT_AUDIENCE_INTERNA": "epidemia-interno",
}

class RedisFalso:
    def __init__(self, llaves=(), caido=False):
        self.llaves = set(llaves)
        self.caido = caido
    def exists(self, clave):
        if self.caido: raise ConnectionError("Redis apagado")
        return clave in self.llaves
    def ping(self):
        if self.caido: raise ConnectionError("Redis apagado")
        return True


def token(**cambios):
    ahora = int(time.time())
    datos = {"iss": "epidemia-auth", "aud": "epidemia-api", "sub": "7", "roles": ["ADMINISTRADOR"],
             "sid": "sesion-uno", "jti": str(uuid4()), "iat": ahora, "nbf": ahora - 1, "exp": ahora + 1200}
    datos.update(cambios)
    return jwt.encode(datos, AJUSTES["JWT_SECRET_KEY"], algorithm="HS256")


def test_token_valido():
    salida = verificar_token(token(), AJUSTES, RedisFalso(["session:" + identificador_sesion("sesion-uno")]), ["ADMINISTRADOR"])
    assert salida["sub"] == "7"


def test_rol_insuficiente():
    with pytest.raises(ErrorAPI) as e:
        verificar_token(token(), AJUSTES, RedisFalso(["session:" + identificador_sesion("sesion-uno")]), ["EPIDEMIOLOGO"])
    assert e.value.estado == 403


def test_sesion_revocada():
    with pytest.raises(ErrorAPI) as e:
        verificar_token(token(), AJUSTES, RedisFalso(), ["ADMINISTRADOR"])
    assert e.value.codigo == "TOKEN_REVOCADO"


def test_redis_caido_falla_cerrado():
    with pytest.raises(ErrorAPI) as e:
        verificar_token(token(), AJUSTES, RedisFalso(caido=True))
    assert e.value.estado == 503


def test_token_expirado():
    with pytest.raises(ErrorAPI) as e:
        verificar_token(token(exp=int(time.time()) - 5), AJUSTES, RedisFalso())
    assert e.value.codigo == "TOKEN_EXPIRADO"


def test_token_con_audiencia_incorrecta():
    with pytest.raises(ErrorAPI) as e:
        verificar_token(token(aud="otra-app"), AJUSTES, RedisFalso())
    assert e.value.codigo == "TOKEN_INVALIDO"


def test_token_con_firma_incorrecta():
    otro = jwt.encode({"sub": "7"}, "otra-clave", algorithm="HS256")
    with pytest.raises(ErrorAPI) as e:
        verificar_token(otro, AJUSTES, RedisFalso())
    assert e.value.estado == 401


def token_servicio(**cambios):
    ahora = int(time.time())
    datos = {"iss": "epidemia-auth", "aud": "epidemia-interno", "sub": "usuarios",
             "jti": str(uuid4()), "iat": ahora, "nbf": ahora - 1, "exp": ahora + 60}
    datos.update(cambios)
    return jwt.encode(datos, AJUSTES["JWT_SECRET_KEY"], algorithm="HS256")


def test_token_de_servicio_valido_en_ruta_interna():
    salida = verificar_token(token_servicio(), AJUSTES, RedisFalso(), interno=True)
    assert salida["sub"] == "usuarios"


def test_token_de_servicio_rechazado_en_ruta_de_personas():
    with pytest.raises(ErrorAPI) as e:
        verificar_token(token_servicio(), AJUSTES, RedisFalso(["session:" + identificador_sesion("sesion-uno")]))
    assert e.value.estado == 401 and e.value.codigo == "TOKEN_INVALIDO"


def test_token_de_persona_rechazado_en_ruta_solo_servicios():
    with pytest.raises(ErrorAPI) as e:
        verificar_token(token(), AJUSTES, RedisFalso(["session:" + identificador_sesion("sesion-uno")]),
                        interno=True)
    assert e.value.estado == 401 and e.value.codigo == "TOKEN_INVALIDO"


def test_alg_none_rechazado():
    falso = jwt.encode({"sub": "7"}, key="", algorithm="none")
    with pytest.raises(ErrorAPI) as e:
        verificar_token(falso, AJUSTES, RedisFalso())
    assert e.value.estado == 401


def test_token_servicio_emitido_vale_en_ruta_interna():
    salida = verificar_token(emitir_servicio(AJUSTES, "simulador"), AJUSTES, RedisFalso(), interno=True)
    assert salida["sub"] == "simulador"
    assert salida["exp"] - salida["iat"] == 60


def test_token_servicio_emitido_no_vale_en_ruta_de_personas():
    with pytest.raises(ErrorAPI) as e:
        verificar_token(emitir_servicio(AJUSTES, "simulador"), AJUSTES, RedisFalso())
    assert e.value.codigo == "TOKEN_INVALIDO"


def test_token_servicio_emitido_vence():
    with pytest.raises(ErrorAPI) as e:
        verificar_token(emitir_servicio(AJUSTES, "simulador", duracion=-5), AJUSTES, RedisFalso(),
                        interno=True)
    assert e.value.codigo == "TOKEN_EXPIRADO"
