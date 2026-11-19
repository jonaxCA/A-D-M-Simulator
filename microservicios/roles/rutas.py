from flask import g, request

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
# La bitácora es del ADMINISTRADOR (D1): expone quién hizo qué y desde qué IP en todo el sistema.
EVENTOS, EVENTOS_MAX = 100, 500


def eventos_bitacora(busqueda=None, usuario_id=None, modulo=None, accion=None, limite=EVENTOS):
    # Las cuatro etapas de una corrida comparten action='RUN' y solo las distingue
    # data_after->>'estado': el filtro acepta RUN::<etapa> para aislar, por ejemplo, las fallidas.
    condiciones, params = [], []
    if busqueda:
        condiciones.append("(u.full_name ILIKE %s OR host(a.ip_address)::text ILIKE %s"
                           " OR a.entity_type ILIKE %s)")
        params += ["%" + busqueda + "%"] * 3
    if usuario_id:
        condiciones.append("a.user_id = %s")
        params.append(usuario_id)
    if modulo:
        condiciones.append("a.entity_type = %s")
        params.append(modulo)
    if accion and accion.startswith("RUN::"):
        condiciones.append("a.action = 'RUN' AND a.data_after->>'estado' = %s")
        params.append(accion.split("::", 1)[1])
    elif accion:
        condiciones.append("a.action = %s")
        params.append(accion)
    where = "WHERE " + " AND ".join(condiciones) if condiciones else ""
    filas = query("""SELECT a.id, a.occurred_at, a.action, a.entity_type, a.entity_id,
                            host(a.ip_address) AS ip, a.data_after, u.full_name AS usuario
                     FROM audit_log a LEFT JOIN users u ON u.id = a.user_id
                     %s ORDER BY a.occurred_at DESC LIMIT %%s""" % where, tuple(params) + (limite,))
    return [{"id": f["id"], "fecha": f["occurred_at"], "usuario": f["usuario"],
             "modulo": f["entity_type"], "accion": f["action"], "entidad_id": f["entity_id"],
             "datos": f["data_after"], "ip": f["ip"]} for f in filas]


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

    @app.get("/api/v1/audit")
    @requiere_token(roles=ADMIN)
    def bitacora():
        usuario, limite = request.args.get("user_id"), request.args.get("limit")
        limite = EVENTOS if limite is None else entero_positivo(limite, "limit")
        if limite > EVENTOS_MAX:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "limit no puede pasar de %d." % EVENTOS_MAX)
        eventos = eventos_bitacora(
            busqueda=(request.args.get("q") or "").strip() or None,
            usuario_id=entero_positivo(usuario, "user_id") if usuario else None,
            modulo=request.args.get("module") or None, accion=request.args.get("action") or None,
            limite=limite)
        return responder({"total": len(eventos), "eventos": eventos}, "bitacora")

    # «Usuarios activos» cuenta quien registró un LOGIN en las últimas 24 horas.
    @app.get("/api/v1/audit/summary")
    @requiere_token(roles=ADMIN)
    def resumen_bitacora():
        fila = query("""SELECT count(*) AS eventos_totales,
                               count(*) FILTER (WHERE action = 'PERMISSION_DENIED') AS criticas,
                               count(*) FILTER (WHERE action = 'LOGIN_FAILED') AS fallidos,
                               count(DISTINCT user_id) FILTER (
                                   WHERE action = 'LOGIN' AND occurred_at >= now() - interval '24 hours'
                               ) AS activos_24h
                        FROM audit_log""", one=True)
        return responder(dict(fila), "resumen_bitacora")

    # Los valores de los filtros: lo que ya aparece en la bitácora.
    @app.get("/api/v1/audit/filters")
    @requiere_token(roles=ADMIN)
    def filtros_bitacora():
        modulos = [f["entity_type"] for f in
                   query("SELECT DISTINCT entity_type FROM audit_log ORDER BY entity_type")]
        acciones = [f["action"] for f in
                    query("SELECT DISTINCT action FROM audit_log WHERE action <> 'RUN' ORDER BY action")]
        acciones += ["RUN::" + f["etapa"] for f in query(
            "SELECT DISTINCT data_after->>'estado' AS etapa FROM audit_log"
            " WHERE action = 'RUN' AND data_after->>'estado' IS NOT NULL ORDER BY 1")]
        usuarios = query("""SELECT DISTINCT u.id, u.full_name FROM users u
                            JOIN audit_log a ON a.user_id = u.id ORDER BY u.full_name""")
        return responder({"modulos": modulos, "acciones": acciones, "usuarios": usuarios},
                         "filtros_bitacora")

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
