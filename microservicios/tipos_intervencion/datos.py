# El catálogo de tipos de intervención y sus supuestos de efectividad (intervention_effectiveness,
# 042, D58). La lectura del catálogo vivía en backend_web.queries.get_tipos_intervencion (E8); el
# costo lo sigue escribiendo intervenciones.
import psycopg2.extras

from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import get_conn, query
from epidemia_comun.errores import ErrorAPI

_EFECTIVIDAD = """
    SELECT e.parameter AS parametro, d.code AS enfermedad, e.reference_value AS valor,
           e.range_min AS min, e.range_max AS max, e.source AS fuente, e.is_assumption AS supuesto,
           e.updated_by, e.updated_at
    FROM intervention_effectiveness e
    LEFT JOIN diseases d ON d.id = e.disease_id
    WHERE e.intervention_type_id = %s"""


def tipos():
    """Tipos activos, con el esquema que describe sus parámetros."""
    return [dict(r) for r in query(
        """SELECT id, code, name, description, target_layer, primitive, param_schema,
                  unit_cost, cost_unit, cost_source, cost_is_assumption,
                  person_days_per_unit, person_days_source, person_days_is_assumption
           FROM intervention_types WHERE is_active ORDER BY name""")]


def efectividad(type_id):
    # La general primero (enfermedad NULL) y luego por enfermedad.
    return [dict(f) for f in query(_EFECTIVIDAD + " ORDER BY e.parameter, d.code NULLS FIRST", (type_id,))]


def enfermedad_id(codigo):
    fila = query("SELECT id FROM diseases WHERE code = %s", (codigo,), one=True)
    return fila["id"] if fila else None


def guarda_efectividad(type_id, parametro, disease_id, valores, *, contexto):
    """Crea o reemplaza el supuesto de (tipo, parámetro, enfermedad). Regresa si era nuevo."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""SELECT id, reference_value, range_min, range_max, source, is_assumption
                           FROM intervention_effectiveness
                           WHERE intervention_type_id = %s AND parameter = %s
                             AND disease_id IS NOT DISTINCT FROM %s FOR UPDATE""",
                        (type_id, parametro, disease_id))
            antes = cur.fetchone()
            columnas = (valores["valor"], valores["min"], valores["max"], valores["fuente"],
                        valores["supuesto"], contexto.user_id)
            if antes is None:
                cur.execute("""INSERT INTO intervention_effectiveness
                                   (intervention_type_id, parameter, disease_id, reference_value, range_min,
                                    range_max, source, is_assumption, updated_by)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                            (type_id, parametro, disease_id) + columnas)
                entity_id = cur.fetchone()["id"]
            else:
                entity_id = antes["id"]
                cur.execute("""UPDATE intervention_effectiveness
                               SET reference_value = %s, range_min = %s, range_max = %s, source = %s,
                                   is_assumption = %s, updated_by = %s, updated_at = now()
                               WHERE id = %s""", columnas + (entity_id,))
            previos = None if antes is None else {
                k: antes[k] for k in ("reference_value", "range_min", "range_max", "source", "is_assumption")}
            log_audit(contexto, "CREATE" if antes is None else "UPDATE", "intervention_effectiveness", entity_id,
                      data_before=previos,
                      data_after=dict(valores, intervention_type_id=type_id, parametro=parametro,
                                      disease_id=disease_id), cur=cur)
        conn.commit()
    return antes is None


def efectividad_de(type_id, parametro, disease_id):
    fila = query(_EFECTIVIDAD + " AND e.parameter = %s AND e.disease_id IS NOT DISTINCT FROM %s",
                 (type_id, parametro, disease_id), one=True)
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe ese supuesto de efectividad.")
    return dict(fila)
