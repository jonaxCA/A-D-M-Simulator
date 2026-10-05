"""Sesion web: cookie con el JWT y decoradores de acceso por rol.
La parte de credenciales (usuarios, bcrypt, firma del JWT) vive en backend_web.auth.
"""
from functools import wraps

from flask import request, redirect, url_for, g, flash

from backend_web.auth import decode_token, usuario_vigente
from backend_web.contexto import Contexto

COOKIE_NAME = "access_token"

# Mismo texto en todos los candados, para que el rechazo se vea igual en
# cualquier pantalla.
MENSAJE_SIN_PERMISO = "No tienes permiso para entrar a esa sección."

_SIN_CALCULAR = object()
_USUARIO_DE_LA_SESION = object()


def contexto_de_peticion(user_id=_USUARIO_DE_LA_SESION):
    """El Contexto de la peticion en curso, para pasarlo a backend_web.

    Por omision el actor es el usuario de la sesion (g.user, que fijan los
    decoradores de este modulo). Donde todavia no hay sesion -- el login, el
    logout, un intento denegado -- se pasa el id explicito, o None.
    """
    if user_id is _USUARIO_DE_LA_SESION:
        user_id = g.user["sub"]
    return Contexto(user_id, request.remote_addr,
                    (request.headers.get("User-Agent") or "")[:255])


def get_current_user():
    """El usuario de la peticion, revalidado contra la base.

    Una firma valida solo prueba que el token lo emitimos nosotros, no que la
    cuenta siga activa ni que conserve sus roles: eso lo contesta
    usuario_vigente(). Se calcula una vez por peticion y se guarda en `g`,
    porque la llaman el decorador y el context_processor de cada plantilla.
    """
    en_cache = g.get("_usuario_actual", _SIN_CALCULAR)
    if en_cache is not _SIN_CALCULAR:
        return en_cache
    usuario = None
    token = request.cookies.get(COOKIE_NAME)
    if token:
        payload = decode_token(token)
        if payload:
            usuario = usuario_vigente(payload)
    g._usuario_actual = usuario
    return usuario


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("main.login", next=request.path))
        g.user = user
        return view(*args, **kwargs)
    return wrapped


def tiene_rol(user, *codigos):
    """True si el usuario del JWT trae alguno de los roles indicados."""
    if not user:
        return False
    return any(c in (user.get("roles") or []) for c in codigos)


def roles_required(*codigos, entity_type="diseases"):
    """Restringe la vista a los roles indicados.

    Misma mecanica que admin_required, pero parametrizable: la usa el catalogo
    de enfermedades, donde definir parametros epidemiologicos es trabajo del
    EPIDEMIOLOGO (el ADMINISTRADOR entra por ser quien opera el sistema).

    `entity_type` es el modulo que queda en la bitacora del intento denegado.
    El valor por defecto es "diseases" porque ahi nacio el decorador; al usarlo
    en otra pantalla hay que pasarlo, o la bitacora atribuiria el intento al
    catalogo de enfermedades y quedaria inservible para rastrear accesos.

    El intento fallido queda en la bitacora: ocultar el boton en la plantilla
    no es control de acceso.
    """
    def decorador(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                return redirect(url_for("main.login", next=request.path))
            g.user = user
            if not tiene_rol(user, *codigos):
                from backend_web.audit import log_audit
                log_audit(contexto_de_peticion(user["sub"]), "PERMISSION_DENIED", entity_type,
                          entity_id=request.path)
                flash(MENSAJE_SIN_PERMISO, "error")
                return redirect(url_for("main.dashboard", denegado=1))
            return view(*args, **kwargs)
        return wrapped
    return decorador


def admin_required(view=None, *, entity_type="users"):
    """Restringe la vista al rol ADMINISTRADOR.

    Un usuario logueado pero sin el rol (p.ej. diana.flores, EPIDEMIOLOGO) NO
    entra: se le manda al dashboard y se deja el intento en la bitacora como
    PERMISSION_DENIED. Sin esto, cualquier cuenta autenticada podria dar de
    alta o borrar usuarios.

    `entity_type` es el modulo que queda en la bitacora del intento denegado
    (por defecto "users", que es donde vivia originalmente este decorador).
    Se puede usar tanto sin parentesis (`@admin_required`) como parametrizado
    (`@admin_required(entity_type="regions")`), igual que roles_required.
    """
    def decorador(v):
        @wraps(v)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                return redirect(url_for("main.login", next=request.path))
            g.user = user
            if not tiene_rol(user, "ADMINISTRADOR"):
                # import local para no crear un ciclo audit <-> auth al importar
                from backend_web.audit import log_audit
                log_audit(contexto_de_peticion(user["sub"]), "PERMISSION_DENIED", entity_type,
                          entity_id=request.path)
                flash(MENSAJE_SIN_PERMISO, "error")
                return redirect(url_for("main.dashboard", denegado=1))
            return v(*args, **kwargs)
        return wrapped

    if view is not None:
        return decorador(view)
    return decorador
