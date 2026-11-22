"""Las series de la pantalla de Monitoreo y los catálogos que revisan sus filtros.

Copia de las de backend_web.queries: la web todavía las usa (D36) y la regla es de este
servicio (E8, docs/arquitectura/duenos_de_reglas.md). Mientras las dos existan deben ser
iguales: microservicios/comun/tests/test_copias_del_monolito.py lo revisa.
"""
from epidemia_comun.bd import query

NL_ESTADO_CODE = "19"


def _pct_change(actual, previa):
    if previa == 0:
        return 100.0 if actual > 0 else 0.0
    return round((actual - previa) / previa * 100, 1)


def get_enfermedad(disease_id):
    """Una sola enfermedad del catalogo. Se usa para la edicion y para el
    snapshot que va a audit_log."""
    return query(
        """
        SELECT id, code, name, description, is_active, created_at, default_params
        FROM diseases WHERE id = %s
        """,
        (disease_id,),
        one=True,
    )


# ---------------------------------------------------------------------------
# Monitoreo -- analisis epidemiologico por tiempo, zona y demografia
# ---------------------------------------------------------------------------
# Todo lo de esta pantalla sale de `cases` (edad, sexo, severidad, fecha,
# municipio). Dos notas de alcance:
#   - La columna "HOSPIT." del mock no existe en el esquema: `cases.severity`
#     no modela hospitalizacion. Se muestra "Graves" (severity = 'grave'), que
#     es el dato real mas cercano.
#   - Las "zonas" del mock (Norte/Centro/Sur...) tampoco existen: aqui son los
#     municipios reales de Nuevo Leon, que es como esta cargado `regions`.
GRUPOS_EDAD = ["0-4", "5-14", "15-24", "25-44", "45-64", "65+"]

_GRUPO_EDAD_SQL = """
    CASE WHEN c.age < 5  THEN '0-4'
         WHEN c.age < 15 THEN '5-14'
         WHEN c.age < 25 THEN '15-24'
         WHEN c.age < 45 THEN '25-44'
         WHEN c.age < 65 THEN '45-64'
         ELSE '65+' END
"""


def _monitoreo_where(disease_id, region_id, dias):
    """Fragmento WHERE compartido por las consultas de la pantalla. Devuelve
    (sql, params); los valores siempre viajan como parametros ligados."""
    cond = ["c.status IN ('pendiente', 'validado')",
            "c.report_date >= current_date - %s"]
    params = [dias - 1]
    if region_id:
        cond.append("c.region_id = %s")
        params.append(region_id)
    else:
        cond.append("""c.region_id IN (SELECT id FROM regions
                       WHERE parent_region_id = (SELECT id FROM regions WHERE code = %s))""")
        params.append(NL_ESTADO_CODE)
    if disease_id:
        cond.append("c.disease_id = %s")
        params.append(disease_id)
    return " AND ".join(cond), params


def _poblacion_ambito(region_id):
    if region_id:
        row = query("SELECT population FROM regions WHERE id = %s", (region_id,), one=True)
    else:
        row = query("SELECT population FROM regions WHERE code = %s", (NL_ESTADO_CODE,), one=True)
    return (row or {}).get("population") or 0


def get_monitoreo_serie(disease_id=None, region_id=None, dias=30):
    """Serie diaria: casos por dia + incidencia acumulada por 100k, que son
    las dos series del grafico 'Evolucion Temporal'."""
    where, params = _monitoreo_where(disease_id, region_id, dias)
    rows = query(
        f"""
        SELECT c.report_date::text AS fecha, count(*) AS casos
        FROM cases c
        WHERE {where}
        GROUP BY c.report_date
        ORDER BY c.report_date
        """,
        tuple(params),
    )
    poblacion = _poblacion_ambito(region_id)
    acumulado = 0
    serie = []
    for r in rows:
        acumulado += r["casos"]
        serie.append({
            "fecha": r["fecha"],
            "casos": r["casos"],
            "incidencia_acum": round(acumulado / poblacion * 100000, 2) if poblacion else 0.0,
        })
    return serie


