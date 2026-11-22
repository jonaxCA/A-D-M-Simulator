"""La tabla por zona, el mapa, su serie y la tendencia de un municipio, y los catálogos que
revisan sus filtros.

Copia de las de backend_web.queries: la web todavía las usa (D36) y la regla es de este
servicio (E8, docs/arquitectura/duenos_de_reglas.md). Mientras las dos existan deben ser
iguales: microservicios/comun/tests/test_copias_del_monolito.py lo revisa.
"""
from datetime import date, timedelta

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


BUCKETS = [
    (0, 15, "baja"),
    (15, 30, "moderada"),
    (30, 45, "alta"),
    (45, 60, "muy_alta"),
    (60, float("inf"), "critica"),
]


def _bucket(incidencia):
    """Nivel del semaforo del mapa para una incidencia por 100k."""
    for lo, hi, nivel in BUCKETS:
        if lo <= incidencia < hi:
            return nivel
    return "critica"


def get_mapa_municipios(disease_id=None, dias=30):
    """Un renglon por municipio de Nuevo Leon: casos totales del periodo,
    incidencia por 100k, variacion vs el periodo anterior de igual longitud,
    y el nivel del semaforo para colorear el marcador en el mapa."""
    periodo_offset = dias - 1          # p.ej. dias=30 -> ultimos 30 dias (offset 0..29)
    previo_offset = 2 * dias - 1       # los `dias` dias inmediatamente anteriores

    disease_filter = ""
    disease_params = ()
    if disease_id:
        disease_filter = "AND c.disease_id = %s"
        disease_params = (disease_id,)

    sql = f"""
        SELECT r.id, r.code, r.name, r.population, r.centroid_lat, r.centroid_lon,
               count(*) FILTER (WHERE c.report_date >= current_date - %s) AS casos_periodo,
               count(*) FILTER (WHERE c.report_date <  current_date - %s
                                   AND c.report_date >= current_date - %s) AS casos_previo
        FROM regions r
        LEFT JOIN cases c ON c.region_id = r.id
                          AND c.status IN ('pendiente','validado')
                          {disease_filter}
        WHERE r.parent_region_id = (SELECT id FROM regions WHERE code = %s)
        GROUP BY r.id, r.code, r.name, r.population, r.centroid_lat, r.centroid_lon
        ORDER BY r.name
        """
    params = (periodo_offset, periodo_offset, previo_offset) + disease_params + (NL_ESTADO_CODE,)
    rows = query(sql, params)

    out = []
    for r in rows:
        casos = r["casos_periodo"] or 0
        casos_previo = r["casos_previo"] or 0
        incidencia = round(casos / r["population"] * 100000, 1) if r["population"] else 0.0
        variacion = _pct_change(casos, casos_previo)
        out.append({
            "id": r["id"],
            "region_code": r["code"],
            "nombre": r["name"],
            "casos": casos,
            "incidencia": incidencia,
            "variacion": variacion,
            "lat": float(r["centroid_lat"]),
            "lon": float(r["centroid_lon"]),
            "nivel": _bucket(incidencia),
        })
    return out


def get_tendencia_zona(region_id, disease_id=None, dias=14):
    """Serie diaria corta para el mini-grafico de 'tendencia temporal' del
    panel de detalle del mapa, para una sola zona."""
    params = [region_id, dias - 1]
    disease_filter = ""
    if disease_id:
        disease_filter = "AND disease_id = %s"
        params.append(disease_id)
    rows = query(
        f"""
        SELECT report_date::text AS fecha, count(*) AS total
        FROM cases
        WHERE region_id = %s
          AND report_date >= current_date - %s
          {disease_filter}
        GROUP BY report_date
        ORDER BY report_date
        """,
        tuple(params),
    )
    return [{"fecha": r["fecha"], "total": r["total"]} for r in rows]


