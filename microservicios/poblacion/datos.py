# La población de cada municipio de Nuevo León, su corrección manual, sus versiones y sus periodos de
# referencia (D58). Las reglas vivían en backend_web.queries (E8); aquí siguen iguales y cada ajuste
# deja además su versión (population_versions, 043) en la misma transacción. La versión 1 se
# guarda al primer ajuste, con las cifras de antes.
import psycopg2

from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import a_jsonb, get_conn, query

NL_ESTADO_CODE = "19"
GRUPOS_EDAD_MUNICIPIO = ("0-19", "20-39", "40-59", "60-79", "80+")
# Las cifras vigentes son las del Censo 2020; un ajuste corrige ese mismo periodo.
ANIO_REFERENCIA = 2020
FUENTE_CENSO = "INEGI, Censo de Población y Vivienda 2020"


def get_region_municipio(region_id):
    """Un municipio de Nuevo León, o None si no existe o no es municipio de NL."""
    return query(
        """SELECT r.id, r.code, r.name, r.level, r.parent_region_id, r.population, r.population_60plus
           FROM regions r
           WHERE r.id = %s AND r.level = 'municipio'
             AND r.parent_region_id = (SELECT id FROM regions WHERE code = %s)""",
        (region_id, NL_ESTADO_CODE), one=True)


def region_nl(region_id):
    """El estado o uno de sus municipios: {id, code, name, level}, o None."""
    return query(
        """SELECT r.id, r.code, r.name, r.level FROM regions r
           WHERE r.id = %s AND (r.code = %s OR r.parent_region_id = (SELECT id FROM regions WHERE code = %s))""",
        (region_id, NL_ESTADO_CODE, NL_ESTADO_CODE), one=True)


def get_grupos_edad_municipio(region_id):
    """Bandas censales y edad no especificada de un municipio de NL; None si no las tiene."""
    filas = query(
        """SELECT g.age_group, g.lower_bound, g.population
           FROM region_age_groups g JOIN regions r ON r.id = g.region_id
           WHERE r.id = %s AND r.level = 'municipio'
             AND r.parent_region_id = (SELECT id FROM regions WHERE code = %s)
           ORDER BY g.lower_bound NULLS LAST""", (region_id, NL_ESTADO_CODE))
    if not filas:
        return None
    return {"grupos": {f["age_group"]: f["population"] for f in filas if f["lower_bound"] is not None},
            "edad_no_especificada": next((f["population"] for f in filas if f["lower_bound"] is None), 0)}


def valida_grupos_edad_municipio(grupos_raw, actuales=None):
    """Valida los cinco grupos que consume el motor; la edad no especificada no se edita."""
    errores, grupos = [], {}
    for grupo in GRUPOS_EDAD_MUNICIPIO:
        try:
            numero = int(str(grupos_raw.get(grupo)).strip())
        except (TypeError, ValueError):
            errores.append(f"La banda {grupo} debe ser un número entero.")
            continue
        if numero < 0:
            errores.append(f"La banda {grupo} no puede ser negativa.")
        elif numero > 2147483647:
            errores.append(f"La banda {grupo} supera el máximo permitido.")
        else:
            grupos[grupo] = numero
    if actuales is not None and not errores \
            and sum(grupos.values()) != sum(actuales[g] for g in GRUPOS_EDAD_MUNICIPIO):
        errores.append("La suma de las cinco bandas debe conservar la población con edad declarada del municipio.")
    return grupos, errores


def valida_poblacion_municipio(population_raw, motivo, poblacion_60_actual=None):
    """(población, errores) del formulario de corrección. Con errores, la población no es de fiar."""
    errores = []
    poblacion = None
    if population_raw is None or str(population_raw).strip() == "":
        errores.append("La población total es obligatoria.")
    else:
        try:
            poblacion = int(str(population_raw).strip())
        except ValueError:
            errores.append("La población total debe ser un número entero.")
        else:
            if poblacion < 0:
                errores.append("La población total no puede ser negativa.")
                poblacion = None
    # El 60 y más no se captura: se deriva de las bandas (022). La corrección no puede dejar al
    # municipio con menos habitantes que su propio grupo de 60 y más.
    if poblacion is not None and poblacion_60_actual is not None and poblacion < poblacion_60_actual:
        errores.append(f"La población total no puede ser menor que las {poblacion_60_actual:,} personas de 60 "
                       f"años o más que el censo registra en este municipio.")
    if not motivo or not motivo.strip():
        errores.append("Indica la fuente o el motivo de la corrección.")
    elif len(motivo.strip()) > 500:
        errores.append("La fuente o motivo no puede pasar de 500 caracteres.")
    return poblacion, errores


# --- versiones ------------------------------------------------------------------------------------

