"""Cada indicador del tablero con su numerador, su denominador y su periodo (F7, RF-G07).

`GET /dashboard/indicators` conserva sus campos de siempre (los de get_resumen_indicadores, que
también lee la web) y agrega `indicadores`: las mismas cuentas, explicadas, más mortalidad,
letalidad y casos graves. Los filtros son los de siempre: casos `pendiente` o `validado`, por
fecha de reporte, en los municipios de Nuevo León; la semana es hoy y los 6 días previos, contra
los 7 anteriores.

Con `factor`, valor = numerador / denominador × factor. Sin él, valor = numerador, y el
denominador, si viene, es el total de referencia (los municipios, para las zonas en riesgo).
"""
from datetime import timedelta

from epidemia_comun.bd import query

ESTADO_NL = "19"
POR_100K = 100000
POR_CIENTO = 100
# Casos por 100 000 habitantes en la semana a partir de los cuales un municipio está en riesgo
# (el mismo umbral de zonas_en_riesgo).
UMBRAL_RIESGO = 10
CASOS = "Casos reportados en el periodo (pendientes o validados) en los municipios de Nuevo León"

SQL = """
WITH estado AS (SELECT id, population FROM regions WHERE code = %(estado)s),
     municipios AS (SELECT id, population FROM regions
                    WHERE parent_region_id = (SELECT id FROM estado)),
     casos AS (SELECT c.region_id, c.severity, c.report_date >= current_date - 6 AS actual
               FROM cases c
               WHERE c.region_id IN (SELECT id FROM municipios)
                 AND c.status IN ('pendiente', 'validado')
                 AND c.report_date >= current_date - 13)
SELECT current_date AS hoy,
       (SELECT population FROM estado) AS poblacion,
       (SELECT count(*) FROM municipios) AS municipios,
       count(*) FILTER (WHERE actual) AS casos,
       count(*) FILTER (WHERE NOT actual) AS casos_previos,
       count(*) FILTER (WHERE actual AND severity = 'fallecido') AS fallecidos,
       count(*) FILTER (WHERE NOT actual AND severity = 'fallecido') AS fallecidos_previos,
       count(*) FILTER (WHERE actual AND severity = 'grave') AS graves,
       count(*) FILTER (WHERE NOT actual AND severity = 'grave') AS graves_previos,
       (SELECT count(*) FROM (
            SELECT m.id FROM municipios m
            LEFT JOIN casos c ON c.region_id = m.id AND c.actual
            GROUP BY m.id, m.population
            HAVING count(c.region_id)::numeric / NULLIF(m.population, 0) * %(por_100k)s
                   > %(umbral)s) en_riesgo) AS zonas,
       (SELECT count(*) FROM simulation_runs
        WHERE status IN ('encolado', 'ejecutando')) AS simulaciones
FROM casos
"""


def _variacion(actual, previa):
    # Igual que backend_web.queries._pct_change, para que coincida con casos_pct y tasa_pct.
    if previa == 0:
        return 100.0 if actual > 0 else 0.0
    return round((actual - previa) / previa * 100, 1)


def _semana(hoy, atras=0):
    hasta = hoy - timedelta(days=7 * atras)
    return {"desde": (hasta - timedelta(days=6)).isoformat(), "hasta": hasta.isoformat(), "dias": 7}


def _valor(numerador, denominador, factor, decimales):
    if factor is None:
        return numerador
    if not denominador:
        return None
    return round(numerador / denominador * factor, decimales)


def _indicador(clave, nombre, unidad, numerador, denominador, factor=None, periodo=None,
               previo=None, decimales=1):
    """numerador y denominador son (valor, descripción); previo, el numerador de la semana
    anterior (el denominador no cambia)."""
    valor = _valor(numerador[0], denominador and denominador[0], factor, decimales)
    resultado = {
        "clave": clave, "nombre": nombre, "valor": valor, "unidad": unidad,
        "numerador": {"valor": numerador[0], "descripcion": numerador[1]},
        "denominador": None if denominador is None
        else {"valor": denominador[0], "descripcion": denominador[1]},
        "factor": factor,
        "periodo": periodo or {"desde": None, "hasta": None, "dias": None},
        "previo": None, "variacion_pct": None,
    }
    if previo is not None:
        anterior = _valor(previo[0], denominador and denominador[0], factor, decimales)
        resultado["previo"] = dict(_semana(previo[1], 1), valor=anterior, numerador=previo[0])
        if valor is not None and anterior is not None:
            resultado["variacion_pct"] = _variacion(valor, anterior)
    return resultado


def calcular():
    f = query(SQL, {"estado": ESTADO_NL, "por_100k": POR_100K, "umbral": UMBRAL_RIESGO}, one=True)
    hoy, semana = f["hoy"], _semana(f["hoy"])
    poblacion = (f["poblacion"], "Habitantes de Nuevo León")
    casos = (f["casos"], "Casos reportados en el periodo")
    fallecidos = "Casos con gravedad «fallecido» reportados en el periodo"
    graves = "Casos con gravedad «grave» reportados en el periodo"
    return [
        _indicador("casos_activos", "Casos de la semana", "casos", (f["casos"], CASOS), None,
                   periodo=semana, previo=(f["casos_previos"], hoy)),
        _indicador("tasa_incidencia", "Tasa de incidencia", "casos por 100 000 habitantes",
                   (f["casos"], CASOS), poblacion, POR_100K, semana, (f["casos_previos"], hoy)),
        _indicador("tasa_mortalidad", "Tasa de mortalidad", "defunciones por 100 000 habitantes",
                   (f["fallecidos"], fallecidos), poblacion, POR_100K, semana,
                   (f["fallecidos_previos"], hoy), decimales=2),
        # La semana previa de las proporciones necesitaría su propio denominador: solo la actual.
        _indicador("letalidad", "Letalidad", "% de los casos", (f["fallecidos"], fallecidos),
                   casos, POR_CIENTO, semana),
        _indicador("casos_graves", "Casos graves", "% de los casos", (f["graves"], graves),
                   casos, POR_CIENTO, semana),
        _indicador("zonas_en_riesgo", "Zonas en riesgo", "municipios",
                   (f["zonas"], "Municipios con más de %d casos por 100 000 habitantes en el periodo"
                    % UMBRAL_RIESGO),
                   (f["municipios"], "Municipios de Nuevo León"), periodo=semana),
        _indicador("simulaciones_activas", "Simulaciones activas", "corridas",
                   (f["simulaciones"], "Corridas encoladas o ejecutándose en este momento"), None),
    ]