def get_mapa_serie_temporal(disease_id=None, dias=30):
    """Matriz municipio x dia para la linea de tiempo del mapa.

    Un cuadro por cada dia del periodo seleccionado -- `dias` cuadros exactos,
    ni mas ni menos, para que la barra corresponda con lo que dice el filtro.
    Cada cuadro trae el ACUMULADO del periodo hasta ese dia, no una ventana
    movil: asi el recorrido se lee como el periodo llenandose dia con dia, que
    es lo que se espera al darle "reproducir".

    Dos propiedades que hay que conservar si esto se toca:

    1. El ultimo cuadro es identico al mapa estatico. Acumular los `dias` dias
       del periodo da exactamente los casos que cuenta get_mapa_municipios, y
       la variacion del ultimo cuadro compara periodo contra periodo previo
       completo, igual que alla.
    2. Ningun cuadro mira antes del inicio del periodo, asi que el acumulado
       nunca queda inflado ni deprimido por falta de historia. (La variacion si
       depende del periodo previo: si no hay datos tan atras se queda en +100%,
       que es lo que ya devolvia _pct_change contra cero.)

    La variacion de cada cuadro compara contra el mismo numero de dias
    transcurridos del periodo previo -- dia 5 del periodo contra dia 5 del
    periodo anterior -- para que sea una comparacion pareja y no acumulado
    parcial contra periodo completo.

    El conteo por dia se hace en SQL y el acumulado en Python. Son
    51 x 2 x dias numeros: no amerita un window function, y de paso el SQL se
    queda sin fragmentos armados a mano mas alla del filtro de enfermedad.
    """
    # Historia a pedir: el periodo mas el periodo previo con el que se compara.
    historia_offset = 2 * dias - 1

    disease_filter = ""
    disease_params = ()
    if disease_id:
        disease_filter = "AND c.disease_id = %s"
        disease_params = (disease_id,)

    # OJO con el orden de los %s: psycopg2 los liga por posicion en el texto
    # del SQL, no por clausula. Aqui los del JOIN (historia y enfermedad) van
    # antes que el del WHERE (codigo del estado).
    sql = f"""
        SELECT r.code, r.name, r.population,
               c.report_date::text AS dia,
               count(c.id) AS casos
        FROM regions r
        LEFT JOIN cases c ON c.region_id = r.id
                          AND c.status IN ('pendiente','validado')
                          AND c.report_date >= current_date - %s
                          {disease_filter}
        WHERE r.parent_region_id = (SELECT id FROM regions WHERE code = %s)
        GROUP BY r.code, r.name, r.population, c.report_date
        ORDER BY r.name, dia
        """
    params = (historia_offset,) + disease_params + (NL_ESTADO_CODE,)
    rows = query(sql, params)

    # La fecha de corte se pide a la base, no se asume date.today(): las dos
    # tienen que ser la misma para que el ultimo cuadro cuadre con el mapa.
    hoy = date.fromisoformat(query("SELECT current_date::text AS hoy", one=True)["hoy"])

    por_municipio = {}
    for r in rows:
        m = por_municipio.setdefault(
            r["code"], {"population": r["population"], "por_dia": {}}
        )
        if r["dia"] is not None:
            m["por_dia"][r["dia"]] = r["casos"]

    inicio = hoy - timedelta(days=dias - 1)            # primer dia del periodo
    inicio_previo = inicio - timedelta(days=dias)      # primer dia del previo
    fechas = [(inicio + timedelta(days=n)).isoformat() for n in range(dias)]

    series = {}
    for code, m in por_municipio.items():
        casos_frame, incidencia_frame, variacion_frame = [], [], []
        acumulado = acumulado_previo = 0
        for i in range(dias):
            acumulado += m["por_dia"].get(fechas[i], 0)
            acumulado_previo += m["por_dia"].get(
                (inicio_previo + timedelta(days=i)).isoformat(), 0
            )
            casos_frame.append(acumulado)
            incidencia_frame.append(
                round(acumulado / m["population"] * 100000, 1) if m["population"] else 0.0
            )
            variacion_frame.append(_pct_change(acumulado, acumulado_previo))
        series[code] = {
            "casos": casos_frame,
            "incidencia": incidencia_frame,
            "variacion": variacion_frame,
        }

    return {"fechas": fechas, "dias_periodo": dias, "series": series}


