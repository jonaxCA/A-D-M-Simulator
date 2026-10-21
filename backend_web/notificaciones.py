"""
Avisos para las apps: la tabla notifications (migraciones 003 y 029).

La escribe solo el microservicio notificaciones; el monolito no los muestra.
Las funciones que escriben reciben el Contexto y auditan con el cursor de su
propia transaccion, como el resto de la capa de datos.
"""
import psycopg2.errors
import psycopg2.extras

from .audit import log_audit
from .db import a_jsonb, get_conn, query

# Los del CHECK ck_notifications_type (003, con SCENARIO_APPROVED desde la 029).
TIPOS = ("RUN_FINISHED", "RUN_FAILED", "THRESHOLD_EXCEEDED", "ASSIGNMENT",
         "SCENARIO_PUBLISHED", "SCENARIO_APPROVED", "SYSTEM")
TITULO_MAX = 160
_COLUMNAS = "id, user_id, type, title, body, payload, read_at, created_at"


def valida_notificacion(datos):
    """Lista de errores en español; vacia si se puede guardar."""
    errores = []
    usuario = datos.get("user_id")
    if isinstance(usuario, bool) or not isinstance(usuario, int) or usuario < 1:
        errores.append("user_id debe ser el id de un usuario.")
    if datos.get("type") not in TIPOS:
        errores.append("type debe ser uno de: %s." % ", ".join(TIPOS))
    titulo = datos.get("title")
    if not isinstance(titulo, str) or not titulo.strip():
        errores.append("title es obligatorio.")
    elif len(titulo.strip()) > TITULO_MAX:
        errores.append("title no puede pasar de %d caracteres." % TITULO_MAX)
    if datos.get("body") is not None and not isinstance(datos["body"], str):
        errores.append("body debe ser texto.")
    if datos.get("payload") is not None and not isinstance(datos["payload"], dict):
        errores.append("payload debe ser un objeto.")
    return errores


def crear_notificacion(datos, *, contexto):
    """Devuelve (id, error)."""
    errores = valida_notificacion(datos)
    if errores:
        return None, " ".join(errores)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO notifications (user_id, type, title, body, payload)
                       VALUES (%s, %s, %s, %s, %s::jsonb) RETURNING id""",
                    (datos["user_id"], datos["type"], datos["title"].strip(),
                     datos.get("body"), a_jsonb(datos.get("payload"))))
                notificacion_id = cur.fetchone()[0]
                log_audit(contexto, "CREATE", "notifications", notificacion_id,
                          data_after={"user_id": datos["user_id"], "type": datos["type"],
                                      "title": datos["title"].strip()},
                          cur=cur)
            conn.commit()
    except psycopg2.errors.ForeignKeyViolation:
        return None, "No existe el usuario destinatario."
    return notificacion_id, None


def listar_notificaciones(user_id, solo_no_leidas=False, limite=50):
    """Las mas recientes de una persona y cuantas tiene sin leer en total."""
    filtro = "AND read_at IS NULL" if solo_no_leidas else ""
    filas = query(
        f"""SELECT {_COLUMNAS},
                   count(*) FILTER (WHERE read_at IS NULL) OVER () AS no_leidas
            FROM notifications
            WHERE user_id = %s {filtro}
            ORDER BY created_at DESC, id DESC
            LIMIT %s""",
        (user_id, limite))
    no_leidas = filas[0]["no_leidas"] if filas else 0
    return [{k: v for k, v in f.items() if k != "no_leidas"} for f in filas], no_leidas


def marcar_leida(notificacion_id, user_id, *, contexto):
    """Devuelve (notificacion, error). Marcar una ya leida no cambia nada; la
    de otra persona no existe para quien pregunta."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""UPDATE notifications SET read_at = now()
                    WHERE id = %s AND user_id = %s AND read_at IS NULL
                    RETURNING {_COLUMNAS}""",
                (notificacion_id, user_id))
            fila = cur.fetchone()
            if fila:
                log_audit(contexto, "UPDATE", "notifications", notificacion_id,
                          data_before={"read_at": None},
                          data_after={"read_at": fila["read_at"].isoformat()}, cur=cur)
            else:
                cur.execute(f"SELECT {_COLUMNAS} FROM notifications WHERE id = %s AND user_id = %s",
                            (notificacion_id, user_id))
                fila = cur.fetchone()
        conn.commit()
    if not fila:
        return None, "No existe la notificación."
    return dict(fila), None
