import secrets
import time
import uuid

import jwt
from flask import current_app, request

from epidemia_comun import llaves, sesiones
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.redis_compartido import RedisNoDisponible, requerido
from epidemia_comun.validaciones import diccionario
from backend_web import auth
from backend_web.audit import log_audit
from backend_web.contexto import Contexto

ACCESS_TTL = 20 * 60
# Lo mismo que la cookie del monolito; renovar no alarga la sesión.
SESION_TTL = 8 * 60 * 60
CAPTCHA_TTL = 300


def _contexto(user_id):
    return Contexto(user_id, request.remote_addr,
                    (request.headers.get("User-Agent") or "")[:255])


def _texto(datos, campo):
    valor = datos.get(campo)
    if valor is None or isinstance(valor, (dict, list, bool)) or not str(valor).strip():
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Falta el campo %s." % campo)
    return str(valor)


def nuevo_captcha():
    a, b = secrets.randbelow(9) + 1, secrets.randbelow(9) + 1
    captcha_id = secrets.token_urlsafe(16)
    requerido("captcha_crear",
              lambda r: r.set(llaves.captcha(captcha_id), str(a + b), ex=CAPTCHA_TTL))
    return {"captcha_id": captcha_id, "pregunta": "%d + %d" % (a, b),
            "expira": int(time.time()) + CAPTCHA_TTL}


def captcha_valido(captcha_id, respuesta):
    # Se borra al leerlo: cada captcha sirve para un solo intento.
    def operar(r):
        p = r.pipeline()
        p.get(llaves.captcha(captcha_id))
        p.delete(llaves.captcha(captcha_id))
        return p.execute()[0]

    esperada = requerido("captcha_usar", operar)
    return esperada is not None and secrets.compare_digest(esperada, respuesta.strip())


def emitir_access(usuario, sid, ajustes):
    ahora = int(time.time())
    claims = {"iss": ajustes["JWT_ISSUER"], "aud": ajustes["JWT_AUDIENCE"],
              "sub": str(usuario["id"]), "roles": usuario["roles"], "sid": sid,
              "jti": str(uuid.uuid4()), "iat": ahora, "nbf": ahora, "exp": ahora + ACCESS_TTL}
    return jwt.encode(claims, ajustes["JWT_SECRET_KEY"], algorithm="HS256")


def registrar(app):
    @app.errorhandler(RedisNoDisponible)
    def redis_caido(exc):
        return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "Redis no está disponible."))

    @app.get("/api/v1/auth/captcha")
    def captcha():
        return responder(nuevo_captcha(), "captcha")

    @app.post("/api/v1/auth/login")
    def login():
        datos = diccionario(leer_cuerpo())
        usuario = _texto(datos, "usuario").strip()
        password = _texto(datos, "password")
        captcha_id = _texto(datos, "captcha_id")
        respuesta = _texto(datos, "captcha_respuesta")
        # Antes que la contraseña: sin resolver el captcha no se puede probar ninguna.
        if not captcha_valido(captcha_id, respuesta):
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "El captcha es incorrecto o venció. Pide uno nuevo.")

        cuenta, error = auth.attempt_login(usuario, password)
        if error:
            log_audit(_contexto(None), "LOGIN_FAILED", "users", entity_id=usuario)
            # Cuenta inactiva, bloqueada o contraseña equivocada: el mismo mensaje,
            # para no revelar cuál de las tres es.
            raise ErrorAPI(401, "CREDENCIALES_INVALIDAS", auth.MENSAJE_CREDENCIALES)

        sesion = sesiones.abrir(cuenta["id"], cuenta["roles"], ttl=SESION_TTL)
        log_audit(_contexto(cuenta["id"]), "LOGIN", "users", entity_id=str(cuenta["id"]))
        return responder({
            "access_token": emitir_access(cuenta, sesion["sid"], current_app.config),
            "refresh_token": sesion["refresh"],
            "token_type": "Bearer",
            "expires_in": ACCESS_TTL,
            "sesion_expira": sesion["expira"],
            "usuario": cuenta,
        }, "sesion")