def _foto(cur, region_id):
    cur.execute("SELECT population, population_60plus FROM regions WHERE id = %s", (region_id,))
    poblacion, p60 = cur.fetchone()
    cur.execute("SELECT age_group, lower_bound, population FROM region_age_groups WHERE region_id = %s",
                (region_id,))
    filas = cur.fetchall()
    grupos = {g: n for g, inferior, n in filas if inferior is not None}
    if filas:
        grupos["edad_no_especificada"] = next((n for _g, inferior, n in filas if inferior is None), 0)
    return poblacion, p60, grupos or None


def _asegura_version_1(cur, region_id):
    """Guarda como versión 1 las cifras de antes del primer ajuste."""
    cur.execute("SELECT 1 FROM population_versions WHERE region_id = %s LIMIT 1", (region_id,))
    if cur.fetchone():
        return
    cur.execute("SELECT 1 FROM region_population_adjustments WHERE region_id = %s LIMIT 1", (region_id,))
    fuente = FUENTE_CENSO + (", con ajustes manuales anteriores al historial" if cur.fetchone() else "")
    poblacion, p60, grupos = _foto(cur, region_id)
    cur.execute("""INSERT INTO population_versions (region_id, version, population, population_60plus,
                                                    age_groups, reference_year, source)
                   VALUES (%s, 1, %s, %s, %s::jsonb, %s, %s)""",
                (region_id, poblacion, p60, a_jsonb(grupos), ANIO_REFERENCIA, fuente))


def _agrega_version(cur, region_id, fuente, motivo, contexto):
    poblacion, p60, grupos = _foto(cur, region_id)
    cur.execute("""INSERT INTO population_versions (region_id, version, population, population_60plus,
                                                    age_groups, reference_year, source, reason, created_by)
                   SELECT %s, max(version) + 1, %s, %s, %s::jsonb, %s, %s, %s, %s
                     FROM population_versions WHERE region_id = %s
                   RETURNING version""",
                (region_id, poblacion, p60, a_jsonb(grupos), ANIO_REFERENCIA, fuente, motivo,
                 contexto.user_id, region_id))
    return cur.fetchone()[0]


def versiones(region_id):
    """Las versiones de una región, la más reciente primero. Sin ajustes, la vigente como versión 1."""
    filas = [dict(f) for f in query(
        """SELECT version, population, population_60plus, age_groups, reference_year, source, reason,
                  created_by, created_at
           FROM population_versions WHERE region_id = %s ORDER BY version DESC""", (region_id,))]
    if filas:
        return filas
    actual = query("SELECT population, population_60plus FROM regions WHERE id = %s", (region_id,), one=True)
    grupos = query("SELECT age_group, lower_bound, population FROM region_age_groups WHERE region_id = %s",
                   (region_id,))
    bandas = {g["age_group"]: g["population"] for g in grupos if g["lower_bound"] is not None}
    if grupos:
        bandas["edad_no_especificada"] = next((g["population"] for g in grupos if g["lower_bound"] is None), 0)
    return [{"version": 1, "population": actual["population"], "population_60plus": actual["population_60plus"],
             "age_groups": bandas or None, "reference_year": ANIO_REFERENCIA, "source": FUENTE_CENSO,
             "reason": None, "created_by": None, "created_at": None}]


def periodos(code):
    """La población de la región en cada censo o conteo de INEGI (census_population)."""
    return [dict(f) for f in query(
        "SELECT year AS anio, population AS poblacion, source AS fuente FROM census_population "
        "WHERE region_code = %s ORDER BY year", (code,))]


# --- corrección de la población total -------------------------------------------------------------

