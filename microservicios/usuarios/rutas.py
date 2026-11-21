import psycopg2
from flask import g, request

from epidemia_comun import sesiones
from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import get_conn, query
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.redis_compartido import RedisNoDisponible
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo
from . import datos as reglas

# Las mismas pantallas del monolito son solo de ADMINISTRADOR (admin_required).
ADMIN = ("ADMINISTRADOR",)
ESTADOS = ("activo", "pendiente", "inactivo")
INSTITUCION = ("id", "code", "name", "is_active")
COLUMNAS = ("id", "username", "email", "full_name", "is_active", "institution_id", "region_id")


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
    errores = reglas.valida_usuario(username, email, full_name, es_alta=es_alta,
                                     password=password)
    if errores:
        raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))


def _id_opcional(datos, campo):
    valor = datos.get(campo)
    return None if valor in (None, "") else entero_positivo(valor, campo)


def _fk_invalida(exc):
    if "fk_users_institution" in str(exc):
        return "No existe la institución."
    return "No existe la región."


def _ficha(cur, user_id, bloquear=False):
    # Lo que se regresa y se audita: nunca password_hash.
    cur.execute("SELECT id, username, email, full_name, is_active, institution_id, region_id"
                " FROM users WHERE id = %s"
                + (" FOR UPDATE" if bloquear else ""), (user_id,))
    fila = cur.fetchone()
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el usuario.")
    return dict(zip(COLUMNAS, fila))


def _validar_institucion(codigo, nombre):
    if not 2 <= len(codigo) <= 30:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El código debe tener de 2 a 30 caracteres.")
    if not 3 <= len(nombre) <= 160:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El nombre debe tener de 3 a 160 caracteres.")


def _no_a_si_mismo(user_id, detalle):
    if user_id == int(g.usuario["sub"]):
        raise ErrorAPI(409, "CONFLICTO", detalle)


def _duplicado(exc):
    if "uq_users_username" in str(exc):
        return "Ya existe un usuario con ese nombre de usuario."
    if "uq_users_email" in str(exc):
        return "Ya existe un usuario con ese correo."
    return "Ya existe un usuario con esos datos."


