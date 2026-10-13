from flask import g

from backend_web import queries
from backend_web.audit import log_audit
from backend_web.db import get_conn, query
from epidemia_comun import sesiones
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.redis_compartido import RedisNoDisponible
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo

# Las mismas pantallas del monolito son solo de ADMINISTRADOR (admin_required).
ADMIN = ("ADMINISTRADOR",)


def registrar(app):
    @app.errorhandler(RedisNoDisponible)
    def redis_caido(exc):
        return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "Redis no está disponible."))

    @app.get("/api/v1/roles")
    @requiere_token(roles=ADMIN)
    def lista():
        datos = queries.get_roles_catalogo()
        return responder({"total": len(datos), "roles": datos}, "catalogo_roles")

    @app.get("/api/v1/roles/<int:role_id>/permissions")
    @requiere_token(roles=ADMIN)
    def permisos(role_id):
        rol = query("SELECT id, code, name FROM roles WHERE id = %s", (role_id,), one=True)
        if rol is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el rol.")
        filas = query("""SELECT p.code, p.resource, p.action, p.description
                         FROM role_permissions rp JOIN permissions p ON p.id = rp.permission_id
                         WHERE rp.role_id = %s ORDER BY p.code""", (role_id,))
        return responder({**rol, "permisos": filas}, "rol")

    # Un rol por cuenta, como en el monolito ("un solo rol por usuario en esta versión").
    @app.put("/api/v1/roles/assignments/<int:user_id>")
    @requiere_token(roles=ADMIN)
    def asignar(user_id):
        datos = diccionario(leer_cuerpo())
        if set(datos) != {"role_id"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Manda solo role_id: cada cuenta tiene un rol.")
        role_id = entero_positivo(datos["role_id"], "role_id")
        yo = int(g.usuario["sub"])
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE id = %s", (user_id,))
                if cur.fetchone() is None:
                    raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el usuario.")
                cur.execute("SELECT code FROM roles WHERE id = %s", (role_id,))
                rol = cur.fetchone()
                if rol is None:
                    raise ErrorAPI(422, "DATOS_INVALIDOS", "No existe el rol.")
                if user_id == yo and rol[0] != "ADMINISTRADOR":
                    raise ErrorAPI(409, "CONFLICTO",
                                   "No puedes quitarte a ti mismo el rol de administrador.")
                cur.execute("SELECT role_id FROM user_roles WHERE user_id = %s ORDER BY role_id FOR UPDATE",
                            (user_id,))
                antes = [fila[0] for fila in cur.fetchall()]
                cerradas = 0
                if antes != [role_id]:
                    cur.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
                    cur.execute("INSERT INTO user_roles (user_id, role_id, assigned_by) VALUES (%s, %s, %s)",
                                (user_id, role_id, yo))
                    log_audit(g.contexto, "UPDATE", "users", user_id, data_before={"role_ids": antes},
                              data_after={"role_ids": [role_id]}, cur=cur)
                    # Los access llevan los roles con que se emitieron: hay que volver a entrar.
                    cerradas = sesiones.cerrar_todas(user_id)
            conn.commit()
        return responder({"user_id": user_id, "role_id": role_id, "sesiones_cerradas": cerradas},
                         "asignacion")
