"""Servicio intervenciones: intervenciones de una versión en borrador.

Agregar, quitar y reordenar usan las funciones de backend_web.queries (que
auditan dentro de su propia transacción, con el Contexto del token). El costo
se guarda aquí, con la bitácora en la misma transacción, porque
actualiza_costo_intervencion no audita.

El costo vive en el tipo de intervención (intervention_types), como en el
monolito: cambiarlo desde una intervención cambia el costo de todas las de ese
tipo. Lo mismo el factor de personas-día por dosis de la frontera de Pareto (D3,
migración 040), que solo tienen los tipos por dosis.
"""
from flask import g

from backend_web import queries
from backend_web.audit import log_audit
from backend_web.db import get_conn, query
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario

ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
ROLES_COSTO = ("EPIDEMIOLOGO", "ADMINISTRADOR")
CAMPOS = {"code", "start_day", "end_day", "coverage", "compliance", "params"}
DIRECCIONES = {"subir": "subir", "bajar": "bajar", "up": "subir", "down": "bajar"}


def _texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (list, tuple)):
        return ",".join(_texto(v) for v in valor)
    return str(valor)


def _fila(i):
    return {"id": i["id"], "code": i["code"], "name": i["name"],
            "target_layer": i["target_layer"], "start_day": i["start_day"],
            "end_day": i["end_day"], "coverage": i["coverage"],
            "compliance": i["compliance"], "params": i["params"] or {},
            "order_index": i["order_index"]}


def _version(version_id):
    fila = query(
        """SELECT v.id, v.scenario_id, v.version_number, v.status, v.is_current,
                  v.horizon_days, s.owner_id
           FROM scenario_versions v JOIN scenarios s ON s.id = v.scenario_id
           WHERE v.id = %s""", (version_id,), one=True)
    if not fila:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la versión.")
    return dict(fila)


def _intervenciones(version_id):
    return [dict(r) for r in query(
        """SELECT i.id, i.start_day, i.end_day, i.coverage, i.compliance, i.params,
                  i.order_index, t.code, t.name, t.target_layer
           FROM scenario_interventions i
           JOIN intervention_types t ON t.id = i.intervention_type_id
           WHERE i.scenario_version_id = %s
           ORDER BY i.order_index, i.start_day, i.id""", (version_id,))]


def _exige_editable(version):
    """Borrador y vigente (409) y dueño o ADMINISTRADOR (403), como el monolito."""
    if version["status"] != "borrador":
        raise ErrorAPI(409, "CONFLICTO", "Esta versión ya no es un borrador: para cambiar sus "
                       "intervenciones hay que crear una versión nueva.")
    if not version["is_current"]:
        raise ErrorAPI(409, "CONFLICTO", "Solo la versión vigente se puede editar.")
    usuario = g.usuario
    if (str(version["owner_id"]) != str(usuario.get("sub"))
            and "ADMINISTRADOR" not in (usuario.get("roles") or [])):
        raise ErrorAPI(403, "PERMISO_INSUFICIENTE",
                       "Solo quien creó el escenario puede editar sus intervenciones.")


def _formulario(cuerpo, tipos):
    """Del cuerpo JSON/XML a los campos planos (p_<CODE>_<clave>) del monolito."""
    cuerpo = diccionario(cuerpo)
    extra = set(cuerpo) - CAMPOS
    if extra:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Campos desconocidos: " + ", ".join(sorted(extra)) + ".")
    form = {k: _texto(v) for k, v in cuerpo.items() if k != "params"}
    code = form.get("code", "").strip()
    params = cuerpo.get("params")
    if params in (None, ""):
        params = {}
    if not isinstance(params, dict):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "params debe ser un objeto.")
    tipo = next((t for t in tipos if t["code"] == code), None)
    if tipo is not None:
        permitidos = set((tipo["param_schema"] or {}).get("properties") or {})
        desconocidos = set(params) - permitidos
        if desconocidos:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Parámetros no reconocidos para %s: %s." % (
                code, ", ".join(sorted(desconocidos))))
    for clave, valor in params.items():
        if isinstance(valor, dict):
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "El parámetro %s debe ser un valor simple o una lista." % clave)
        form["p_%s_%s" % (code, clave)] = _texto(valor)
    return form


