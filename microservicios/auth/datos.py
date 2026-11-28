import bcrypt

from epidemia_comun.bd import execute, get_conn, query

INTENTOS_MAXIMOS = 5
MINUTOS_BLOQUEO = 15
MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos."


def find_user_by_login(username_or_email):
    # No hay columna de bloqueo: updated_at es la hora del último fallo mientras el contador está en el tope.
    return query(
        """
        SELECT id, username, email, full_name, password_hash, is_active,
               failed_attempts,
               (failed_attempts >= %s
                AND updated_at > now() - make_interval(mins => %s)) AS bloqueada
        FROM users
        WHERE lower(username) = lower(%s) OR lower(email) = lower(%s)
        """,
        (INTENTOS_MAXIMOS, MINUTOS_BLOQUEO, username_or_email, username_or_email),
        one=True,
    )


def get_user_roles(user_id):
    filas = query("SELECT r.code FROM roles r JOIN user_roles ur ON ur.role_id = r.id "
                  "WHERE ur.user_id = %s", (user_id,))
    return [r["code"] for r in filas]


def check_password(password, password_hash):
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _registra_fallo(user_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET failed_attempts = LEAST(failed_attempts + 1, 100) "
                        "WHERE id = %s RETURNING failed_attempts", (user_id,))
            fila = cur.fetchone()
        conn.commit()
    return fila[0] if fila else 0


def _mensaje_bloqueo():
    return ("Demasiados intentos fallidos. La cuenta quedó bloqueada; "
            "intenta de nuevo en %d minutos." % MINUTOS_BLOQUEO)


def attempt_login(username_or_email, password):
    # Una cuenta bloqueada se rechaza antes de revisar la contraseña.
    user = find_user_by_login(username_or_email)
    if not user:
        return None, MENSAJE_CREDENCIALES
    if user["bloqueada"]:
        return None, _mensaje_bloqueo()
    if not user["is_active"]:
        return None, "Esta cuenta esta inactiva."
    if not check_password(password, user["password_hash"]):
        if _registra_fallo(user["id"]) >= INTENTOS_MAXIMOS:
            return None, _mensaje_bloqueo()
        return None, MENSAJE_CREDENCIALES
    execute("UPDATE users SET last_login_at = now(), failed_attempts = 0 WHERE id = %s",
            (user["id"],))
    return {"id": user["id"], "username": user["username"], "full_name": user["full_name"],
            "roles": get_user_roles(user["id"])}, None
