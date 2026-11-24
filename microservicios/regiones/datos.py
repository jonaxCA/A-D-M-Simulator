# Jerarquía territorial, jurisdicciones sanitarias y búsqueda (043, D58). Las jurisdicciones salen de
# health_areas y health_area_municipalities, que ligan cada municipio por su clave INEGI; la
# geometría y los mapas siguen en zonas.
import unicodedata

from epidemia_comun.bd import query

ESTADO = "19"
_AREAS = """SELECT a.id, a.number AS numero, a.name AS nombre, a.description AS circunscripcion,
                   a.source AS fuente, a.source_url AS url
            FROM health_areas a WHERE a.state_code = %s"""


def normaliza(texto):
    # Minúsculas y sin acentos, para buscar «monterrey» o «Gral. Escobedo» como se escriba.
    texto = unicodedata.normalize("NFKD", (texto or "").strip().lower())
    return " ".join(texto.encode("ascii", "ignore").decode("ascii").split())


def region(region_id):
    fila = query("""SELECT r.id, r.code, r.name AS nombre, r.level AS nivel, r.population AS poblacion,
                           r.parent_region_id AS padre_id
                    FROM regions r WHERE r.id = %s""", (region_id,), one=True)
    return dict(fila) if fila else None


def hijos(region_id):
    return [dict(f) for f in query(
        """SELECT id, code, name AS nombre, level AS nivel, population AS poblacion
           FROM regions WHERE parent_region_id = %s ORDER BY name""", (region_id,))]


def _miembros(area_ids):
    filas = query("""SELECT m.health_area_id, m.region_code AS code, m.partial AS parcial, r.id AS region_id,
                            r.name AS nombre
                     FROM health_area_municipalities m
                     LEFT JOIN regions r ON r.code = m.region_code
                     WHERE m.health_area_id = ANY(%s)
                     ORDER BY r.name, m.region_code""", (list(area_ids),))
    por_area = {}
    for f in filas:
        f = dict(f)
        por_area.setdefault(f.pop("health_area_id"), []).append(f)
    return por_area


def jurisdicciones(numero=None):
    if numero is None:
        filas = [dict(f) for f in query(_AREAS + " ORDER BY a.number", (ESTADO,))]
    else:
        filas = [dict(f) for f in query(_AREAS + " AND a.number = %s", (ESTADO, numero))]
    miembros = _miembros([f["id"] for f in filas])
    return [dict({k: v for k, v in f.items() if k != "id"}, municipios=miembros.get(f["id"], [])) for f in filas]


def jurisdicciones_de(code):
    # Las jurisdicciones de un municipio (Monterrey está en tres, en parte).
    return [dict(f) for f in query(
        """SELECT a.number AS numero, a.name AS nombre, m.partial AS parcial
           FROM health_area_municipalities m JOIN health_areas a ON a.id = m.health_area_id
           WHERE m.region_code = %s ORDER BY a.number""", (code,))]


def busca(texto, limite=20):
    """Estado, municipios y jurisdicciones cuyo nombre o clave contiene `texto`, sin importar acentos."""
    buscado = normaliza(texto)
    salida = []
    for r in query("""SELECT r.id, r.code, r.name, r.level, p.name AS padre
                      FROM regions r LEFT JOIN regions p ON p.id = r.parent_region_id
                      WHERE r.code = %s OR p.code = %s ORDER BY r.level DESC, r.name""", (ESTADO, ESTADO)):
        if buscado in normaliza(r["name"]) or buscado == r["code"]:
            salida.append({"tipo": r["level"], "id": r["id"], "code": r["code"], "nombre": r["name"],
                           "padre": r["padre"]})
    for a in query(_AREAS + " ORDER BY a.number", (ESTADO,)):
        if buscado in normaliza(a["nombre"]) or buscado in normaliza(a["circunscripcion"]):
            salida.append({"tipo": "jurisdiccion", "id": a["numero"], "code": None, "nombre": a["nombre"],
                           "padre": None})
    return salida[:limite]


