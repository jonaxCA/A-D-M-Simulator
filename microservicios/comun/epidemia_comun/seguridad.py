from functools import wraps

import jwt

from .errores import ErrorAPI
from .llaves import huella, revocado, sesion


def identificador_sesion(sid):
    return huella(str(sid))


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


def requiere_token(roles=()):
    from flask import current_app, g, request
    def decorador(funcion):
        @wraps(funcion)
        def ejecutar(*args, **kwargs):
            cabecera = request.headers.get("Authorization", "")
            if not cabecera.startswith("Bearer "):
                raise ErrorAPI(401, "TOKEN_AUSENTE", "Falta Authorization: Bearer.")
            usuario = verificar_token(cabecera[7:].strip(), current_app.config,
                                     current_app.extensions["epidemia_redis"], roles)
            g.usuario = usuario
            from backend_web.contexto import Contexto
            try:
                user_id = int(usuario["sub"])
            except (TypeError, ValueError):
                raise ErrorAPI(401, "TOKEN_INVALIDO", "Identificador de usuario inválido.")
            g.contexto = Contexto(user_id, request.remote_addr,
                                  request.user_agent.string[:255])
            return funcion(*args, **kwargs)
        return ejecutar
    return decorador


def solo_servicios(funcion):
    from flask import current_app, g, request
    @wraps(funcion)
    def ejecutar(*args, **kwargs):
        cabecera = request.headers.get("Authorization", "")
        if not cabecera.startswith("Bearer "):
            raise ErrorAPI(401, "TOKEN_AUSENTE", "Falta Authorization: Bearer.")
        g.servicio = verificar_token(cabecera[7:].strip(), current_app.config,
                                    current_app.extensions["epidemia_redis"], interno=True)
        return funcion(*args, **kwargs)
    return ejecutar
