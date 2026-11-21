from datetime import datetime, timedelta

from flask import g, request

from epidemia_comun import alcance as alcances, sesiones
from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import get_conn, query
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.redis_compartido import RedisNoDisponible
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo

# Las mismas pantallas del monolito son solo de ADMINISTRADOR (admin_required).
ADMIN = ("ADMINISTRADOR",)
# La bitácora es del ADMINISTRADOR (D1): expone quién hizo qué y desde qué IP en todo el sistema.
EVENTOS, EVENTOS_MAX = 100, 500
# El historial de una entidad es una vista acotada (sin IP) que consultan también quienes
# trabajan los escenarios (D43); la bitácora completa sigue siendo del ADMINISTRADOR.
HISTORIAL = ("ADMINISTRADOR", "EPIDEMIOLOGO", "ANALISTA")
# La región de cada entidad del historial, para aplicar el alcance (D43).
REGION_DE_ENTIDAD = {
    "scenarios": "SELECT region_id FROM scenarios WHERE id = %s",
    "scenario_versions": """SELECT s.region_id FROM scenario_versions sv
                            JOIN scenarios s ON s.id = sv.scenario_id WHERE sv.id = %s""",
    "scenario_interventions": """SELECT s.region_id FROM scenario_interventions si
                                 JOIN scenario_versions sv ON sv.id = si.scenario_version_id
                                 JOIN scenarios s ON s.id = sv.scenario_id WHERE si.id = %s"""}
ENTIDADES_HISTORIAL = tuple(REGION_DE_ENTIDAD)


def _fecha(valor, campo, fin=False):
    if not valor:
        return None
    try:
        fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser una fecha ISO 8601." % campo)
    # Con solo la fecha, to incluye ese día completo; con hora, la cota es exclusiva.
    return fecha + timedelta(days=1) if fin and len(valor) == 10 else fecha


def eventos_bitacora(busqueda=None, usuario_id=None, modulo=None, accion=None, entidad_id=None,
                     desde=None, hasta=None, limite=EVENTOS, desplazamiento=0, con_ip=True):
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
    if entidad_id:
        condiciones.append("a.entity_id = %s")
        params.append(entidad_id)
    if desde:
        condiciones.append("a.occurred_at >= %s")
        params.append(desde)
    if hasta:
        condiciones.append("a.occurred_at < %s")
        params.append(hasta)
    if accion and accion.startswith("RUN::"):
        condiciones.append("a.action = 'RUN' AND a.data_after->>'estado' = %s")
        params.append(accion.split("::", 1)[1])
    elif accion:
        condiciones.append("a.action = %s")
        params.append(accion)
    where = "WHERE " + " AND ".join(condiciones) if condiciones else ""
    de = "FROM audit_log a LEFT JOIN users u ON u.id = a.user_id " + where
    coincidencias = query("SELECT count(*) AS n " + de, tuple(params), one=True)["n"]
    filas = query("""SELECT a.id, a.occurred_at, a.action, a.entity_type, a.entity_id, a.user_id,
                            host(a.ip_address) AS ip, a.data_before, a.data_after, u.full_name AS usuario
                     %s ORDER BY a.occurred_at DESC, a.id DESC LIMIT %%s OFFSET %%s""" % de,
                  tuple(params) + (limite, desplazamiento))
    eventos = [{"id": f["id"], "fecha": f["occurred_at"], "usuario": f["usuario"],
                "usuario_id": f["user_id"], "modulo": f["entity_type"], "accion": f["action"],
                "entidad_id": f["entity_id"], "antes": f["data_before"], "datos": f["data_after"],
                "ip": f["ip"]} for f in filas]
    if not con_ip:
        for e in eventos:
            del e["ip"]
    return eventos, coincidencias


def _paginacion():
    limite, desplazamiento = request.args.get("limit"), request.args.get("offset")
    limite = EVENTOS if limite is None else entero_positivo(limite, "limit")
    if limite > EVENTOS_MAX:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "limit no puede pasar de %d." % EVENTOS_MAX)
    if desplazamiento is not None and not desplazamiento.isdigit():
        raise ErrorAPI(422, "DATOS_INVALIDOS", "offset debe ser un entero de 0 en adelante.")
    return limite, int(desplazamiento or 0)


def _rango():
    desde = _fecha(request.args.get("from"), "from")
    hasta = _fecha(request.args.get("to"), "to", fin=True)
    if desde and hasta and desde >= hasta:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "from debe ser anterior a to.")
    return desde, hasta


def _ids(datos, campo):
    valor = datos.get(campo, [])
    # En XML una lista de un elemento llega como texto y una vacía como "".
    if isinstance(valor, dict) and set(valor) == {"item"}:
        valor = valor["item"]
    if valor in ("", None):
        valor = []
    if not isinstance(valor, list):
        valor = [valor]
    return sorted({entero_positivo(v, campo) for v in valor})


def alcance(user_id):
    # Sin filas la cuenta es nacional (D43). Una región cubre también a sus hijas.
    regiones = [f["region_id"] for f in query(
        "SELECT region_id FROM user_scopes WHERE user_id = %s AND region_id IS NOT NULL"
        " ORDER BY region_id", (user_id,))]
    instituciones = [f["institution_id"] for f in query(
        "SELECT institution_id FROM user_scopes WHERE user_id = %s AND institution_id IS NOT NULL"
        " ORDER BY institution_id", (user_id,))]
    cubiertas = [f["id"] for f in query(
        """WITH RECURSIVE r AS (SELECT id FROM regions WHERE id = ANY(%s)
                                UNION SELECT h.id FROM regions h JOIN r ON h.parent_region_id = r.id)
           SELECT id FROM r ORDER BY id""", (regiones,))] if regiones else []
    return {"user_id": user_id, "nacional": not regiones and not instituciones,
            "region_ids": regiones, "regiones_cubiertas": cubiertas,
            "institution_ids": instituciones}