def _valor_con_fuente(campos, nombre):
    """Lee del cuerpo un valor con su fuente y su marca de supuesto (regla 8).

    `campos` son las tres llaves (valor, fuente, supuesto); el resultado las conserva.
    Las reglas son las de queries.valida_costo_intervencion.
    """
    llave_valor, llave_fuente, llave_supuesto = campos
    cuerpo = diccionario(leer_cuerpo())
    if set(cuerpo) - set(campos):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Solo se aceptan %s, %s y %s." % campos)
    supuesto = cuerpo.get(llave_supuesto, False)
    if isinstance(supuesto, str) and supuesto.strip().lower() in ("true", "false", "1", "0"):
        supuesto = supuesto.strip().lower() in ("true", "1")
    if not isinstance(supuesto, bool):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser booleano." % llave_supuesto)
    fuente = cuerpo.get(llave_fuente)
    if fuente is not None and not isinstance(fuente, str):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser texto." % llave_fuente)
    valor = cuerpo.get(llave_valor)
    if isinstance(valor, (bool, dict, list)):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser numerico." % nombre)
    nuevo, errores = queries.valida_costo_intervencion(_texto(valor), fuente, supuesto, nombre=nombre)
    if errores:
        raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
    return dict(zip(campos, (nuevo["unit_cost"], nuevo["cost_source"], nuevo["cost_is_assumption"])))


def _falla(mensaje):
    mensaje = mensaje or "No se pudo completar la operación."
    if "Ya hay" in mensaje:
        raise ErrorAPI(409, "CONFLICTO", mensaje)
    if "ya no está" in mensaje:
        raise ErrorAPI(404, "NO_ENCONTRADO", mensaje)
    raise ErrorAPI(422, "DATOS_INVALIDOS", mensaje)


