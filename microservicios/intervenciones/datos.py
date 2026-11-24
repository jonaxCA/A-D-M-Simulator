# Alta, baja y orden de las intervenciones de una versión (antes en backend_web.queries, E8). Cada
# escritura y su bitácora van en la misma transacción. Regresan (ok, error) como en el monolito.
import psycopg2

from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import a_jsonb, get_conn, query


def tipos():
    """Tipos activos, con el esquema que describe sus parámetros."""
    return [dict(r) for r in query(
        """SELECT id, code, name, description, target_layer, primitive, param_schema,
                  unit_cost, cost_unit, cost_source, cost_is_assumption,
                  person_days_per_unit, person_days_source, person_days_is_assumption
           FROM intervention_types WHERE is_active ORDER BY name""")]


def agrega(version_id, datos, *, contexto):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT COALESCE(max(order_index), -1) + 1
                               FROM scenario_interventions WHERE scenario_version_id = %s""",
                            (version_id,))
                orden = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO scenario_interventions
                           (scenario_version_id, intervention_type_id, start_day, end_day,
                            coverage, compliance, params, order_index)
                       VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                       RETURNING id""",
                    (version_id, datos["intervention_type_id"], datos["start_day"], datos["end_day"],
                     datos["coverage"], datos["compliance"], a_jsonb(datos["params"] or {}), orden))
                iid = cur.fetchone()[0]
                log_audit(contexto, "CREATE", "scenario_interventions", iid,
                          data_after={**datos, "scenario_version_id": version_id, "order_index": orden},
                          cur=cur)
            conn.commit()
        return True, None
    except psycopg2.errors.UniqueViolation:
        return False, "Ya hay una intervención de ese tipo que empieza ese mismo día en esta versión."
    except psycopg2.errors.CheckViolation as exc:
        return False, "Los datos no cumplen las restricciones de la base: %s" % exc


def quita(version_id, intervention_id, *, contexto):
    # Renumera para que el orden no quede con huecos: mover «una posición» sigue siendo predecible.
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT i.id, i.start_day, i.end_day, i.coverage, i.compliance,
                              i.params, i.order_index, t.code
                       FROM scenario_interventions i
                       JOIN intervention_types t ON t.id = i.intervention_type_id
                       WHERE i.id = %s AND i.scenario_version_id = %s
                       FOR UPDATE OF i""", (intervention_id, version_id))
                fila = cur.fetchone()
                if not fila:
                    return False, "Esa intervención ya no está en esta versión."
                antes = dict(zip(("id", "start_day", "end_day", "coverage", "compliance", "params",
                                  "order_index", "code"), fila))
                cur.execute("DELETE FROM scenario_interventions WHERE id = %s", (intervention_id,))
                cur.execute("""UPDATE scenario_interventions SET order_index = order_index - 1
                               WHERE scenario_version_id = %s AND order_index > %s""",
                            (version_id, antes["order_index"]))
                log_audit(contexto, "DELETE", "scenario_interventions", intervention_id,
                          data_before=antes, cur=cur)
            conn.commit()
        return True, None
    except psycopg2.errors.CheckViolation as exc:
        return False, "No se pudo quitar: %s" % exc


def mueve(version_id, intervention_id, direccion, *, contexto):
    # Sube o baja una posición, intercambiándola con su vecina. En el extremo: (False, None).
    if direccion not in ("subir", "bajar"):
        return False, "Dirección de movimiento inválida."
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT id, order_index FROM scenario_interventions
                               WHERE scenario_version_id = %s ORDER BY order_index, start_day, id
                               FOR UPDATE""", (version_id,))
                posiciones = [f[0] for f in cur.fetchall()]
                if intervention_id not in posiciones:
                    return False, "Esa intervención ya no está en esta versión."
                i = posiciones.index(intervention_id)
                j = i - 1 if direccion == "subir" else i + 1
                if not 0 <= j < len(posiciones):
                    return False, None
                posiciones[i], posiciones[j] = posiciones[j], posiciones[i]
                for nuevo, iid in enumerate(posiciones):
                    cur.execute("UPDATE scenario_interventions SET order_index = %s WHERE id = %s",
                                (nuevo, iid))
                log_audit(contexto, "UPDATE", "scenario_interventions", intervention_id,
                          data_before={"order_index": i}, data_after={"order_index": j}, cur=cur)
            conn.commit()
        return True, None
    except psycopg2.errors.CheckViolation as exc:
        return False, "No se pudo reordenar: %s" % exc
