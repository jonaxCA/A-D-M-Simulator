import json
import os
import re
import secrets
import time
import uuid

import jwt
from flask import current_app, g, request

from epidemia_comun import llaves
from epidemia_comun.auditoria import Contexto, log_audit
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.http import llamar
from epidemia_comun.limites import limitar
from epidemia_comun.redis_compartido import RedisNoDisponible, requerido
from epidemia_comun.seguridad import requiere_token, token_servicio
from epidemia_comun.validaciones import diccionario, entero_positivo
from . import datos as auth, mfa

ACCESS_TTL = 20 * 60
CAPTCHA_TTL = 300
MFA_TTL = 300
MFA_INTENTOS = 5
# Tope por cuenta, aparte del que lleva cada token de MFA: pedir otro token no reinicia la cuenta.
MFA_FALLOS_CUENTA = 5
MFA_BLOQUEO = 15 * 60
ALTA_TTL = 15 * 60
CODIGO_6 = re.compile(r"[0-9]{6}")


def _perfiles_mfa():
    # D40: sin MFA_PERFILES (o vacía) el MFA está apagado; se activa con MFA_PERFILES=ADMINISTRADOR,EPIDEMIOLOGO,AUTORIDAD_SANITARIA.
    return {p.strip() for p in os.environ.get("MFA_PERFILES", "").split(",") if p.strip()}


def _contexto(user_id):
    return Contexto(user_id, request.remote_addr,
                    (request.headers.get("User-Agent") or "")[:255])


def _texto(datos, campo):
    valor = datos.get(campo)
    if valor is None or isinstance(valor, (dict, list, bool)) or not str(valor).strip():
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Falta el campo %s." % campo)
    return str(valor)


def _revisar_dispositivo(cuenta, identificador, etiqueta):
    if not isinstance(identificador, str) or not 8 <= len(identificador.strip()) <= 128:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "dispositivo_id debe tener de 8 a 128 caracteres.")
    identificador = identificador.strip()
    respuesta = llamar("sesiones", "POST", "/api/v1/sessions/devices/check",
                       token=token_servicio(current_app.config, "auth"),
                       cuerpo={"usuario": cuenta["id"], "dispositivo_id": identificador,
                               "etiqueta": etiqueta if isinstance(etiqueta, str) else None})
    if respuesta.status_code == 429:
        raise ErrorAPI(429, "DEMASIADOS_DISPOSITIVOS",
                       "Demasiados dispositivos pendientes: pide a un ADMINISTRADOR que los revise.")
    if respuesta.status_code != 200:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "sesiones no pudo revisar el dispositivo.")
    estado = respuesta.json()["status"]
    if estado != "autorizado":
        raise ErrorAPI(403, "DISPOSITIVO_NO_AUTORIZADO",
                       "Este dispositivo está %s: autorízalo desde una sesión abierta en otro "
                       "dispositivo autorizado o pide a un ADMINISTRADOR que lo autorice." % estado)
    return llaves.huella(identificador)


def _token_mfa(cuenta, dispositivo):
    token = secrets.token_urlsafe(32)
    clave = llaves.mfa(llaves.huella(token))

    def guardar(r):
        p = r.pipeline()
        p.hset(clave, mapping={"cuenta": json.dumps(cuenta), "dispositivo": dispositivo or "",
                               "intentos": 0})
        p.expire(clave, MFA_TTL)
        p.execute()

    requerido("mfa_crear", guardar)
    return token, int(time.time()) + MFA_TTL


def _leer_mfa(datos):
    token = _texto(datos, "mfa_token").strip()
    clave = llaves.mfa(llaves.huella(token))
    guardado = requerido("mfa_leer", lambda r: r.hgetall(clave))
    if not guardado:
        raise ErrorAPI(401, "MFA_TOKEN_INVALIDO", "El token de MFA no es válido o venció. Inicia sesión otra vez.")
    return clave, guardado, json.loads(guardado["cuenta"])


