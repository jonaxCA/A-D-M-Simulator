import re

import bcrypt

from epidemia_comun.bd import query

RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# tabla -> columna que apunta a users, etiqueta
DEPENDENCIAS_RESTRICT = [
    ("cases", "reported_by", "casos capturados"),
    ("case_attachments", "uploaded_by", "evidencias subidas"),
    ("vaccine_lots", "scanned_by", "lotes de vacuna escaneados"),
    ("scenarios", "owner_id", "escenarios"),
    ("scenario_versions", "created_by", "versiones de escenario"),
    ("simulation_batches", "requested_by", "lotes de simulacion"),
    # audit_log NO va en esta lista: su FK es ON DELETE SET NULL y, tras
    # la migracion 011_fix_audit_log_delete.sql, el trigger de inmutabilidad permite ese
    # unico caso. Los eventos del usuario borrado se conservan, pero quedan
    # sin dueno (user_id NULL) -- ver la nota del README sobre esa perdida de
    # atribucion.
]


def get_usuario(user_id):
    return query(
        """
        SELECT u.id, u.username, u.email, u.full_name, u.is_active,
               u.last_login_at, u.created_at,
               (SELECT ur.role_id FROM user_roles ur WHERE ur.user_id = u.id LIMIT 1) AS role_id
        FROM users u
        WHERE u.id = %s
        """,
        (user_id,),
        one=True,
    )


def get_usuarios_lista(busqueda=None, rol_id=None, estado=None):
    condiciones = []
    params = []
    if busqueda:
        condiciones.append("(u.full_name ILIKE %s OR u.email ILIKE %s OR u.username ILIKE %s)")
        like = f"%{busqueda}%"
        params += [like, like, like]
    if rol_id:
        condiciones.append("r.id = %s")
        params.append(rol_id)
    if estado == "activo":
        condiciones.append("u.is_active AND u.last_login_at IS NOT NULL")
    elif estado == "pendiente":
        condiciones.append("u.is_active AND u.last_login_at IS NULL")
    elif estado == "inactivo":
        condiciones.append("NOT u.is_active")

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    rows = query(
        f"""
        SELECT u.id, u.full_name, u.email, u.is_active, u.last_login_at,
               string_agg(DISTINCT r.name, ', ' ORDER BY r.name) AS roles,
               i.name AS institucion, reg.name AS region
        FROM users u
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        LEFT JOIN roles r ON r.id = ur.role_id
        LEFT JOIN institutions i ON i.id = u.institution_id
        LEFT JOIN regions reg ON reg.id = u.region_id
        {where}
        GROUP BY u.id, u.full_name, u.email, u.is_active, u.last_login_at, i.name, reg.name
        ORDER BY u.full_name
        """,
        tuple(params),
    )
    out = []
    for r in rows:
        if not r["is_active"]:
            estado_calc = "inactivo"
        elif r["last_login_at"] is None:
            estado_calc = "pendiente"
        else:
            estado_calc = "activo"
        out.append({
            "id": r["id"],
            "nombre": r["full_name"],
            "correo": r["email"],
            "roles": r["roles"],
            "estado": estado_calc,
            "ultimo_acceso": r["last_login_at"],
            "institucion": r["institucion"],
            "region": r["region"],
        })
    return out


def valida_usuario(username, email, full_name, es_alta, password=None):
    errores = []
    if es_alta:
        if not username or len(username.strip()) < 3:
            errores.append("El usuario debe tener al menos 3 caracteres.")
        elif len(username.strip()) > 60:
            errores.append("El usuario no puede pasar de 60 caracteres.")
        if not password or len(password) < 8:
            errores.append("La contraseña debe tener al menos 8 caracteres.")
    elif password is not None and password != "" and len(password) < 8:
        errores.append("La contraseña debe tener al menos 8 caracteres.")

    if not full_name or not full_name.strip():
        errores.append("El nombre completo es obligatorio.")
    elif len(full_name.strip()) > 160:
        errores.append("El nombre completo no puede pasar de 160 caracteres.")

    if not email or not RE_EMAIL.match(email.strip()):
        errores.append("El correo no tiene un formato valido.")
    elif len(email.strip()) > 160:
        errores.append("El correo no puede pasar de 160 caracteres.")

    return errores


def dependencias_usuario(user_id):
    out = []
    for tabla, columna, etiqueta in DEPENDENCIAS_RESTRICT:
        row = query(
            f"SELECT count(*) AS n FROM {tabla} WHERE {columna} = %s",
            (user_id,),
            one=True,
        )
        if row["n"]:
            out.append((etiqueta, row["n"]))
    return out


def get_user_roles(user_id):
    filas = query("SELECT r.code FROM roles r JOIN user_roles ur ON ur.role_id = r.id "
                  "WHERE ur.user_id = %s", (user_id,))
    return [r["code"] for r in filas]


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