def actualiza_poblacion_municipio(region_id, population, motivo, esperado_population, *, contexto):
    """Corrige la población total de un municipio y recalcula el estado, con su bitácora y sus versiones,
    en una sola transacción. Control optimista con `esperado_population`. Regresa (ok, error, resultado)."""
    motivo = motivo.strip()
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, level, parent_region_id, population, population_60plus "
                            "FROM regions WHERE id = %s FOR UPDATE", (region_id,))
                fila = cur.fetchone()
                if not fila or fila[2] != "municipio":
                    return False, "Ese municipio ya no existe en el catálogo.", None
                _, nombre, _nivel, padre_id, pob_actual, pob60_actual = fila
                if pob_actual != esperado_population:
                    return False, ("Otra persona corrigió este municipio mientras editabas el formulario. "
                                   "Recarga la página y vuelve a intentarlo."), None
                cur.execute("SELECT id, population, population_60plus FROM regions WHERE id = %s FOR UPDATE",
                            (padre_id,))
                estado_antes = cur.fetchone()
                _asegura_version_1(cur, region_id)
                _asegura_version_1(cur, padre_id)

                cur.execute("UPDATE regions SET population = %s WHERE id = %s", (population, region_id))
                if pob_actual != population:
                    cur.execute(
                        """INSERT INTO region_population_adjustments
                               (region_id, field, census_value, previous_value, new_value, reason, adjusted_by,
                                adjusted_at)
                           VALUES (%s, 'population',
                                   COALESCE((SELECT census_value FROM region_population_adjustments
                                             WHERE region_id = %s AND field = 'population'), %s),
                                   %s, %s, %s, %s, now())
                           ON CONFLICT (region_id, field) DO UPDATE
                           SET previous_value = region_population_adjustments.new_value,
                               new_value = EXCLUDED.new_value, reason = EXCLUDED.reason,
                               adjusted_by = EXCLUDED.adjusted_by, adjusted_at = now()""",
                        (region_id, region_id, pob_actual, pob_actual, population, motivo, contexto.user_id))
                version = _agrega_version(cur, region_id, "Ajuste manual de la población total", motivo, contexto)
                log_audit(contexto, "UPDATE", "regions", region_id,
                          data_before={"id": region_id, "name": nombre, "population": pob_actual,
                                       "population_60plus": pob60_actual},
                          data_after={"id": region_id, "name": nombre, "population": population,
                                      "population_60plus": pob60_actual, "fuente_motivo": motivo,
                                      "version_poblacion": version}, cur=cur)

                # El estado es la suma de sus municipios; si a alguno le faltara la población no se
                # recalcula. Su 60 y más sale de sus bandas (022), no de aquí.
                cur.execute(
                    """UPDATE regions e
                       SET population = CASE WHEN sub.faltan_pob = 0 THEN sub.total_pob ELSE e.population END
                       FROM (SELECT sum(population) AS total_pob,
                                    count(*) FILTER (WHERE population IS NULL) AS faltan_pob
                             FROM regions WHERE parent_region_id = %s) sub
                       WHERE e.id = %s
                       RETURNING e.population, e.population_60plus, sub.faltan_pob""", (padre_id, padre_id))
                estado_despues = cur.fetchone()
                faltan_pob = estado_despues[2] if estado_despues else 0
                estado_cambio = (estado_antes is not None and estado_despues is not None
                                 and (estado_antes[1] != estado_despues[0] or estado_antes[2] != estado_despues[1]))
                if estado_cambio:
                    _agrega_version(cur, padre_id, "Agregado de los municipios", "Recalculado tras corregir %s: %s"
                                    % (nombre, motivo), contexto)
                    log_audit(contexto, "UPDATE", "regions", padre_id,
                              data_before={"population": estado_antes[1], "population_60plus": estado_antes[2],
                                           "nota": "agregado de los 51 municipios de Nuevo León"},
                              data_after={"population": estado_despues[0], "population_60plus": estado_despues[1],
                                          "nota": f"recalculado tras corregir {nombre}"}, cur=cur)
            conn.commit()
        return True, None, {"municipio": nombre, "poblacion_antes": pob_actual, "poblacion_despues": population,
                            "poblacion_60": pob60_actual, "estado_actualizado": estado_cambio,
                            "municipios_sin_poblacion": faltan_pob, "version": version}
    except psycopg2.errors.CheckViolation:
        return False, "Los datos no cumplen las restricciones de la base.", None


# --- corrección de las bandas de edad -------------------------------------------------------------

def _snap_grupos_edad(grupos, edad_no_especificada):
    return {"population_by_age": {g: grupos[g] for g in GRUPOS_EDAD_MUNICIPIO},
            "edad_no_especificada": edad_no_especificada}


def _valida_correccion_grupos(grupos, motivo):
    if not motivo or not motivo.strip():
        return "Indica la fuente o el motivo de la corrección."
    if len(motivo.strip()) > 500:
        return "La fuente o motivo no puede pasar de 500 caracteres."
    if set(grupos) != set(GRUPOS_EDAD_MUNICIPIO):
        return "Debes enviar las cinco bandas de edad."
    return None


def _bloquea_municipio(cur, region_id):
    cur.execute("""SELECT r.id, r.name, r.level, r.parent_region_id
                   FROM regions r JOIN regions e ON e.id = r.parent_region_id
                   WHERE r.id = %s AND e.code = %s FOR UPDATE OF r""", (region_id, NL_ESTADO_CODE))
    region = cur.fetchone()
    if not region or region[2] != "municipio":
        return None
    return region[0], region[1], region[3]


def _bloquea_grupos_edad(cur, region_id):
    cur.execute("SELECT age_group, lower_bound, population FROM region_age_groups WHERE region_id = %s FOR UPDATE",
                (region_id,))
    filas = cur.fetchall()
    return ({f[0]: f[2] for f in filas if f[1] is not None},
            next((f[2] for f in filas if f[1] is None), None))