def _cuenta(user_id):
    fila = reglas.get_usuario(user_id)
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el usuario.")
    perfil = query("""SELECT u.institution_id, i.name AS institucion, u.region_id, r.name AS region
                      FROM users u LEFT JOIN institutions i ON i.id = u.institution_id
                      LEFT JOIN regions r ON r.id = u.region_id WHERE u.id = %s""",
                   (user_id,), one=True)
    return responder({**fila, **perfil, "roles": reglas.get_user_roles(user_id)}, "usuario")


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
        datos = reglas.get_usuarios_lista(
            busqueda=(request.args.get("q") or "").strip() or None,
            rol_id=entero_positivo(rol, "role_id") if rol else None, estado=estado)
        return responder({"total": len(datos), "usuarios": datos}, "catalogo_usuarios")

    # Las tarjetas de la pantalla de usuarios, con los mismos estados que la lista.
    @app.get("/api/v1/users/summary")
    @requiere_token(roles=ADMIN)
    def resumen():
        fila = query("""SELECT count(*) AS total,
                               count(*) FILTER (WHERE is_active AND last_login_at IS NOT NULL) AS activos,
                               count(*) FILTER (WHERE is_active AND last_login_at IS NULL) AS pendientes,
                               count(*) FILTER (WHERE NOT is_active) AS inactivos
                        FROM users""", one=True)
        return responder(dict(fila), "resumen_usuarios")

    # El perfil: cualquier cuenta consulta la suya, sin ser ADMINISTRADOR.
    @app.get("/api/v1/users/me")
    @requiere_token()
    def perfil():
        return _cuenta(g.contexto.user_id)

    @app.get("/api/v1/users/<int:user_id>")
    @requiere_token(roles=ADMIN)
    def detalle(user_id):
        return _cuenta(user_id)

    # El rol se asigna después, en el servicio roles (dueño de user_roles).
    @app.post("/api/v1/users")
    @requiere_token(roles=ADMIN)
    def crear():
        datos = diccionario(leer_cuerpo())
        if set(datos) - {"username", "email", "full_name", "password", "is_active",
                         "institution_id", "region_id"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "Campos no reconocidos; el rol se asigna en el servicio roles.")
        username, email, full_name, password = (
            _texto(datos, c) for c in ("username", "email", "full_name", "password"))
        activo = _booleano(datos.get("is_active", True))
        institucion, region = _id_opcional(datos, "institution_id"), _id_opcional(datos, "region_id")
        _validar(username, email, full_name, True, password)
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO users (username, email, password_hash, full_name, is_active,
                                                      institution_id, region_id)
                                   VALUES (lower(%s), lower(%s), %s, %s, %s, %s, %s) RETURNING id""",
                                (username.strip(), email.strip(), reglas.hash_password(password),
                                 full_name.strip(), activo, institucion, region))
                    ficha = _ficha(cur, cur.fetchone()[0])
                    log_audit(g.contexto, "CREATE", "users", ficha["id"], data_after=ficha, cur=cur)
                conn.commit()
        except psycopg2.errors.UniqueViolation as exc:
            raise ErrorAPI(409, "CONFLICTO", _duplicado(exc)) from exc
        except psycopg2.errors.ForeignKeyViolation as exc:
            raise ErrorAPI(422, "DATOS_INVALIDOS", _fk_invalida(exc)) from exc
        except psycopg2.errors.CheckViolation as exc:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Los datos no cumplen las restricciones de la base.") from exc
        return responder(ficha, "usuario", estado=201)

    # El username no se edita (como en el monolito); estado y rol tienen sus rutas.
    @app.put("/api/v1/users/<int:user_id>")
    @requiere_token(roles=ADMIN)
    def editar(user_id):
        datos = diccionario(leer_cuerpo())
        if set(datos) - {"email", "full_name", "password", "institution_id", "region_id"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "Solo se editan email, full_name, password, institution_id y region_id.")
        email, full_name, password = (_texto(datos, c) for c in ("email", "full_name", "password"))
        _validar("", email, full_name, False, password)
        nuevos = {c: _id_opcional(datos, c) for c in ("institution_id", "region_id") if c in datos}
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    antes = _ficha(cur, user_id, bloquear=True)
                    institucion = nuevos.get("institution_id", antes["institution_id"])
                    region = nuevos.get("region_id", antes["region_id"])
                    cur.execute("""UPDATE users SET email = lower(%s), full_name = %s,
                                   password_hash = COALESCE(%s, password_hash),
                                   institution_id = %s, region_id = %s WHERE id = %s""",
                                (email.strip(), full_name.strip(),
                                 reglas.hash_password(password) if password else None,
                                 institucion, region, user_id))
                    despues = _ficha(cur, user_id)
                    log_audit(g.contexto, "UPDATE", "users", user_id,
                              data_before=antes, data_after=despues, cur=cur)
                    # Con contraseña nueva, las sesiones abiertas con la anterior se cierran.
                    cerradas = sesiones.cerrar_de_usuario(user_id) if password else 0
                conn.commit()
        except psycopg2.errors.UniqueViolation as exc:
            raise ErrorAPI(409, "CONFLICTO", "Ya existe otro usuario con ese correo.") from exc
        except psycopg2.errors.ForeignKeyViolation as exc:
            raise ErrorAPI(422, "DATOS_INVALIDOS", _fk_invalida(exc)) from exc
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
                cerradas = 0 if activo else sesiones.cerrar_de_usuario(user_id)
            conn.commit()
        return responder({"id": user_id, "is_active": activo, "sesiones_cerradas": cerradas},
                         "usuario")

    @app.delete("/api/v1/users/<int:user_id>")
    @requiere_token(roles=ADMIN)
    def eliminar(user_id):
        _no_a_si_mismo(user_id, "No puedes eliminar tu propia cuenta.")
        if reglas.get_usuario(user_id) is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el usuario.")
        dependencias = reglas.dependencias_usuario(user_id)
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
                    cerradas = sesiones.cerrar_de_usuario(user_id)
                conn.commit()
        except (psycopg2.errors.ForeignKeyViolation, psycopg2.errors.RestrictViolation) as exc:
            raise ErrorAPI(409, "CONFLICTO", "No se puede eliminar: el usuario tiene registros "
                           "asociados. Usa la baja lógica (deactivate).") from exc
        return responder({"id": user_id, "eliminado": True, "sesiones_cerradas": cerradas},
                         "usuario")

    # Catálogo de instituciones (D42): cualquier cuenta lo lee para llenar su perfil.
    @app.get("/api/v1/institutions")
    @requiere_token()
    def instituciones():
        datos = query("SELECT id, code, name, is_active FROM institutions ORDER BY name")
        return responder({"total": len(datos), "instituciones": datos}, "catalogo_instituciones")

    @app.post("/api/v1/institutions")
    @requiere_token(roles=ADMIN)
    def crear_institucion():
        datos = diccionario(leer_cuerpo())
        if set(datos) != {"code", "name"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Manda code y name.")
        codigo, nombre = _texto(datos, "code").strip().upper(), _texto(datos, "name").strip()
        _validar_institucion(codigo, nombre)
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO institutions (code, name) VALUES (%s, %s)"
                                " RETURNING id, code, name, is_active", (codigo, nombre))
                    ficha = dict(zip(INSTITUCION, cur.fetchone()))
                    log_audit(g.contexto, "CREATE", "institutions", ficha["id"], data_after=ficha, cur=cur)
                conn.commit()
        except psycopg2.errors.UniqueViolation as exc:
            raise ErrorAPI(409, "CONFLICTO", "Ya existe una institución con ese código o nombre.") from exc
        return responder(ficha, "institucion", estado=201)

    @app.put("/api/v1/institutions/<int:institution_id>")
    @requiere_token(roles=ADMIN)
    def editar_institucion(institution_id):
        datos = diccionario(leer_cuerpo())
        if set(datos) - {"name", "is_active"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Solo se editan name e is_active.")
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, code, name, is_active FROM institutions WHERE id = %s"
                                " FOR UPDATE", (institution_id,))
                    fila = cur.fetchone()
                    if fila is None:
                        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la institución.")
                    antes = dict(zip(INSTITUCION, fila))
                    nombre = _texto(datos, "name").strip() if "name" in datos else antes["name"]
                    activa = _booleano(datos["is_active"]) if "is_active" in datos else antes["is_active"]
                    _validar_institucion(antes["code"], nombre)
                    cur.execute("UPDATE institutions SET name = %s, is_active = %s WHERE id = %s",
                                (nombre, activa, institution_id))
                    despues = {**antes, "name": nombre, "is_active": activa}
                    log_audit(g.contexto, "UPDATE", "institutions", institution_id,
                              data_before=antes, data_after=despues, cur=cur)
                conn.commit()
        except psycopg2.errors.UniqueViolation as exc:
            raise ErrorAPI(409, "CONFLICTO", "Ya existe una institución con ese nombre.") from exc
        return responder(despues, "institucion")
