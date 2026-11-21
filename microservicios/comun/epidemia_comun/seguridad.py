import time
from functools import wraps
from uuid import uuid4

import jwt

from .errores import ErrorAPI
from . import limites
from .llaves import huella, revocado, sesion


def identificador_sesion(sid):
    return huella(str(sid))


def token_servicio(ajustes, nombre, duracion=60):
    # Para las llamadas sin persona detrás. Su audiencia es la interna: solo lo
    # aceptan las rutas con @solo_servicios.
    ahora = int(time.time())
    claims = {"iss": ajustes["JWT_ISSUER"], "aud": ajustes["JWT_AUDIENCE_INTERNA"], "sub": nombre,
              "jti": str(uuid4()), "iat": ahora, "nbf": ahora, "exp": ahora + duracion}
    return jwt.encode(claims, ajustes["JWT_SECRET_KEY"], algorithm="HS256")


def verificar_token(token, ajustes, redis_client, roles=(), interno=False):
    audiencia = ajustes["JWT_AUDIENCE_INTERNA"] if interno else ajustes["JWT_AUDIENCE"]
    try:
        payload = jwt.decode(
            token, ajustes["JWT_SECRET_KEY"], algorithms=["HS256"],
            issuer=ajustes["JWT_ISSUER"], audience=audiencia,
            options={"require": ["iss", "aud", "exp", "nbf", "iat", "jti", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ErrorAPI(401, "TOKEN_EXPIRADO", "La sesión venció.") from exc
    except jwt.PyJWTError as exc:
        raise ErrorAPI(401, "TOKEN_INVALIDO", "Token inválido.") from exc
    if not interno and not payload.get("sid"):
        raise ErrorAPI(401, "TOKEN_INVALIDO", "Token sin sesión.")
    try:
        if redis_client.exists(revocado(payload["jti"])):
            raise ErrorAPI(401, "TOKEN_REVOCADO", "La sesión fue revocada.")
        if not interno and not redis_client.exists(sesion(identificador_sesion(payload["sid"]))):
            raise ErrorAPI(401, "TOKEN_REVOCADO", "La sesión ya no está activa.")
        if interno:
            redis_client.ping()
    except ErrorAPI:
        raise
    except Exception as exc:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "Redis no está disponible.") from exc
    actuales = payload.get("roles") or []
    if not isinstance(actuales, list) or any(not isinstance(rol, str) for rol in actuales):
        raise ErrorAPI(401, "TOKEN_INVALIDO", "Los roles del token no son válidos.")
    if roles and not set(roles).intersection(actuales):
        raise ErrorAPI(403, "PERMISO_INSUFICIENTE", "No tienes permiso para esta operación.")
    return payload


def _audita_negado(contexto, roles):
    # RF-A05: el 403 queda en la bitácora del servicio que lo responde (D36). Si la base no
    # responde, el 403 sale igual: negar no depende de poder anotarlo.
    from flask import current_app, request
    from .auditoria import log_audit
    try:
        log_audit(contexto, "PERMISSION_DENIED", current_app.name[:60], entity_id=request.path[:64],
                  data_after={"metodo": request.method, "roles_requeridos": list(roles)})
    except Exception as exc:
        current_app.logger.warning("No se pudo auditar el permiso denegado: %s", type(exc).__name__)


def requiere_token(roles=()):
    from flask import current_app, g, request
    def decorador(funcion):
        @wraps(funcion)
        def ejecutar(*args, **kwargs):
            cabecera = request.headers.get("Authorization", "")
            if not cabecera.startswith("Bearer "):
                raise ErrorAPI(401, "TOKEN_AUSENTE", "Falta Authorization: Bearer.")
            usuario = verificar_token(cabecera[7:].strip(), current_app.config,
                                     current_app.extensions["epidemia_redis"])
            g.usuario = usuario
            from .auditoria import Contexto
            try:
                user_id = int(usuario["sub"])
            except (TypeError, ValueError):
                raise ErrorAPI(401, "TOKEN_INVALIDO", "Identificador de usuario inválido.")
            g.contexto = Contexto(user_id, request.remote_addr,
                                  request.user_agent.string[:255])
            if roles and not set(roles).intersection(usuario.get("roles") or []):
                _audita_negado(g.contexto, roles)
                raise ErrorAPI(403, "PERMISO_INSUFICIENTE", "No tienes permiso para esta operación.")
            limites.consumir(usuario["sub"])
            return funcion(*args, **kwargs)
        return ejecutar
    return decorador


def solo_servicios(*permitidos):
    # @solo_servicios acepta a cualquier servicio; @solo_servicios("auth") solo a los nombrados.
    from flask import current_app, g, request

    def decorador(funcion):
        @wraps(funcion)
        def ejecutar(*args, **kwargs):
            cabecera = request.headers.get("Authorization", "")
            if not cabecera.startswith("Bearer "):
                raise ErrorAPI(401, "TOKEN_AUSENTE", "Falta Authorization: Bearer.")
            g.servicio = verificar_token(cabecera[7:].strip(), current_app.config,
                                        current_app.extensions["epidemia_redis"], interno=True)
            if permitidos and g.servicio["sub"] not in permitidos:
                raise ErrorAPI(403, "PERMISO_INSUFICIENTE", "Este servicio no puede usar esta ruta.")
            return funcion(*args, **kwargs)
        return ejecutar
    if len(permitidos) == 1 and callable(permitidos[0]):
        funcion, permitidos = permitidos[0], ()
        return decorador(funcion)
    return decorador