def get_monitoreo_edad(disease_id=None, region_id=None, dias=30):
    """Casos por grupo etario. Siempre devuelve los 6 grupos en orden, aunque
    alguno venga en cero, para que el eje del grafico no se mueva."""
    where, params = _monitoreo_where(disease_id, region_id, dias)
    rows = query(
        f"""
        SELECT {_GRUPO_EDAD_SQL} AS grupo, count(*) AS casos
        FROM cases c
        WHERE {where} AND c.age IS NOT NULL
        GROUP BY 1
        """,
        tuple(params),
    )
    conteo = {r["grupo"]: r["casos"] for r in rows}
    return [{"grupo": g, "casos": conteo.get(g, 0)} for g in GRUPOS_EDAD]


def get_monitoreo_sexo(disease_id=None, region_id=None, dias=30):
    where, params = _monitoreo_where(disease_id, region_id, dias)
    rows = query(
        f"""
        SELECT c.sex, count(*) AS casos
        FROM cases c
        WHERE {where}
        GROUP BY c.sex
        ORDER BY casos DESC
        """,
        tuple(params),
    )
    total = sum(r["casos"] for r in rows) or 1
    return [{
        "label": SEXOS.get(r["sex"], "No especificado"),
        "casos": r["casos"],
        "pct": round(r["casos"] / total * 100, 1),
    } for r in rows]


def get_monitoreo_totales(disease_id=None, region_id=None, dias=30):
    """Casos e incidencia del periodo vs el periodo previo de igual largo."""
    cond = ["c.status IN ('pendiente', 'validado')"]
    cond_params = []
    if region_id:
        cond.append("c.region_id = %s")
        cond_params.append(region_id)
    else:
        cond.append("""c.region_id IN (SELECT id FROM regions
                       WHERE parent_region_id = (SELECT id FROM regions WHERE code = %s))""")
        cond_params.append(NL_ESTADO_CODE)
    if disease_id:
        cond.append("c.disease_id = %s")
        cond_params.append(disease_id)

    # Los tres %s de los FILTER van antes que los del WHERE en el texto del SQL
    # (ver nota en get_monitoreo_zonas): el orden de la lista tiene que seguir
    # al texto, no a las clausulas.
    row = query(
        f"""
        SELECT count(*) FILTER (WHERE c.report_date >= current_date - %s) AS actual,
               count(*) FILTER (WHERE c.report_date <  current_date - %s
                                  AND c.report_date >= current_date - %s) AS previo
        FROM cases c
        WHERE {' AND '.join(cond)}
        """,
        tuple([dias - 1, dias - 1, 2 * dias - 1] + cond_params),
    )
    row = row[0] if row else {"actual": 0, "previo": 0}
    poblacion = _poblacion_ambito(region_id)
    actual, previo = row["actual"] or 0, row["previo"] or 0
    return {
        "casos": actual,
        "casos_previo": previo,
        "casos_pct": _pct_change(actual, previo),
        "incidencia": round(actual / poblacion * 100000, 1) if poblacion else 0.0,
        "incidencia_previa": round(previo / poblacion * 100000, 1) if poblacion else 0.0,
    }


SEXOS = {"M": "Masculino", "F": "Femenino", "O": "Otro"}


def get_region_municipio(region_id):
    """Un municipio de Nuevo Leon para el formulario de edicion de poblacion.
    None si no existe o si no es un municipio de NL (nivel/padre incorrectos):
    asi la ruta no depende de confiar en el region_id que llega por la URL."""
    return query(
        """
        SELECT r.id, r.code, r.name, r.level, r.parent_region_id,
               r.population, r.population_60plus
        FROM regions r
        WHERE r.id = %s
          AND r.level = 'municipio'
          AND r.parent_region_id = (SELECT id FROM regions WHERE code = %s)
        """,
        (region_id, NL_ESTADO_CODE),
        one=True,
    )
