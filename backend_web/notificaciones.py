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

# Los del CHECK ck_notifications_type (003, 029, 037, 057 y 060).
TIPOS = ("RUN_FINISHED", "RUN_FAILED", "THRESHOLD_EXCEEDED", "ASSIGNMENT",
         "SCENARIO_PUBLISHED", "SCENARIO_APPROVED", "SCENARIO_SUBMITTED",
         "SCENARIO_REJECTED", "NEW_CASES", "SYSTEM", "CASE_REJECTED", "CAMPAIGN",
         "DATA_INCOMPLETE")
# Los avisos que de verdad le llegan a cada perfil (D49): son los que puede apagar. SYSTEM, las
# alertas técnicas del ADMINISTRADOR, no se apaga.
TIPOS_POR_ROL = {
    "CAPTURISTA": ("CASE_REJECTED", "DATA_INCOMPLETE", "CAMPAIGN"),
    "EPIDEMIOLOGO": ("NEW_CASES", "SCENARIO_SUBMITTED"),
    "ANALISTA": ("RUN_FINISHED", "RUN_FAILED", "SCENARIO_APPROVED", "SCENARIO_REJECTED"),
    "ADMINISTRADOR": ("SYSTEM", "RUN_FINISHED", "RUN_FAILED", "SCENARIO_APPROVED",
                      "SCENARIO_REJECTED"),
}
FIJOS = ("SYSTEM",)
NOMBRES = {"RUN_FINISHED": "Corrida terminada", "RUN_FAILED": "Corrida con error",
           "SCENARIO_APPROVED": "Versión aprobada", "SCENARIO_SUBMITTED": "Versión por revisar",
           "SCENARIO_REJECTED": "Versión rechazada", "NEW_CASES": "Casos nuevos",
           "SYSTEM": "Alertas técnicas", "CASE_REJECTED": "Caso descartado",
           "CAMPAIGN": "Campañas", "DATA_INCOMPLETE": "Datos incompletos"}
TITULO_MAX = 160
_COLUMNAS = "id, user_id, type, title, body, payload, read_at, created_at"


def valida_notificacion(datos, *, a_rol=False):
    """Lista de errores en español; vacia si se puede guardar."""
    errores = []
    usuario = datos.get("user_id")
    if not a_rol and (isinstance(usuario, bool) or not isinstance(usuario, int) or usuario < 1):
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
    """Devuelve (id, error). (None, None): la persona apagó ese tipo de aviso (D49) y no se crea."""
    errores = valida_notificacion(datos)
    if errores:
        return None, " ".join(errores)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT enabled FROM notification_preferences WHERE user_id = %s AND type = %s",
                            (datos["user_id"], datos["type"]))
                preferencia = cur.fetchone()
                if preferencia is not None and not preferencia[0]:
                    return None, None
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


def crear_notificaciones_a_rol(datos, rol, *, contexto):
    errores = valida_notificacion(datos, a_rol=True)
    if errores:
        return None, " ".join(errores)
    ids = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Sin quienes apagaron ese tipo de aviso (D49).
            cur.execute(
                """SELECT u.id FROM users u
                   JOIN user_roles ur ON ur.user_id = u.id
                   JOIN roles r ON r.id = ur.role_id
                   WHERE r.code = %s AND u.is_active
                     AND NOT EXISTS (SELECT 1 FROM notification_preferences p
                                     WHERE p.user_id = u.id AND p.type = %s AND NOT p.enabled)
                   ORDER BY u.id""", (rol, datos["type"]))
            for (user_id,) in cur.fetchall():
                cur.execute(
                    """INSERT INTO notifications (user_id, type, title, body, payload)
                       VALUES (%s, %s, %s, %s, %s::jsonb) RETURNING id""",
                    (user_id, datos["type"], datos["title"].strip(),
                     datos.get("body"), a_jsonb(datos.get("payload"))))
                ids.append(cur.fetchone()[0])
                log_audit(contexto, "CREATE", "notifications", ids[-1],
                          data_after={"user_id": user_id, "type": datos["type"],
                                      "title": datos["title"].strip()},
                          cur=cur)
        conn.commit()
    return ids, None


def tipos_de(roles):
    """Los tipos de aviso que le tocan a quien tiene esos roles, en orden."""
    return [t for t in TIPOS if any(t in TIPOS_POR_ROL.get(r, ()) for r in roles)]


def preferencias(user_id, roles):
    """[{type, nombre, enabled, fijo}] de los tipos que le tocan; sin fila, prendido."""
    tipos = tipos_de(roles)
    filas = query("SELECT type, enabled FROM notification_preferences WHERE user_id = %s", (user_id,))
    apagados = {f["type"] for f in filas if not f["enabled"]}
    return [{"type": t, "nombre": NOMBRES.get(t, t), "enabled": t not in apagados, "fijo": t in FIJOS}
            for t in tipos]


def guarda_preferencias(user_id, cambios, *, contexto):
    """cambios: {tipo: bool}, ya validados. Una fila por tipo, en una transacción."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            for tipo, prendido in cambios.items():
                cur.execute(
                    """INSERT INTO notification_preferences (user_id, type, enabled)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (user_id, type) DO UPDATE SET enabled = EXCLUDED.enabled,
                                                                 updated_at = now()""",
                    (user_id, tipo, prendido))
            log_audit(contexto, "UPDATE", "notification_preferences", user_id,
                      data_after=cambios, cur=cur)
        conn.commit()


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
