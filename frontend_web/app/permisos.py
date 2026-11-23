"""Sesion web y candados por permiso (D1, RF-A05).

Las credenciales y la sesion las llevan auth y sesiones (D36). Los permisos de la cuenta salen de
role_permissions por medio de roles (`GET /api/v1/permissions/me`) y se guardan en la sesion
firmada al entrar. Cambiar el rol de una cuenta cierra sus sesiones, asi que no envejecen.
"""
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from backend_web import servicios
from backend_web.servicios import ErrorServicio, ServicioNoDisponible

from . import sesion_servicios
from .sesion_servicios import COOKIE_ACCESS, COOKIE_REFRESH

COOKIE_NAME = COOKIE_ACCESS

MENSAJE_SIN_PERMISO = "No tienes permiso para entrar a esa sección."

# En la web el CAPTURISTA solo consulta el tablero y el mapa (D1, RF-G11): captura en la app movil.
ROLES_SOLO_TABLERO = {"CAPTURISTA"}

_SIN_CALCULAR = object()


def get_current_user():
    """El usuario de la peticion, segun sesiones, con sus permisos; o None.

    Se calcula una vez por peticion. Si sesiones no responde sube ServicioNoDisponible: la web no
    deja pasar sin poder revisar la sesion (D36).
    """
    en_cache = g.get("_usuario_actual", _SIN_CALCULAR)
    if en_cache is not _SIN_CALCULAR:
        return en_cache
    g.access = request.cookies.get(COOKIE_ACCESS)
    user = sesion_servicios.usuario(g.access, request.cookies.get(COOKIE_REFRESH))
    if user:
        user["permisos"] = permisos_de_la_sesion(g.access, user["sub"])
    g._usuario_actual = user
    return user


def permisos_de_la_sesion(token, user_id):
    guardados = session.get("permisos")
    if guardados and guardados.get("user_id") == user_id:
        return set(guardados.get("codigos") or [])
    try:
        datos = servicios.llamar("roles", "GET", "/api/v1/permissions/me", token=token) or {}
    except ErrorServicio:
        # Si roles rechaza la consulta, la cuenta se queda sin permisos: falla cerrada.
        return set()
    codigos = list(datos.get("permisos") or [])
    session["permisos"] = {"user_id": user_id, "codigos": codigos}
    return set(codigos)


def token_de_sesion():
    """El access vigente de la peticion, para reenviarlo a los servicios (D34)."""
    get_current_user()
    return g.get("access")


def tiene_rol(user, *codigos):
    return bool(user) and any(c in (user.get("roles") or []) for c in codigos)


def tiene_permiso(user, codigo):
    if not user:
        return False
    if codigo is None:
        return not solo_tablero(user)
    return codigo in user.get("permisos", ()) and not solo_tablero(user)


def solo_tablero(user):
    return set(user.get("roles") or []) <= ROLES_SOLO_TABLERO


def _audita_negado(codigo, modulo):
    # El 403 queda en la bitacora de roles; negar no depende de poder anotarlo.
    try:
        servicios.llamar("roles", "POST", "/api/v1/audit/denied", token=g.get("access"),
               cuerpo={"ruta": request.path[:64], "permiso": codigo or "", "modulo": modulo})
    except (ErrorServicio, ServicioNoDisponible):
        pass


def login_required(view):
    """Solo pide sesion: el tablero y el mapa, que ven todos los roles (matriz de permisos)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("main.login", next=request.path))
        g.user = user
        return view(*args, **kwargs)
    return wrapped


def requiere_permiso(codigo=None, modulo="web"):
    """Candado de una ruta: sin sesion manda al login; sin el permiso (o con solo el rol
    CAPTURISTA) responde 403 y deja PERMISSION_DENIED en la bitacora (RF-A05).

    `codigo` es un permiso de role_permissions. Sin codigo, basta con no ser CAPTURISTA: son las
    pantallas que la matriz abre a todos los roles de oficina, como los avisos propios.
    """
    def decorador(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                return redirect(url_for("main.login", next=request.path))
            g.user = user
            if not tiene_permiso(user, codigo):
                _audita_negado(codigo, modulo)
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorador
