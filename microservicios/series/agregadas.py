"""Series de casos con rango de fechas libre, agregación por día, semana epidemiológica o mes,
agrupación por sexo, edad, enfermedad o municipio, paginación y salida para Highcharts (F7).

Los casos son los de siempre: `pendiente` o `validado`, por fecha de reporte, en los municipios
de Nuevo León (o en uno, con region_id). Cada periodo sale aunque no tenga casos, así que el eje
de una gráfica no tiene huecos.

- La semana epidemiológica va de domingo a sábado, y la semana 1 es la primera con al menos
  cuatro días del año (la que usa el SINAVE): «2026-47».
- El primer y el último periodo pueden quedar cortados por el rango: `completo` lo dice.
"""
import calendar
import math
from datetime import date, datetime, timedelta, timezone

from epidemia_comun.bd import query
from epidemia_comun.errores import ErrorAPI

ESTADO_NL = "19"
INTERVALOS = ("dia", "semana", "mes")
AGRUPACIONES = ("sexo", "edad", "enfermedad", "municipio")
DIAS_POR_OMISION = 90
# Dos años: el rango más largo que se puede pedir (731 periodos diarios como mucho).
DIAS_MAXIMOS = 731
TAMANO_POR_OMISION = 52
TAMANO_MAXIMO = 366
SIN_DATO = "No especificado"
SEXOS = {"M": "Masculino", "F": "Femenino", "O": "Otro"}
# Los de la pantalla de Monitoreo (backend_web.queries.GRUPOS_EDAD); hay prueba.
GRUPOS_EDAD = ("0-4", "5-14", "15-24", "25-44", "45-64", "65+")

_INICIO = {
    "dia": "c.report_date",
    "semana": "c.report_date - EXTRACT(DOW FROM c.report_date)::int",
    "mes": "date_trunc('month', c.report_date)::date",
}
_GRUPO = {
    None: ("NULL", ""),
    "sexo": ("c.sex", ""),
    "edad": ("""CASE WHEN c.age IS NULL THEN NULL
                     WHEN c.age < 5 THEN '0-4' WHEN c.age < 15 THEN '5-14'
                     WHEN c.age < 25 THEN '15-24' WHEN c.age < 45 THEN '25-44'
                     WHEN c.age < 65 THEN '45-64' ELSE '65+' END""", ""),
    "enfermedad": ("d.name", "JOIN diseases d ON d.id = c.disease_id"),
    "municipio": ("r.name", "JOIN regions r ON r.id = c.region_id"),
}


def _fecha(valor, campo):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser una fecha AAAA-MM-DD." % campo)


def _hoy():
    return query("SELECT current_date AS hoy", one=True)["hoy"]


def rango(args, dias_ambito):
    """(desde, hasta) de ?from y ?to, o de ?days, o los últimos 90 días hasta hoy (el de la base).
    dias_ambito es el days ya validado por filtros_ambito, o None si no vino."""
    desde, hasta = args.get("from") or None, args.get("to") or None
    if (desde or hasta) and dias_ambito is not None:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Manda days o from y to, no los dos.")
    hasta = _fecha(hasta, "to") if hasta else _hoy()
    if desde:
        desde = _fecha(desde, "from")
    else:
        desde = hasta - timedelta(days=(dias_ambito or DIAS_POR_OMISION) - 1)
    if desde > hasta:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "from no puede ser posterior a to.")
    if (hasta - desde).days + 1 > DIAS_MAXIMOS:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "El rango no puede pasar de %d días." % DIAS_MAXIMOS)
    return desde, hasta


def opcion(args, campo, opciones, por_omision=None):
    valor = args.get(campo) or por_omision
    if valor is not None and valor not in opciones:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "%s debe ser uno de: %s." % (campo, ", ".join(opciones)))
    return valor


