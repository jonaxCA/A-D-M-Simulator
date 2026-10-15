import psycopg2
from flask import g, request

from backend_web import queries
from backend_web.audit import log_audit
from backend_web.auth import get_user_roles, hash_password
from backend_web.db import get_conn
from epidemia_comun import sesiones
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.redis_compartido import RedisNoDisponible
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo

# Las mismas pantallas del monolito son solo de ADMINISTRADOR (admin_required).
ADMIN = ("ADMINISTRADOR",)
ESTADOS = ("activo", "pendiente", "inactivo")
COLUMNAS = ("id", "username", "email", "full_name", "is_active")


def _texto(datos, campo):
    valor = datos.get(campo)
    if valor is not None and not isinstance(valor, str):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El campo %s debe ser texto." % campo)
    return valor or ""


def _booleano(valor):
    # En XML sin el atributo tipo llega como texto.
    if isinstance(valor, str) and valor.lower() in ("true", "false"):
        return valor.lower() == "true"
    if not isinstance(valor, bool):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "is_active debe ser true o false.")
    return valor


def _validar(username, email, full_name, es_alta, password):
    errores = queries.valida_usuario(username, email, full_name, es_alta=es_alta,
                                     password=password)
    if errores:
        raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))


def _ficha(cur, user_id, bloquear=False):
    # Lo que se regresa y se audita: nunca password_hash.
    cur.execute("SELECT id, username, email, full_name, is_active FROM users WHERE id = %s"
                + (" FOR UPDATE" if bloquear else ""), (user_id,))
    fila = cur.fetchone()
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el usuario.")
    return dict(zip(COLUMNAS, fila))


def _no_a_si_mismo(user_id, detalle):
    if user_id == int(g.usuario["sub"]):
        raise ErrorAPI(409, "CONFLICTO", detalle)


def _duplicado(exc):
    if "uq_users_username" in str(exc):
        return "Ya existe un usuario con ese nombre de usuario."
    if "uq_users_email" in str(exc):
        return "Ya existe un usuario con ese correo."
    return "Ya existe un usuario con esos datos."