def registrar(app):
    @app.get("/api/v1/versions/<int:version_id>/interventions")
    @requiere_token(roles=ROLES)
    def listar(version_id):
        version = _version(version_id)
        filas = [_fila(i) for i in _intervenciones(version_id)]
        return responder({
            "version_id": version["id"], "scenario_id": version["scenario_id"],
            "version_number": version["version_number"], "status": version["status"],
            "editable": version["status"] == "borrador" and version["is_current"],
            "total": len(filas), "intervenciones": filas}, "intervenciones_version")

    @app.post("/api/v1/versions/<int:version_id>/interventions")
    @requiere_token(roles=ROLES)
    def agregar(version_id):
        version = _version(version_id)
        _exige_editable(version)
        tipos = queries.get_tipos_intervencion()
        form = _formulario(leer_cuerpo(), tipos)
        datos, errores = queries.valida_intervencion(
            form, tipos, version, _intervenciones(version_id))
        if errores:
            if any(e.startswith("Ya hay una intervención") for e in errores):
                raise ErrorAPI(409, "CONFLICTO", " ".join(errores))
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        ok, error = queries.agrega_intervencion(version_id, datos, contexto=g.contexto)
        if not ok:
            _falla(error)
        # La recién agregada queda al final del orden de la versión.
        ultima = _intervenciones(version_id)[-1]
        return responder(_fila(ultima), "intervencion", estado=201)

    @app.delete("/api/v1/versions/<int:version_id>/interventions/<int:intervention_id>")
    @requiere_token(roles=ROLES)
    def quitar(version_id, intervention_id):
        _exige_editable(_version(version_id))
        ok, error = queries.quita_intervencion(version_id, intervention_id, contexto=g.contexto)
        if not ok:
            _falla(error)
        return responder({"id": intervention_id, "eliminada": True}, "intervencion")

    @app.post("/api/v1/versions/<int:version_id>/interventions/<int:intervention_id>/move")
    @requiere_token(roles=ROLES)
    def mover(version_id, intervention_id):
        cuerpo = diccionario(leer_cuerpo())
        if set(cuerpo) - {"direction"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Solo se acepta direction.")
        direccion = DIRECCIONES.get(str(cuerpo.get("direction")).strip().lower())
        if direccion is None:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "direction debe ser subir o bajar (o up o down).")
        _exige_editable(_version(version_id))
        ok, error = queries.mueve_intervencion(version_id, intervention_id, direccion,
                                               contexto=g.contexto)
        if not ok and error:
            _falla(error)
        # Sin error y sin movimiento: ya estaba en el extremo, no es falla.
        return responder({"id": intervention_id, "direction": direccion, "movida": ok},
                         "intervencion")

    @app.put("/api/v1/versions/<int:version_id>/interventions/<int:intervention_id>/cost")
    @requiere_token(roles=ROLES_COSTO)
    def costo(version_id, intervention_id):
        nuevo = _valor_con_fuente(("unit_cost", "cost_source", "cost_is_assumption"), "El importe")
        _version(version_id)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT t.id, t.unit_cost, t.cost_source, t.cost_is_assumption
                       FROM scenario_interventions i
                       JOIN intervention_types t ON t.id = i.intervention_type_id
                       WHERE i.id = %s AND i.scenario_version_id = %s AND t.is_active
                       FOR UPDATE OF t""", (intervention_id, version_id))
                fila = cur.fetchone()
                if fila is None:
                    raise ErrorAPI(404, "NO_ENCONTRADO", "Esa intervención no está en esta versión.")
                tipo_id = fila[0]
                antes = {"unit_cost": fila[1], "cost_source": fila[2],
                         "cost_is_assumption": fila[3]}
                cur.execute(
                    """UPDATE intervention_types
                       SET unit_cost = %s, cost_source = %s, cost_is_assumption = %s
                       WHERE id = %s AND is_active""",
                    (nuevo["unit_cost"], nuevo["cost_source"],
                     nuevo["cost_is_assumption"], tipo_id))
                log_audit(g.contexto, "UPDATE", "intervention_types", tipo_id,
                          data_before=antes, data_after=nuevo, cur=cur)
            conn.commit()
        return responder({"id": intervention_id, "intervention_type_id": tipo_id, **nuevo},
                         "costo_intervencion")

    # El mismo costo, fijado desde el catálogo de tipos y sin pasar por una versión: la
    # pantalla de costos de la web (D36).
    @app.put("/api/v1/intervention-types/<int:type_id>/cost")
    @requiere_token(roles=ROLES_COSTO)
    def costo_de_tipo(type_id):
        nuevo = _valor_con_fuente(("unit_cost", "cost_source", "cost_is_assumption"), "El importe")
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT unit_cost, cost_source, cost_is_assumption
                               FROM intervention_types WHERE id = %s AND is_active
                               FOR UPDATE""", (type_id,))
                fila = cur.fetchone()
                if fila is None:
                    raise ErrorAPI(404, "NO_ENCONTRADO", "No existe ese tipo de intervención activo.")
                antes = dict(zip(("unit_cost", "cost_source", "cost_is_assumption"), fila))
                cur.execute("""UPDATE intervention_types
                               SET unit_cost = %s, cost_source = %s, cost_is_assumption = %s
                               WHERE id = %s""",
                            (nuevo["unit_cost"], nuevo["cost_source"], nuevo["cost_is_assumption"],
                             type_id))
                log_audit(g.contexto, "UPDATE", "intervention_types", type_id,
                          data_before=antes, data_after=nuevo, cur=cur)
            conn.commit()
        return responder({"intervention_type_id": type_id, **nuevo}, "costo_tipo")

    @app.put("/api/v1/versions/<int:version_id>/interventions/<int:intervention_id>/person-days")
    @requiere_token(roles=ROLES_COSTO)
    def personas_dia(version_id, intervention_id):
        # Personas-día que cuenta cada dosis en la frontera de Pareto (D3). Las capas y el
        # testeo las cuentan por definición, así que solo lo tienen los tipos por dosis.
        nuevo = _valor_con_fuente(("person_days_per_unit", "person_days_source",
                                   "person_days_is_assumption"), "El factor de personas-dia")
        _version(version_id)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT t.id, t.cost_unit, t.person_days_per_unit, t.person_days_source,
                              t.person_days_is_assumption
                       FROM scenario_interventions i
                       JOIN intervention_types t ON t.id = i.intervention_type_id
                       WHERE i.id = %s AND i.scenario_version_id = %s AND t.is_active
                       FOR UPDATE OF t""", (intervention_id, version_id))
                fila = cur.fetchone()
                if fila is None:
                    raise ErrorAPI(404, "NO_ENCONTRADO", "Esa intervención no está en esta versión.")
                tipo_id, unidad = fila[0], fila[1]
                if unidad != "por_dosis":
                    raise ErrorAPI(422, "DATOS_INVALIDOS",
                                   "Solo los tipos por dosis llevan factor: las demás "
                                   "intervenciones cuentan sus personas-día por definición.")
                antes = {"person_days_per_unit": fila[2], "person_days_source": fila[3],
                         "person_days_is_assumption": fila[4]}
                cur.execute(
                    """UPDATE intervention_types
                       SET person_days_per_unit = %s, person_days_source = %s,
                           person_days_is_assumption = %s
                       WHERE id = %s AND is_active""",
                    (nuevo["person_days_per_unit"], nuevo["person_days_source"],
                     nuevo["person_days_is_assumption"], tipo_id))
                log_audit(g.contexto, "UPDATE", "intervention_types", tipo_id,
                          data_before=antes, data_after=nuevo, cur=cur)
            conn.commit()
        return responder({"id": intervention_id, "intervention_type_id": tipo_id, **nuevo},
                         "factor_personas_dia")