ORDEN_ZONAS = {
    "casos": "casos DESC, r.name",
    "incidencia": "incid_orden DESC NULLS LAST, r.name",
}


def get_monitoreo_zonas(disease_id=None, region_id=None, dias=30, busqueda=None,
                        orden="casos", pagina=1, por_pagina=10):
    """Tabla 'Detalle por Zona Geografica': un renglon por municipio.

    La variacion es siempre a 7 dias (como el mock), independiente del periodo
    elegido, por eso el LEFT JOIN abre la ventana a max(dias, 14) dias y los
    recortes finos se hacen con FILTER.
    """
    ventana = max(dias, 14) - 1
    cond_join = ["c.region_id = r.id", "c.status IN ('pendiente', 'validado')",
                 "c.report_date >= current_date - %s"]
    cond_where = ["r.parent_region_id = (SELECT id FROM regions WHERE code = %s)"]
    pagina = max(1, pagina)

    # psycopg2 liga los %s por el orden en que aparecen en el TEXTO del SQL, no
    # por clausula: primero los dos FILTER del SELECT, luego el JOIN, luego el
    # WHERE y al final LIMIT/OFFSET. Armar la lista en otro orden cruza el
    # periodo y la ventana: con dias=7 la ventana quedaria en 7 dias y prev7
    # saldria siempre 0, o sea +100% / Critico en toda zona.
    params = [dias - 1, dias - 1, dias - 1, ventana]
    if disease_id:
        cond_join.append("c.disease_id = %s")
        params.append(disease_id)
    params.append(NL_ESTADO_CODE)
    if region_id:
        cond_where.append("r.id = %s")
        params.append(region_id)
    if busqueda:
        cond_where.append("r.name ILIKE %s")
        params.append(f"%{busqueda}%")
    params += [por_pagina, (pagina - 1) * por_pagina]

    rows = query(
        f"""
        SELECT r.id, r.name, r.population,
               count(c.id) FILTER (WHERE c.report_date >= current_date - %s) AS casos,
               count(c.id) FILTER (WHERE c.report_date >= current_date - %s
                                     AND c.severity = 'grave')               AS graves,
               count(c.id) FILTER (WHERE c.report_date >= current_date - %s)::numeric
                 / NULLIF(r.population, 0)                                   AS incid_orden,
               count(c.id) FILTER (WHERE c.report_date >= current_date - 6)  AS ult7,
               count(c.id) FILTER (WHERE c.report_date BETWEEN current_date - 13
                                                          AND current_date - 7) AS prev7,
               count(*) OVER () AS total_filtrado
        FROM regions r
        LEFT JOIN cases c ON {' AND '.join(cond_join)}
        WHERE {' AND '.join(cond_where)}
        GROUP BY r.id, r.name, r.population
        ORDER BY {ORDEN_ZONAS.get(orden, ORDEN_ZONAS['casos'])}
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )

    total = rows[0]["total_filtrado"] if rows else 0
    zonas = []
    for r in rows:
        casos = r["casos"] or 0
        variacion = _pct_change(r["ult7"] or 0, r["prev7"] or 0)
        zonas.append({
            "id": r["id"],
            "zona": r["name"],
            "casos": casos,
            "incidencia": round(casos / r["population"] * 100000, 1) if r["population"] else 0.0,
            "variacion": variacion,
            "graves": r["graves"] or 0,
            "estado": _clasifica_tendencia(variacion),
        })

    return {
        "zonas": zonas,
        "total": total,
        "pagina": pagina,
        "paginas": max(1, -(-total // por_pagina)),
        "desde": (pagina - 1) * por_pagina + 1 if total else 0,
        "hasta": min(pagina * por_pagina, total),
    }


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
