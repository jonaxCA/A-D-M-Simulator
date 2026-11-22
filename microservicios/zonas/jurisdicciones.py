"""Casos por jurisdicción sanitaria (F7, agrupaciones territoriales).

Los municipios de cada jurisdicción salen de datos/geo/nl_jurisdicciones_sanitarias.json (lo
genera datos/scripts/build_jurisdicciones.py desde el artículo 27 del Reglamento Interior de
Servicios de Salud de Nuevo León). Las cifras son las de la tabla por zona (`/zones`), sumadas
por jurisdicción: casos y graves del periodo, incidencia por 100 000 habitantes y variación de
los últimos 7 días contra los 7 anteriores, con el mismo semáforo.

Monterrey se reparte entre las jurisdicciones 1, 2 y 3. Con casos por municipio no se puede
partir, así que sale como su propio grupo, «Monterrey (jurisdicciones 1, 2 y 3)», y las
jurisdicciones 2 y 3 llevan solo sus otros municipios.
"""
import json
from functools import lru_cache
from pathlib import Path

from epidemia_comun.bd import query

ARCHIVO = Path(__file__).resolve().parents[2] / "datos/geo/nl_jurisdicciones_sanitarias.json"
ESTADO_NL = "19"


@lru_cache(maxsize=1)
def catalogo():
    return json.loads(ARCHIVO.read_text(encoding="utf-8"))


def grupos():
    """[(clave, nombre, números de jurisdicción, claves INEGI)] en orden: los compartidos
    primero (Monterrey), luego cada jurisdicción con municipios completos."""
    datos = catalogo()
    resultado = []
    for codigo, numeros in datos["compartidos"].items():
        resultado.append(("compartido-" + codigo, None, numeros, [codigo]))
    for j in datos["jurisdicciones"]:
        if j["municipios"]:
            resultado.append((str(j["numero"]), j["nombre"], [j["numero"]], j["municipios"]))
    return resultado


def _variacion(actual, previa):
    # Como backend_web.queries._pct_change y _clasifica_tendencia, los de la tabla por zona.
    if previa == 0:
        return 100.0 if actual > 0 else 0.0
    return round((actual - previa) / previa * 100, 1)


def _estado(variacion):
    if variacion >= 50:
        return "critico"
    if variacion >= 15:
        return "alerta"
    return "estable"


def _por_municipio(dias, disease_id):
    union = ["c.region_id = r.id", "c.status IN ('pendiente', 'validado')",
             "c.report_date >= current_date - %(ventana)s"]
    if disease_id:
        union.append("c.disease_id = %(disease_id)s")
    sql = """SELECT r.code, r.name, r.population,
                    count(c.id) FILTER (WHERE c.report_date >= current_date - %(dias)s) AS casos,
                    count(c.id) FILTER (WHERE c.report_date >= current_date - %(dias)s
                                          AND c.severity = 'grave') AS graves,
                    count(c.id) FILTER (WHERE c.report_date >= current_date - 6) AS ult7,
                    count(c.id) FILTER (WHERE c.report_date BETWEEN current_date - 13
                                                               AND current_date - 7) AS prev7
             FROM regions r
             LEFT JOIN cases c ON {}
             WHERE r.parent_region_id = (SELECT id FROM regions WHERE code = %(estado)s)
             GROUP BY r.code, r.name, r.population""".format(" AND ".join(union))
    return {f["code"]: f for f in query(sql, {"dias": dias - 1, "ventana": max(dias, 14) - 1,
                                              "disease_id": disease_id, "estado": ESTADO_NL})}


def _nombre_compartido(nombres, numeros):
    return "%s (jurisdicciones %s)" % (", ".join(nombres),
                                       ", ".join(str(n) for n in numeros[:-1]) + " y " + str(numeros[-1]))


def de_municipio(codigo, nombre_municipio):
    """El grupo de un municipio, con la clave y el nombre que usa /zones/jurisdictions."""
    for clave, nombre, numeros, codigos in grupos():
        if codigo in codigos:
            return {"clave": clave, "nombre": nombre or _nombre_compartido([nombre_municipio], numeros),
                    "numeros": numeros}
    return None


def calcular(dias, disease_id=None):
    municipios = _por_municipio(dias, disease_id)
    salida, vistos = [], set()
    for clave, nombre, numeros, codigos in grupos():
        filas = [municipios[c] for c in codigos if c in municipios]
        vistos.update(codigos)
        if nombre is None:
            nombre = _nombre_compartido([f["name"] for f in filas] or codigos, numeros)
        salida.append(_grupo(clave, nombre, numeros, filas))
    # Un municipio que la base tiene y el catálogo no (no debería pasar): no se pierden sus casos.
    sueltos = [f for c, f in sorted(municipios.items()) if c not in vistos]
    if sueltos:
        salida.append(_grupo("sin-jurisdiccion", "Sin jurisdicción", [], sueltos))
    return salida


def _grupo(clave, nombre, numeros, filas):
    poblacion = sum(f["population"] or 0 for f in filas)
    casos = sum(f["casos"] or 0 for f in filas)
    variacion = _variacion(sum(f["ult7"] or 0 for f in filas), sum(f["prev7"] or 0 for f in filas))
    return {"clave": clave, "nombre": nombre, "numeros": numeros,
            "municipios": [{"region_code": f["code"], "nombre": f["name"]} for f in filas],
            "poblacion": poblacion, "casos": casos,
            "incidencia": round(casos / poblacion * 100000, 1) if poblacion else 0.0,
            "graves": sum(f["graves"] or 0 for f in filas),
            "variacion": variacion, "estado": _estado(variacion)}


def fuente():
    datos = catalogo()["fuente"]
    return {"documento": datos["documento"], "publicacion": datos["publicacion"],
            "url": datos["url"], "nota": datos["nota"]}