def semana_epi(domingo):
    miercoles = domingo + timedelta(days=3)
    return "%d-%02d" % (miercoles.year, (miercoles.timetuple().tm_yday - 1) // 7 + 1)


def periodos(desde, hasta, intervalo):
    """Los (inicio, fin) de cada periodo que toca el rango, en orden."""
    if intervalo == "dia":
        inicio = desde
    elif intervalo == "semana":
        inicio = desde - timedelta(days=(desde.weekday() + 1) % 7)
    else:
        inicio = desde.replace(day=1)
    resultado = []
    while inicio <= hasta:
        if intervalo == "dia":
            fin = inicio
        elif intervalo == "semana":
            fin = inicio + timedelta(days=6)
        else:
            fin = inicio.replace(day=calendar.monthrange(inicio.year, inicio.month)[1])
        resultado.append((inicio, fin))
        inicio = fin + timedelta(days=1)
    return resultado


def _conteos(desde, hasta, intervalo, agrupar, disease_id, region_id):
    columna, union = _GRUPO[agrupar]
    condiciones = ["c.status IN ('pendiente', 'validado')",
                   "c.report_date BETWEEN %(desde)s AND %(hasta)s"]
    if region_id:
        condiciones.append("c.region_id = %(region_id)s")
    else:
        condiciones.append("""c.region_id IN (SELECT id FROM regions WHERE parent_region_id =
                                  (SELECT id FROM regions WHERE code = %(estado)s))""")
    if disease_id:
        condiciones.append("c.disease_id = %(disease_id)s")
    sql = """SELECT {inicio} AS inicio, {grupo} AS grupo, count(*) AS casos
             FROM cases c {union}
             WHERE {condiciones}
             GROUP BY 1, 2""".format(inicio=_INICIO[intervalo], grupo=columna, union=union,
                                     condiciones=" AND ".join(condiciones))
    return query(sql, {"desde": desde, "hasta": hasta, "region_id": region_id,
                       "disease_id": disease_id, "estado": ESTADO_NL})


def _etiqueta(agrupar, valor):
    if agrupar == "sexo":
        return SEXOS.get(valor, SIN_DATO)
    return SIN_DATO if valor is None else valor


def _grupos(agrupar, totales):
    if agrupar is None:
        return []
    if agrupar == "edad":
        return list(GRUPOS_EDAD) + ([SIN_DATO] if SIN_DATO in totales else [])
    return sorted(totales, key=lambda g: (-totales[g], g))


def calcular(desde, hasta, intervalo, agrupar=None, disease_id=None, region_id=None):
    """Todos los periodos del rango con sus casos, su acumulado y, si se agrupa, cada grupo."""
    por_periodo, totales = {}, {}
    for fila in _conteos(desde, hasta, intervalo, agrupar, disease_id, region_id):
        grupo = _etiqueta(agrupar, fila["grupo"]) if agrupar else None
        celda = por_periodo.setdefault(fila["inicio"], {})
        celda[grupo] = celda.get(grupo, 0) + fila["casos"]
        totales[grupo] = totales.get(grupo, 0) + fila["casos"]
    grupos = _grupos(agrupar, totales)
    acumulado, salida = 0, []
    for inicio, fin in periodos(desde, hasta, intervalo):
        celda = por_periodo.get(inicio, {})
        casos = sum(celda.values())
        acumulado += casos
        salida.append({"inicio": inicio.isoformat(), "fin": fin.isoformat(),
                       "semana_epi": semana_epi(inicio) if intervalo == "semana" else None,
                       "completo": inicio >= desde and fin <= hasta,
                       "casos": casos, "acumulado": acumulado,
                       "por_grupo": [{"grupo": g, "casos": celda.get(g, 0)} for g in grupos]})
    return {"grupos": grupos, "total_casos": acumulado, "periodos": salida}


def pagina(datos, numero, tamano):
    total = len(datos["periodos"])
    inicio = (numero - 1) * tamano
    return {"grupos": datos["grupos"], "total_casos": datos["total_casos"], "total": total,
            "pagina": numero, "paginas": max(1, math.ceil(total / tamano)),
            "periodos": datos["periodos"][inicio:inicio + tamano]}


def _milisegundos(dia):
    return int(datetime(dia.year, dia.month, dia.day, tzinfo=timezone.utc).timestamp() * 1000)


def highcharts(datos):
    """{xAxis, series} listo para Highcharts.chart(): una serie por grupo (o «Casos»), con
    puntos {x, y}; x es el inicio del periodo en milisegundos UTC."""
    xs = [_milisegundos(date.fromisoformat(p["inicio"])) for p in datos["periodos"]]
    if datos["grupos"]:
        series = [{"name": g, "data": [{"x": x, "y": p["por_grupo"][i]["casos"]}
                                       for x, p in zip(xs, datos["periodos"])]}
                  for i, g in enumerate(datos["grupos"])]
    else:
        series = [{"name": "Casos", "data": [{"x": x, "y": p["casos"]}
                                             for x, p in zip(xs, datos["periodos"])]}]
    return {"xAxis": {"type": "datetime"}, "yAxis": {"title": {"text": "Casos"}},
            "series": series}