def catalogo_roles():
    return query("SELECT id, code, name FROM roles ORDER BY name")


def registrar(app):
    @app.errorhandler(RedisNoDisponible)
    def redis_caido(exc):
        return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "Redis no está disponible."))

    @app.get("/api/v1/roles")
    @requiere_token(roles=ADMIN)
    def lista():
        datos = catalogo_roles()
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
        usuario = request.args.get("user_id")
        limite, desplazamiento = _paginacion()
        desde, hasta = _rango()
        eventos, coincidencias = eventos_bitacora(
            busqueda=(request.args.get("q") or "").strip() or None,
            usuario_id=entero_positivo(usuario, "user_id") if usuario else None,
            modulo=request.args.get("module") or None, accion=request.args.get("action") or None,
            entidad_id=request.args.get("entity_id") or None, desde=desde, hasta=hasta,
            limite=limite, desplazamiento=desplazamiento)
        return responder({"total": len(eventos), "coincidencias": coincidencias,
                          "limit": limite, "offset": desplazamiento, "eventos": eventos}, "bitacora")

    @app.get("/api/v1/audit/history/<entity_type>/<int:entity_id>")
    @requiere_token(roles=HISTORIAL)
    def historial(entity_type, entity_id):
        if entity_type not in ENTIDADES_HISTORIAL:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No hay historial para ese tipo de entidad.")
        permitidas = alcances.permitidas(alcance(g.contexto.user_id))
        if permitidas is not None:
            fila = query(REGION_DE_ENTIDAD[entity_type], (entity_id,), one=True)
            if fila and fila["region_id"] not in permitidas:
                raise ErrorAPI(403, "PERMISO_INSUFICIENTE", "El dato está fuera del alcance de tu cuenta.")
        limite, desplazamiento = _paginacion()
        eventos, coincidencias = eventos_bitacora(
            modulo=entity_type, entidad_id=str(entity_id), limite=limite,
            desplazamiento=desplazamiento, con_ip=False)
        return responder({"total": len(eventos), "coincidencias": coincidencias,
                          "limit": limite, "offset": desplazamiento, "eventos": eventos}, "bitacora")

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
                    cerradas = sesiones.cerrar_de_usuario(user_id)
            conn.commit()
        return responder({"user_id": user_id, "role_id": role_id, "sesiones_cerradas": cerradas},
                         "asignacion")

    # Cualquier cuenta consulta su propio alcance; los servicios lo piden con el token de la persona.
    @app.get("/api/v1/scopes/me")
    @requiere_token()
    def alcance_propio():
        return responder(alcance(g.contexto.user_id), "alcance")

    @app.get("/api/v1/scopes/<int:user_id>")
    @requiere_token(roles=ADMIN)
    def alcance_de(user_id):
        if query("SELECT 1 FROM users WHERE id = %s", (user_id,), one=True) is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el usuario.")
        return responder(alcance(user_id), "alcance")

    # Reemplaza el alcance completo; con las dos listas vacías la cuenta vuelve a ser nacional.
    @app.put("/api/v1/scopes/<int:user_id>")
    @requiere_token(roles=ADMIN)
    def asignar_alcance(user_id):
        datos = diccionario(leer_cuerpo())
        if set(datos) - {"region_ids", "institution_ids"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Manda solo region_ids e institution_ids.")
        regiones, instituciones = _ids(datos, "region_ids"), _ids(datos, "institution_ids")
        yo = int(g.usuario["sub"])
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE id = %s FOR UPDATE", (user_id,))
                if cur.fetchone() is None:
                    raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el usuario.")
                for tabla, ids, campo in (("regions", regiones, "region_ids"),
                                          ("institutions", instituciones, "institution_ids")):
                    cur.execute("SELECT count(*) FROM %s WHERE id = ANY(%%s)" % tabla, (ids,))
                    if cur.fetchone()[0] != len(ids):
                        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s trae un id que no existe." % campo)
                antes = {}
                for campo in ("region_ids", "institution_ids"):
                    columna = campo[:-1]
                    cur.execute("SELECT %s FROM user_scopes WHERE user_id = %%s AND %s IS NOT NULL"
                                " ORDER BY 1" % (columna, columna), (user_id,))
                    antes[campo] = [f[0] for f in cur.fetchall()]
                despues = {"region_ids": regiones, "institution_ids": instituciones}
                if antes != despues:
                    cur.execute("DELETE FROM user_scopes WHERE user_id = %s", (user_id,))
                    for region in regiones:
                        cur.execute("INSERT INTO user_scopes (user_id, region_id, assigned_by)"
                                    " VALUES (%s, %s, %s)", (user_id, region, yo))
                    for institucion in instituciones:
                        cur.execute("INSERT INTO user_scopes (user_id, institution_id, assigned_by)"
                                    " VALUES (%s, %s, %s)", (user_id, institucion, yo))
                    log_audit(g.contexto, "UPDATE", "user_scopes", user_id, data_before=antes,
                              data_after=despues, cur=cur)
            conn.commit()
        return responder(alcance(user_id), "alcance")