# El catálogo de municipios de NL (antes en backend_web.queries, E8). Solo se ordena por una
# columna de esta lista: nunca se interpola la entrada en el SQL.
ORDEN_REGIONES = {"nombre": "r.name", "poblacion": "r.population"}
FUENTE_60 = "Grupos 60-79 y 80+ del Censo 2020"


def _fuente_campo(motivo, fecha, por, fuente_censal):
    # Un ajuste manual vigente nunca se le atribuye a INEGI.
    if motivo is None:
        return {"tipo": "censal", "fuente": fuente_censal}
    return {"tipo": "manual", "motivo": motivo, "fecha": fecha, "por": por}


def _ultima_correccion_grupos_edad(region_ids):
    if not region_ids:
        return {}
    filas = query(
        """SELECT DISTINCT ON (a.entity_id)
                  a.entity_id, a.data_after ->> 'age_correction_reason' AS reason,
                  a.occurred_at, u.full_name
           FROM audit_log a
           LEFT JOIN users u ON u.id = a.user_id
           WHERE a.entity_type = 'regions'
             AND a.entity_id = ANY(%s)
             AND a.data_after ? 'population_by_age'
             AND (a.data_after -> 'age_groups_modified') ?| ARRAY['60-79', '80+']
           ORDER BY a.entity_id, a.occurred_at DESC, a.id DESC""",
        ([str(i) for i in region_ids],))
    return {f["entity_id"]: f for f in filas}


def catalogo(busqueda=None, orden="nombre", direccion="asc"):
    columna = ORDEN_REGIONES.get(orden, ORDEN_REGIONES["nombre"])
    direccion_sql = "DESC" if direccion == "desc" else "ASC"
    condiciones = ["r.parent_region_id = (SELECT id FROM regions WHERE code = %s)"]
    params = [ESTADO]
    if busqueda:
        condiciones.append("(r.name ILIKE %s OR r.code ILIKE %s)")
        params += ["%" + busqueda + "%"] * 2
    filas = query(
        """SELECT r.id, r.code, r.name, r.population, r.population_60plus
           FROM regions r WHERE %s
           ORDER BY %s %s, r.name ASC""" % (" AND ".join(condiciones), columna, direccion_sql),
        tuple(params))
    ajustes = {}
    if filas:
        ajustes = {a["region_id"]: a for a in query(
            """SELECT a.region_id, a.reason, a.adjusted_at, u.full_name
               FROM region_population_adjustments a
               LEFT JOIN users u ON u.id = a.adjusted_by
               WHERE a.region_id = ANY(%s) AND a.field = 'population'""",
            ([f["id"] for f in filas],))}
    correcciones = _ultima_correccion_grupos_edad([f["id"] for f in filas])
    municipios = []
    for f in filas:
        ajuste = ajustes.get(f["id"], {})
        edad = correcciones.get(str(f["id"]))
        municipios.append({
            "id": f["id"], "code": f["code"], "nombre": f["name"], "poblacion": f["population"],
            "poblacion_60": f["population_60plus"],
            "fuente_poblacion": _fuente_campo(ajuste.get("reason"), ajuste.get("adjusted_at"),
                                              ajuste.get("full_name"), "INEGI, Censo 2020"),
            "fuente_poblacion_60": (_fuente_campo(edad["reason"], edad["occurred_at"], edad["full_name"],
                                                  FUENTE_60)
                                    if edad else {"tipo": "derivado", "fuente": FUENTE_60}),
        })
    return {"municipios": municipios, "total": len(municipios), "busqueda": busqueda or "",
            "orden": orden if orden in ORDEN_REGIONES else "nombre",
            "direccion": direccion if direccion in ("asc", "desc") else "asc"}


def municipio(region_id):
    # None si no existe o no es un municipio de NL: la ruta no confía en el id de la URL.
    return query(
        """SELECT r.id, r.code, r.name, r.level, r.parent_region_id, r.population, r.population_60plus
           FROM regions r
           WHERE r.id = %s AND r.level = 'municipio'
             AND r.parent_region_id = (SELECT id FROM regions WHERE code = %s)""",
        (region_id, ESTADO), one=True)