def _bloqueo_mfa(cuenta):
    log_audit(_contexto(cuenta["id"]), "LOGIN_FAILED", "user_mfa", entity_id=str(cuenta["id"]),
              data_after={"bloqueada": True})
    raise ErrorAPI(429, "MFA_BLOQUEADO",
                   "Demasiados códigos incorrectos. Intenta de nuevo en %d minutos." % (MFA_BLOQUEO // 60))


def _mfa_bloqueada(cuenta):
    fallos = requerido("mfa_fallos_leer", lambda r: r.get(llaves.mfa_fallos(cuenta["id"])))
    return int(fallos or 0) >= MFA_FALLOS_CUENTA


def _gastar_intento(cuenta):
    # Se cuenta antes de verificar y de forma atómica: las peticiones en paralelo no rebasan el tope.
    clave = llaves.mfa_fallos(cuenta["id"])

    def sumar(r):
        p = r.pipeline()
        p.incr(clave)
        p.ttl(clave)
        n, ttl = p.execute()
        if ttl < 0:
            r.expire(clave, MFA_BLOQUEO)
        return n

    if requerido("mfa_fallos_sumar", sumar) > MFA_FALLOS_CUENTA:
        _bloqueo_mfa(cuenta)


def _fallo_mfa(clave, cuenta):
    log_audit(_contexto(cuenta["id"]), "LOGIN_FAILED", "user_mfa", entity_id=str(cuenta["id"]))

    def sumar(r):
        if r.hincrby(clave, "intentos", 1) >= MFA_INTENTOS:
            r.delete(clave)

    requerido("mfa_fallo", sumar)
    raise ErrorAPI(401, "MFA_CODIGO_INVALIDO", "El código no es correcto.")


def _codigo(datos):
    entrada = _texto(datos, "codigo").strip()
    if not entrada.isascii():
        raise ErrorAPI(422, "DATOS_INVALIDOS", "codigo solo admite caracteres ASCII.")
    return entrada


def _consumir_alta(cuenta, codigo):
    if not isinstance(codigo, str) or not codigo.strip():
        raise ErrorAPI(403, "ALTA_REQUERIDA",
                       "Enrolar el MFA requiere un código de alta: pídelo a un ADMINISTRADOR.")
    clave = llaves.mfa_alta(cuenta["id"])

    def operar(r):
        p = r.pipeline()
        p.get(clave)
        p.delete(clave)
        return p.execute()[0]

    esperado = requerido("mfa_alta_usar", operar)
    if esperado is None or not secrets.compare_digest(esperado, llaves.huella(codigo.strip())):
        raise ErrorAPI(403, "ALTA_INVALIDA", "El código de alta no es válido o venció.")


def _abrir_sesion(clave, guardado, cuenta, extra=None):
    # Quien consume el token de MFA primero es el único que abre la sesión.
    if requerido("mfa_consumir", lambda r: r.delete(clave)) != 1:
        raise ErrorAPI(401, "MFA_TOKEN_INVALIDO", "El token de MFA no es válido o venció. Inicia sesión otra vez.")
    requerido("mfa_fallos_borrar", lambda r: r.delete(llaves.mfa_fallos(cuenta["id"])))
    return _sesion(cuenta, guardado["dispositivo"] or None, extra)


def _sesion(cuenta, dispositivo, extra=None):
    respuesta = llamar("sesiones", "POST", "/api/v1/sessions/internal/open",
                       token=token_servicio(current_app.config, "auth"),
                       cuerpo={"usuario": cuenta["id"], "roles": cuenta["roles"],
                               "dispositivo": dispositivo})
    if respuesta.status_code != 200:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "sesiones no pudo abrir la sesión.")
    sesion = respuesta.json()
    log_audit(_contexto(cuenta["id"]), "LOGIN", "users", entity_id=str(cuenta["id"]),
              **({"data_after": {"sesiones_cerradas": sesion["cerradas"]}} if sesion["cerradas"] else {}))
    return responder({
        "access_token": emitir_access(cuenta, sesion["sid"], current_app.config),
        "refresh_token": sesion["refresh"],
        "token_type": "Bearer",
        "expires_in": ACCESS_TTL,
        "sesion_expira": sesion["expira"],
        "usuario": cuenta,
        **(extra or {}),
    }, "sesion")


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
    @limitar("normal")
    def captcha():
        return responder(nuevo_captcha(), "captcha")

    @app.post("/api/v1/auth/login")
    @limitar()
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

        critico = bool(_perfiles_mfa() & set(cuenta["roles"]))
        identificador = datos.get("dispositivo_id")
        if identificador is None and (critico or os.environ.get("DISPOSITIVO_OBLIGATORIO") == "1"):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Falta el campo dispositivo_id.")
        dispositivo = None
        if identificador is not None:
            dispositivo = _revisar_dispositivo(cuenta, identificador, datos.get("dispositivo_etiqueta"))
        if not critico:
            return _sesion(cuenta, dispositivo)
        if _mfa_bloqueada(cuenta):
            _bloqueo_mfa(cuenta)
        token, expira = _token_mfa(cuenta, dispositivo)
        fila = mfa.estado(cuenta["id"])
        return responder({"mfa_requerido": True, "mfa_enrolado": bool(fila and fila["enabled"]),
                          "mfa_token": token, "mfa_expira": expira}, "mfa")

    @app.post("/api/v1/auth/mfa/verify")
    @limitar()
    def mfa_verificar():
        datos = diccionario(leer_cuerpo())
        clave, guardado, cuenta = _leer_mfa(datos)
        entrada = _codigo(datos)
        fila = mfa.estado(cuenta["id"])
        if fila is None or not fila["enabled"]:
            raise ErrorAPI(409, "CONFLICTO", "La cuenta aún no tiene MFA: usa /api/v1/auth/mfa/enroll.")
        _gastar_intento(cuenta)
        if CODIGO_6.fullmatch(entrada):
            paso = mfa.paso_valido(fila["secret"], entrada, fila["last_counter"])
            valido = paso is not None and mfa.aceptar_paso(cuenta["id"], paso)
        else:
            valido = mfa.usar_respaldo(_contexto(cuenta["id"]), cuenta["id"],
                                       mfa.normalizar_respaldo(entrada))
        if not valido:
            _fallo_mfa(clave, cuenta)
        return _abrir_sesion(clave, guardado, cuenta)

    @app.post("/api/v1/auth/mfa/enroll")
    @limitar()
    def mfa_enrolar():
        datos = diccionario(leer_cuerpo())
        clave, _, cuenta = _leer_mfa(datos)
        fila = mfa.estado(cuenta["id"])
        if fila is not None and fila["enabled"]:
            raise ErrorAPI(409, "CONFLICTO", "La cuenta ya tiene MFA.")
        if fila is not None and fila.get("pendiente_reciente"):
            raise ErrorAPI(409, "CONFLICTO", "Ya hay un enrolamiento en curso; un ADMINISTRADOR puede restablecerlo.")
        # D40: sin el código de alta, quien llega primero con la contraseña fijaría su propio secreto.
        if os.environ.get("MFA_ENROLAMIENTO_LIBRE") != "1":
            _consumir_alta(cuenta, datos.get("codigo_alta"))
        secreto = mfa.nuevo_secreto()
        if not mfa.guardar_secreto(_contexto(cuenta["id"]), cuenta["id"], secreto):
            raise ErrorAPI(409, "CONFLICTO", "Ya hay un enrolamiento en curso; un ADMINISTRADOR puede restablecerlo.")
        return responder({"secreto": secreto, "uri": mfa.uri(secreto, cuenta["username"]),
                          "algoritmo": "SHA1", "digitos": mfa.DIGITOS, "periodo": mfa.PASO}, "mfa")

    @app.post("/api/v1/auth/mfa/confirm")
    @limitar()
    def mfa_confirmar():
        datos = diccionario(leer_cuerpo())
        clave, guardado, cuenta = _leer_mfa(datos)
        entrada = _codigo(datos)
        if not CODIGO_6.fullmatch(entrada):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "codigo debe tener 6 dígitos.")
        fila = mfa.estado(cuenta["id"])
        if fila is None or fila["enabled"]:
            raise ErrorAPI(409, "CONFLICTO", "No hay un enrolamiento pendiente: usa /api/v1/auth/mfa/enroll.")
        _gastar_intento(cuenta)
        paso = mfa.paso_valido(fila["secret"], entrada)
        respaldos = None if paso is None else mfa.confirmar(_contexto(cuenta["id"]), cuenta["id"], paso)
        if respaldos is None:
            _fallo_mfa(clave, cuenta)
        return _abrir_sesion(clave, guardado, cuenta, {"codigos_respaldo": respaldos})

    @app.post("/api/v1/auth/mfa/<int:user_id>/enrollment-code")
    @requiere_token(roles=("ADMINISTRADOR",))
    def mfa_codigo_alta(user_id):
        codigo = secrets.token_hex(8)
        requerido("mfa_alta_crear",
                  lambda r: r.set(llaves.mfa_alta(user_id), llaves.huella(codigo), ex=ALTA_TTL))
        log_audit(g.contexto, "UPDATE", "user_mfa", user_id, data_after={"codigo_alta": "emitido"})
        return responder({"usuario": user_id, "codigo_alta": codigo,
                          "expira": int(time.time()) + ALTA_TTL}, "mfa")

    @app.delete("/api/v1/auth/mfa/<int:user_id>")
    @requiere_token(roles=("ADMINISTRADOR",))
    def mfa_restablecer(user_id):
        return responder({"usuario": user_id, "restablecido": mfa.restablecer(g.contexto, user_id)},
                         "mfa")
