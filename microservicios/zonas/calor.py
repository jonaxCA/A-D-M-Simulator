"""Puntos para un mapa de calor (F7): los casos con coordenadas, agregados en celdas.

Cada caso trae la latitud y la longitud de donde se capturó; publicarlas tal cual ubicaría a
una persona. Por eso salen agregadas en una cuadrícula de `celda` grados (0.01 son unos 1.1 km
en Nuevo León) y una celda con menos de MINIMO_POR_CELDA casos no se publica: se cuenta en
`casos_suprimidos`. Los casos son los de siempre (`pendiente` o `validado`, por fecha de
reporte, en los municipios de Nuevo León o en uno).
"""
from decimal import Decimal

from epidemia_comun.bd import query

ESTADO_NL = "19"
# La más fina es de ~1 km: una más chica acercaría el punto a un domicilio.
CELDAS = ("0.01", "0.02", "0.05")
MINIMO_POR_CELDA = 3


def _conteos(celda, dias, disease_id, region_id):
    condiciones = ["c.status IN ('pendiente', 'validado')",
                   "c.report_date >= current_date - %(dias)s"]
    if region_id:
        condiciones.append("c.region_id = %(region_id)s")
    else:
        condiciones.append("""c.region_id IN (SELECT id FROM regions WHERE parent_region_id =
                                  (SELECT id FROM regions WHERE code = %(estado)s))""")
    if disease_id:
        condiciones.append("c.disease_id = %(disease_id)s")
    # Sin coordenadas, la fila y la columna salen NULL: ese grupo son los casos sin ubicación.
    sql = """SELECT floor(c.latitude / %(celda)s::numeric)::int AS fila,
                    floor(c.longitude / %(celda)s::numeric)::int AS columna,
                    count(*) AS casos
             FROM cases c
             WHERE {}
             GROUP BY 1, 2""".format(" AND ".join(condiciones))
    return query(sql, {"celda": celda, "dias": dias - 1, "region_id": region_id,
                       "disease_id": disease_id, "estado": ESTADO_NL})


def _centro(indice, celda):
    return float(round((Decimal(indice) + Decimal("0.5")) * Decimal(celda), 6))


def calcular(celda, dias, disease_id=None, region_id=None):
    sin_coordenadas = suprimidos = celdas_suprimidas = total = 0
    puntos = []
    for f in _conteos(celda, dias, disease_id, region_id):
        total += f["casos"]
        if f["fila"] is None or f["columna"] is None:
            sin_coordenadas += f["casos"]
        elif f["casos"] < MINIMO_POR_CELDA:
            suprimidos += f["casos"]
            celdas_suprimidas += 1
        else:
            puntos.append({"lat": _centro(f["fila"], celda), "lon": _centro(f["columna"], celda),
                           "casos": f["casos"]})
    maximo = max((p["casos"] for p in puntos), default=0)
    for p in puntos:
        # Para la intensidad de Leaflet.heat o el color de Highcharts: de 0 a 1.
        p["peso"] = round(p["casos"] / maximo, 4)
    puntos.sort(key=lambda p: (-p["casos"], p["lat"], p["lon"]))
    return {"celda_grados": float(celda), "minimo_por_celda": MINIMO_POR_CELDA,
            "total_casos": total, "casos_en_puntos": total - sin_coordenadas - suprimidos,
            "casos_sin_coordenadas": sin_coordenadas, "casos_suprimidos": suprimidos,
            "celdas_suprimidas": celdas_suprimidas, "puntos": puntos}
