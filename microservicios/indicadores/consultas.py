"""Las tarjetas del panorama y el resumen de situación del tablero.

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


def _clasifica_tendencia(pct):
    """Clave del semaforo de tendencia; el texto lo arma frontend_web."""
    if pct >= 50:
        return "critico"
    if pct >= 15:
        return "alerta"
    return "estable"


def get_resumen_indicadores():
    """Las 4 tarjetas del panorama: casos activos, tasa de incidencia,
    zonas en riesgo, simulaciones activas. Todo acotado a Nuevo Leon."""
    casos = query(
        """
        SELECT
            count(*) FILTER (WHERE c.report_date >= current_date - 6) AS actual,
            count(*) FILTER (WHERE c.report_date BETWEEN current_date - 13
                                                       AND current_date - 7) AS previa
        FROM cases c
        JOIN regions r ON r.id = c.region_id
        WHERE r.parent_region_id = (SELECT id FROM regions WHERE code = %s)
          AND c.status IN ('pendiente', 'validado')
        """,
        (NL_ESTADO_CODE,),
        one=True,
    )
    casos_activos = casos["actual"] or 0
    pct_casos = _pct_change(casos["actual"] or 0, casos["previa"] or 0)

    poblacion_nl = query(
        "SELECT population FROM regions WHERE code = %s", (NL_ESTADO_CODE,), one=True
    )["population"]
    # Tasa de incidencia expresada como casos por cada 100,000 habitantes
    # (convencion epidemiologica estandar -- la misma que ya usa el panel del
    # mapa). El mock de Figma la mostraba como "%", pero un state de 5.8M
    # habitantes nunca produce un porcentaje legible; "por 100k hab." si.
    tasa_actual = round((casos["actual"] or 0) / poblacion_nl * 100000, 1) if poblacion_nl else 0
    tasa_previa = round((casos["previa"] or 0) / poblacion_nl * 100000, 1) if poblacion_nl else 0
    pct_tasa = _pct_change(tasa_actual, tasa_previa)

    zonas = query(
        """
        SELECT count(*) AS n FROM (
            SELECT r.id,
                   count(c.*) FILTER (WHERE c.report_date >= current_date - 6)::numeric
                     / r.population * 100000 AS incidencia_100k
            FROM regions r
            LEFT JOIN cases c ON c.region_id = r.id AND c.status IN ('pendiente','validado')
            WHERE r.parent_region_id = (SELECT id FROM regions WHERE code = %s)
            GROUP BY r.id, r.population
        ) t
        WHERE incidencia_100k > 10
        """,
        (NL_ESTADO_CODE,),
        one=True,
    )["n"]

    simulaciones_activas = query(
        "SELECT count(*) AS n FROM simulation_runs WHERE status IN ('encolado','ejecutando')",
        one=True,
    )["n"]

    return {
        "casos_activos": casos_activos,
        "casos_pct": pct_casos,
        "tasa_incidencia": tasa_actual,
        "tasa_pct": pct_tasa,
        "zonas_en_riesgo": zonas,
        "simulaciones_activas": simulaciones_activas,
    }


def get_resumen_situacion(limit=5):
    """Tabla 'Resumen de Situacion': casos activos de la ultima semana por
    enfermedad, con su tendencia clasificada, ordenado por volumen."""
    rows = query(
        """
        SELECT d.name,
               count(*) FILTER (WHERE c.report_date >= current_date - 6) AS actual,
               count(*) FILTER (WHERE c.report_date BETWEEN current_date - 13
                                                          AND current_date - 7) AS previa
        FROM cases c
        JOIN diseases d ON d.id = c.disease_id
        JOIN regions r ON r.id = c.region_id
        WHERE r.parent_region_id = (SELECT id FROM regions WHERE code = %s)
        GROUP BY d.name
        HAVING count(*) FILTER (WHERE c.report_date >= current_date - 6) > 0
        ORDER BY actual DESC
        LIMIT %s
        """,
        (NL_ESTADO_CODE, limit),
    )
    out = []
    for r in rows:
        pct = _pct_change(r["actual"], r["previa"])
        out.append({
            "enfermedad": r["name"],
            "estado": _clasifica_tendencia(pct),
            "incidencia": r["actual"],
        })
    return out