def registrar(app):
    @app.errorhandler(RedisNoDisponible)
    def redis_caido(exc):
        return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "Redis no está disponible."))

    @app.get("/api/v1/users")
    @requiere_token(roles=ADMIN)
    def lista():
        estado = request.args.get("status")
        if estado not in (None,) + ESTADOS:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "status debe ser activo, pendiente o inactivo.")
        rol = request.args.get("role_id")
        datos = queries.get_usuarios_lista(
            busqueda=(request.args.get("q") or "").strip() or None,
            rol_id=entero_positivo(rol, "role_id") if rol else None, estado=estado)
        return responder({"total": len(datos), "usuarios": datos}, "catalogo_usuarios")

    @app.get("/api/v1/users/<int:user_id>")
    @requiere_token(roles=ADMIN)
    def detalle(user_id):
        fila = queries.get_usuario(user_id)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el usuario.")
        return responder({**fila, "roles": get_user_roles(user_id)}, "usuario")

    # El rol se asigna después, en el servicio roles (dueño de user_roles).
    @app.post("/api/v1/users")
    @requiere_token(roles=ADMIN)
    def crear():
        datos = diccionario(leer_cuerpo())
        if set(datos) - {"username", "email", "full_name", "password", "is_active"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "Campos no reconocidos; el rol se asigna en el servicio roles.")
        username, email, full_name, password = (
            _texto(datos, c) for c in ("username", "email", "full_name", "password"))
        activo = _booleano(datos.get("is_active", True))
        _validar(username, email, full_name, True, password)
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO users (username, email, password_hash, full_name, is_active)
                                   VALUES (lower(%s), lower(%s), %s, %s, %s) RETURNING id""",
                                (username.strip(), email.strip(), hash_password(password),
                                 full_name.strip(), activo))
                    ficha = _ficha(cur, cur.fetchone()[0])
                    log_audit(g.contexto, "CREATE", "users", ficha["id"], data_after=ficha, cur=cur)
                conn.commit()
        except psycopg2.errors.UniqueViolation as exc:
            raise ErrorAPI(409, "CONFLICTO", _duplicado(exc)) from exc
        except psycopg2.errors.CheckViolation as exc:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Los datos no cumplen las restricciones de la base.") from exc
        return responder(ficha, "usuario", estado=201)

    # El username no se edita (como en el monolito); estado y rol tienen sus rutas.
    @app.put("/api/v1/users/<int:user_id>")
    @requiere_token(roles=ADMIN)
    def editar(user_id):
        datos = diccionario(leer_cuerpo())
        if set(datos) - {"email", "full_name", "password"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "Solo se editan email, full_name y password.")
        email, full_name, password = (_texto(datos, c) for c in ("email", "full_name", "password"))
        _validar("", email, full_name, False, password)
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    antes = _ficha(cur, user_id, bloquear=True)
                    cur.execute("""UPDATE users SET email = lower(%s), full_name = %s,
                                   password_hash = COALESCE(%s, password_hash) WHERE id = %s""",
                                (email.strip(), full_name.strip(),
                                 hash_password(password) if password else None, user_id))
                    despues = _ficha(cur, user_id)
                    log_audit(g.contexto, "UPDATE", "users", user_id,
                              data_before=antes, data_after=despues, cur=cur)
                    # Con contraseña nueva, las sesiones abiertas con la anterior se cierran.
                    cerradas = sesiones.cerrar_todas(user_id) if password else 0
                conn.commit()
        except psycopg2.errors.UniqueViolation as exc:
            raise ErrorAPI(409, "CONFLICTO", "Ya existe otro usuario con ese correo.") from exc
        except psycopg2.errors.CheckViolation as exc:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Los datos no cumplen las restricciones de la base.") from exc
        return responder({**despues, "sesiones_cerradas": cerradas}, "usuario")

    @app.post("/api/v1/users/<int:user_id>/<accion>")
    @requiere_token(roles=ADMIN)
    def activar(user_id, accion):
        if accion not in ("activate", "deactivate"):
            raise ErrorAPI(404, "NO_ENCONTRADO", "Operación no disponible.")
        activo = accion == "activate"
        if not activo:
            _no_a_si_mismo(user_id, "No puedes desactivar tu propia cuenta.")
        with get_conn() as conn:
            with conn.cursor() as cur:
                antes = _ficha(cur, user_id, bloquear=True)
                cur.execute("UPDATE users SET is_active = %s WHERE id = %s", (activo, user_id))
                log_audit(g.contexto, "UPDATE", "users", user_id, data_before=antes,
                          data_after={**antes, "is_active": activo}, cur=cur)
                # Antes del commit: si Redis falla, la baja no se guarda con sesiones abiertas.
                cerradas = 0 if activo else sesiones.cerrar_todas(user_id)
            conn.commit()
        return responder({"id": user_id, "is_active": activo, "sesiones_cerradas": cerradas},
                         "usuario")

    @app.delete("/api/v1/users/<int:user_id>")
    @requiere_token(roles=ADMIN)
    def eliminar(user_id):
        _no_a_si_mismo(user_id, "No puedes eliminar tu propia cuenta.")
        if queries.get_usuario(user_id) is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el usuario.")
        dependencias = queries.dependencias_usuario(user_id)
        if dependencias:
            detalle = ", ".join("%d %s" % (n, etiqueta) for etiqueta, n in dependencias)
            raise ErrorAPI(409, "CONFLICTO", "No se puede eliminar: tiene %s. "
                           "Usa la baja lógica (deactivate)." % detalle)
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    antes = _ficha(cur, user_id, bloquear=True)
                    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                    log_audit(g.contexto, "DELETE", "users", user_id, data_before=antes, cur=cur)
                    cerradas = sesiones.cerrar_todas(user_id)
                conn.commit()
        except (psycopg2.errors.ForeignKeyViolation, psycopg2.errors.RestrictViolation) as exc:
            raise ErrorAPI(409, "CONFLICTO", "No se puede eliminar: el usuario tiene registros "
                           "asociados. Usa la baja lógica (deactivate).") from exc
        return responder({"id": user_id, "eliminado": True, "sesiones_cerradas": cerradas},
                         "usuario")