def _revisa_correccion_grupos(grupos, esperados, actuales, edad_no_especificada):
    if set(actuales) != set(GRUPOS_EDAD_MUNICIPIO) or edad_no_especificada is None:
        return ("Este municipio no tiene todas sus bandas de edad cargadas. "
                "Vuelve a ejecutar la semilla nl_municipios_completos.sql.")
    if any(esperados.get(g) != actuales[g] for g in GRUPOS_EDAD_MUNICIPIO):
        return "Otra persona corrigió las bandas mientras editabas. Recarga la página e intenta de nuevo."
    if esperados.get("edad_no_especificada") != edad_no_especificada:
        return "Los datos del municipio cambiaron mientras editabas. Recarga la página e intenta de nuevo."
    if sum(grupos.values()) != sum(actuales.values()):
        return "La suma de las cinco bandas debe conservar la población con edad declarada del municipio."
    if all(grupos[g] == actuales[g] for g in GRUPOS_EDAD_MUNICIPIO):
        return "No hay cambios en las bandas de edad."
    return None


def _recalcula_grupos_estado(cur, estado_id):
    cur.execute("""SELECT age_group, sum(g.population) FROM region_age_groups g
                   JOIN regions m ON m.id = g.region_id
                   WHERE m.parent_region_id = %s AND m.level = 'municipio' GROUP BY age_group""", (estado_id,))
    totales = dict(cur.fetchall())
    cur.execute("SELECT age_group, population FROM region_age_groups WHERE region_id = %s FOR UPDATE", (estado_id,))
    antes = {f[0]: f[1] for f in cur.fetchall()}
    for grupo, total in totales.items():
        if antes.get(grupo) != total:
            cur.execute("UPDATE region_age_groups SET population = %s WHERE region_id = %s AND age_group = %s",
                        (total, estado_id, grupo))
    return antes, totales


def actualiza_grupos_edad_municipio(region_id, grupos, esperados, motivo, *, contexto):
    """Corrige las bandas de un municipio y su agregado estatal en una sola transacción, con bitácora y
    versiones. Conserva la suma con edad declarada; el trigger 022 deriva el 60 y más."""
    error = _valida_correccion_grupos(grupos, motivo)
    if error:
        return False, error, None
    motivo = motivo.strip()
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                municipio = _bloquea_municipio(cur, region_id)
                if municipio is None:
                    return False, "Ese municipio ya no existe en el catálogo.", None
                municipio_id, nombre, estado_id = municipio
                actuales, edad_no_especificada = _bloquea_grupos_edad(cur, region_id)
                error = _revisa_correccion_grupos(grupos, esperados, actuales, edad_no_especificada)
                if error:
                    return False, error, None
                _asegura_version_1(cur, region_id)
                _asegura_version_1(cur, estado_id)

                modificados = [g for g in GRUPOS_EDAD_MUNICIPIO if grupos[g] != actuales[g]]
                for grupo in modificados:
                    cur.execute("UPDATE region_age_groups SET population = %s WHERE region_id = %s AND age_group = %s",
                                (grupos[grupo], region_id, grupo))
                estado_antes, totales_estado = _recalcula_grupos_estado(cur, estado_id)

                cur.execute("SELECT age_group, population FROM region_age_groups WHERE region_id = %s", (region_id,))
                despues = {f[0]: f[1] for f in cur.fetchall()}
                cur.execute("SELECT population_60plus FROM regions WHERE id = %s", (region_id,))
                p60_despues = cur.fetchone()[0]
                version = _agrega_version(cur, region_id, "Corrección manual de las bandas de edad", motivo, contexto)
                log_audit(contexto, "UPDATE", "regions", municipio_id,
                          data_before=_snap_grupos_edad(actuales, edad_no_especificada),
                          data_after=dict(_snap_grupos_edad(despues, edad_no_especificada),
                                          population_60plus=p60_despues, age_groups_modified=modificados,
                                          age_correction_reason=motivo, version_poblacion=version), cur=cur)

                modificados_estado = [g for g in totales_estado if estado_antes.get(g) != totales_estado[g]]
                if modificados_estado:
                    motivo_estado = f"Agregado estatal tras corregir {nombre}: {motivo}"
                    _agrega_version(cur, estado_id, "Agregado de los municipios", motivo_estado, contexto)
                    log_audit(contexto, "UPDATE", "regions", estado_id,
                              data_before={"population_by_age": estado_antes},
                              data_after={"population_by_age": totales_estado, "age_groups_modified": modificados_estado,
                                          "age_correction_reason": motivo_estado}, cur=cur)
            conn.commit()
        return True, None, {"municipio": nombre, "population_60plus": p60_despues,
                            "estado_actualizado": bool(modificados_estado), "version": version}
    except psycopg2.errors.CheckViolation:
        return False, "Las bandas no cumplen las restricciones de la base.", None
