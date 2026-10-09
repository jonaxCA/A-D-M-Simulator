"""
Autenticacion real contra la tabla users. JWT (PyJWT) guardado en una cookie
httponly.

El secreto que firma los tokens sale SOLO de JWT_SECRET_KEY. No hay valor por
omision: con uno fijo en el codigo, cualquiera que lea el repositorio puede
fabricar un token de ADMINISTRADOR. Sin la variable, la app no arranca.
"""
import os
import datetime
import bcrypt
import jwt

from .db import execute, get_conn, query

TOKEN_TTL_MINUTES = 60 * 8  # 8 horas

# Valores que alguna vez vivieron en el codigo, en .env.example o en
# docs/INSTALACION.md. Si llegan aqui es que alguien copio la plantilla sin
# cambiarla: se tratan como si faltara el secreto.
_SECRETOS_DE_EJEMPLO = {
    "dev-secret-cambiar-en-despliegue",
    "CAMBIAR_POR_UNA_CADENA_LARGA_Y_ALEATORIA",
    "pon-aqui-cualquier-cadena-larga-y-aleatoria",
}

# Bloqueo por intentos fallidos. Al llegar a INTENTOS_MAXIMOS la cuenta queda
# bloqueada MINUTOS_BLOQUEO minutos contados desde el ultimo fallo.
INTENTOS_MAXIMOS = 5
MINUTOS_BLOQUEO = 15

MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos."


def secreto_jwt():
    """El secreto de firma, o RuntimeError si no esta configurado.

    Se lee en cada llamada y no al importar: asi el error aparece con un
    mensaje claro al arrancar la app (create_app lo pide) y no como un
    KeyError en medio de una peticion.
    """
    secreto = (os.environ.get("JWT_SECRET_KEY") or "").strip()
    if not secreto or secreto in _SECRETOS_DE_EJEMPLO:
        raise RuntimeError(
            "Falta JWT_SECRET_KEY en el archivo .env (o sigue con el valor de "
            "ejemplo). Genera uno con: "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    return secreto


def find_user_by_login(username_or_email):
    """La cuenta, con `bloqueada` ya calculado por la base.

    No hay columna de bloqueo: se usa `updated_at`, que el trigger
    tg_users_updated_at pone en now() en cada UPDATE. Mientras el contador
    esta en el tope, lo unico que toca la fila es el siguiente fallo (un
    acierto pone el contador en 0), asi que `updated_at` es la hora del
    ultimo intento fallido. Si un administrador edita la cuenta durante el
    bloqueo, este se extiende hasta 15 minutos desde esa edicion.
    """
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
    rows = query(
        """
        SELECT r.code FROM roles r
        JOIN user_roles ur ON ur.role_id = r.id
        WHERE ur.user_id = %s
        """,
        (user_id,),
    )
    return [r["code"] for r in rows]


def check_password(password, password_hash):
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # password_hash invalido/marcador (p.ej. el admin sin hash real todavia)
        return False


def _mensaje_bloqueo():
    return (f"Demasiados intentos fallidos. La cuenta quedó bloqueada; "
            f"intenta de nuevo en {MINUTOS_BLOQUEO} minutos.")


def _registra_fallo(user_id):
    """Suma un intento fallido y devuelve el total. El tope 100 es el de
    ck_users_intentos. No usa query(): esa no hace commit, y el UPDATE se
    perderia al cerrar la conexion."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users SET failed_attempts = LEAST(failed_attempts + 1, 100)
                WHERE id = %s
                RETURNING failed_attempts
                """,
                (user_id,),
            )
            fila = cur.fetchone()
        conn.commit()
    return fila[0] if fila else 0


def attempt_login(username_or_email, password):
    """Devuelve (user_dict, error_message). user_dict es None si fallo.

    Una cuenta bloqueada se rechaza ANTES de revisar la contraseña: si la
    contraseña correcta la desbloqueara, el bloqueo no frenaria a quien la
    esta adivinando.
    """
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
    roles = get_user_roles(user["id"])
    return {
        "id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "roles": roles,
    }, None


def usuario_vigente(payload):
    """Revalida contra la base un token cuya firma ya se verifico.

    El JWT dura 8 horas y trae los roles con los que se emitio. Sin esta
    consulta, desactivar una cuenta o quitarle un rol no surtia efecto hasta
    que el token vencia. Devuelve el usuario con los datos y roles de HOY, o
    None si la cuenta ya no existe o esta inactiva.

    `sub` viaja como cadena en el token (RFC 7519; PyJWT >= 2.10 rechaza un
    entero), pero la app lo compara con ids de la base: aqui vuelve a ser int.
    """
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    fila = query(
        """
        SELECT u.id, u.username, u.full_name, u.is_active,
               array_remove(array_agg(r.code ORDER BY r.code), NULL) AS roles
        FROM users u
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        LEFT JOIN roles r ON r.id = ur.role_id
        WHERE u.id = %s
        GROUP BY u.id
        """,
        (user_id,),
        one=True,
    )
    if not fila or not fila["is_active"]:
        return None
    return {**payload, "sub": fila["id"], "username": fila["username"],
            "full_name": fila["full_name"], "roles": list(fila["roles"])}


def create_token(user):
    ahora = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "full_name": user["full_name"],
        "roles": user["roles"],
        "exp": ahora + datetime.timedelta(minutes=TOKEN_TTL_MINUTES),
        "iat": ahora,
    }
    return jwt.encode(payload, secreto_jwt(), algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, secreto_jwt(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
