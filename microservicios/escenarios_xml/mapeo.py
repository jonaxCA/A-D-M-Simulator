"""Traducciones entre el documento XML del escenario y los cuerpos de los otros servicios.

TODO lo que depende de la forma exacta que aceptan `escenarios`, `intervenciones` y
`validacion` está aquí, en las funciones `cuerpo_*` e `ids_de_respuesta`/`fallas_de`. Si
esos servicios cambian un nombre de campo, solo se ajusta este módulo.
"""
import json
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

GRUPOS_EDAD = ("0-19", "20-39", "40-59", "60-79", "80+")
VERSION_ESQUEMA = "1.0"


# --------------------------------------------------------------------------- exportar

def _texto_proporcion(valor):
    return str(Decimal(str(valor)).quantize(Decimal("0.001")))


def _agregar_parametro(padre, nombre, valor):
    nodo = ET.SubElement(padre, "parametro", nombre=str(nombre))
    if isinstance(valor, bool):
        nodo.set("tipo", "booleano")
        nodo.text = "true" if valor else "false"
    elif isinstance(valor, int):
        nodo.set("tipo", "entero")
        nodo.text = str(valor)
    elif isinstance(valor, (float, Decimal)):
        nodo.set("tipo", "numero")
        nodo.text = str(valor)
    elif isinstance(valor, str):
        nodo.set("tipo", "texto")
        nodo.text = valor
    elif isinstance(valor, list) and all(isinstance(x, str) for x in valor):
        nodo.set("tipo", "lista")
        for elemento in valor:
            ET.SubElement(nodo, "elemento").text = elemento
    else:
        nodo.set("tipo", "json")
        nodo.text = json.dumps(valor, ensure_ascii=False, default=str)


def construir_documento(datos):
    """Arma el XML del escenario a partir de lectura.leer_escenario(). Devuelve bytes UTF-8.

    Lanza ValueError si la población por edad de la versión no tiene los cinco grupos.
    """
    esc, ver = datos["escenario"], datos["version"]
    raiz = ET.Element("escenario", esquema=VERSION_ESQUEMA, id=str(esc["id"]))
    ET.SubElement(raiz, "nombre").text = esc["name"]
    if esc.get("description"):
        ET.SubElement(raiz, "descripcion").text = esc["description"]
    enf = ET.SubElement(raiz, "enfermedad", codigo=esc["disease_code"])
    if esc.get("disease_name"):
        enf.set("nombre", esc["disease_name"])
    reg = ET.SubElement(raiz, "region", codigo=esc["region_code"])
    if esc.get("region_name"):
        reg.set("nombre", esc["region_name"])

    nodo_v = ET.SubElement(raiz, "version", numero=str(ver["version_number"]))
    if ver.get("status"):
        nodo_v.set("estado", ver["status"])
    nodo_v.set("vigente", "true" if ver.get("is_current") else "false")
    pob = ET.SubElement(nodo_v, "poblacion", total=str(ver["population_size"]))
    por_edad = ver.get("population_by_age")
    if por_edad:
        if set(por_edad) != set(GRUPOS_EDAD):
            raise ValueError("La población por edad no tiene los grupos %s." % ", ".join(GRUPOS_EDAD))
        nodo_e = ET.SubElement(pob, "por_edad")
        for grupo in GRUPOS_EDAD:
            ET.SubElement(nodo_e, "grupo", edad=grupo).text = str(int(por_edad[grupo]))
    sin_edad = ver.get("population_age_unknown") or 0
    if sin_edad:
        nodo = ET.SubElement(pob, "edad_no_especificada")
        if ver.get("age_unknown_policy"):
            nodo.set("politica", ver["age_unknown_policy"])
        nodo.text = str(int(sin_edad))
    ET.SubElement(nodo_v, "horizonte_dias").text = str(ver["horizon_days"])
    ET.SubElement(nodo_v, "infectados_iniciales").text = str(ver["initial_infected"])
    if ver.get("notes"):
        ET.SubElement(nodo_v, "notas").text = ver["notes"]
    nodo_i = ET.SubElement(nodo_v, "intervenciones")
    for pos, i in enumerate(datos["intervenciones"]):
        orden = i.get("order_index")
        nodo = ET.SubElement(nodo_i, "intervencion",
                             orden=str(pos if orden is None else orden), tipo=i["type_code"])
        if i.get("region_code"):
            nodo.set("region", i["region_code"])
        ET.SubElement(nodo, "inicio_dia").text = str(i["start_day"])
        if i.get("end_day") is not None:
            ET.SubElement(nodo, "fin_dia").text = str(i["end_day"])
        if i.get("coverage") is not None:
            ET.SubElement(nodo, "cobertura").text = _texto_proporcion(i["coverage"])
        if i.get("compliance") is not None:
            ET.SubElement(nodo, "cumplimiento").text = _texto_proporcion(i["compliance"])
        if i.get("params"):
            nodo_p = ET.SubElement(nodo, "parametros")
            for nombre, valor in i["params"].items():
                _agregar_parametro(nodo_p, nombre, valor)
    ET.indent(raiz)
    return ET.tostring(raiz, encoding="utf-8", xml_declaration=True)


# --------------------------------------------------------------------------- importar

def _valor_parametro(nodo):
    tipo, texto = nodo.get("tipo"), (nodo.text or "")
    if tipo == "lista":
        return [e.text or "" for e in nodo.findall("elemento")]
    if tipo == "texto":
        return texto
    if tipo == "booleano":
        if texto.strip() not in ("true", "false", "1", "0"):
            raise ValueError("no es un booleano")
        return texto.strip() in ("true", "1")
    if tipo == "entero":
        return int(texto.strip())
    if tipo == "numero":
        valor = float(texto.strip())
        if valor != valor or valor in (float("inf"), float("-inf")):
            raise ValueError("no es un número finito")
        return valor
    return json.loads(texto)


def leer_documento(raiz):
    """Convierte el elemento <escenario> (ya válido contra el XSD) en un dict de dominio.

    Devuelve (doc, fallas); fallas es una lista de (ruta, mensaje) con los valores de
    parámetros que no se pudieron convertir a su tipo.
    """
    fallas = []
    ver = raiz.find("version")
    pob = ver.find("poblacion")
    por_edad = None
    if pob.find("por_edad") is not None:
        por_edad = {g.get("edad"): int(g.text) for g in pob.find("por_edad").findall("grupo")}
    sin = pob.find("edad_no_especificada")
    intervenciones = []
    for nodo in ver.find("intervenciones").findall("intervencion"):
        params = {}
        nodo_p = nodo.find("parametros")
        for p in (nodo_p.findall("parametro") if nodo_p is not None else []):
            try:
                params[p.get("nombre")] = _valor_parametro(p)
            except (ValueError, TypeError):
                fallas.append(("/escenario/version/intervenciones/intervencion[@orden='%s']"
                               "/parametros/parametro[@nombre='%s']" % (nodo.get("orden"), p.get("nombre")),
                               "El valor no corresponde al tipo %s." % p.get("tipo")))

        def numero(nombre, conversor):
            hijo = nodo.find(nombre)
            return None if hijo is None else conversor(hijo.text.strip())
        intervenciones.append({
            "orden": int(nodo.get("orden")), "tipo": nodo.get("tipo"), "region": nodo.get("region"),
            "inicio": numero("inicio_dia", int), "fin": numero("fin_dia", int),
            "cobertura": numero("cobertura", float), "cumplimiento": numero("cumplimiento", float),
            "params": params})
    intervenciones.sort(key=lambda i: i["orden"])
    descripcion = raiz.findtext("descripcion")
    notas = ver.findtext("notas")
    return {
        "nombre": raiz.findtext("nombre").strip(),
        "descripcion": descripcion.strip() if descripcion and descripcion.strip() else None,
        "enfermedad": raiz.find("enfermedad").get("codigo"),
        "region": raiz.find("region").get("codigo"),
        "numero_version": int(ver.get("numero")),
        "poblacion_total": int(pob.get("total")),
        "por_edad": por_edad,
        "sin_edad": int(sin.text) if sin is not None else 0,
        "politica": sin.get("politica") if sin is not None else None,
        "horizonte": int(ver.findtext("horizonte_dias")),
        "infectados": int(ver.findtext("infectados_iniciales")),
        "notas": notas.strip() if notas and notas.strip() else None,
        "intervenciones": intervenciones,
    }, fallas


def reglas_documento(doc):
    """Reglas entre campos que el XSD no expresa. Devuelve lista de (ruta, mensaje)."""
    fallas = []
    base = "/escenario/version"
    if doc["por_edad"] is not None:
        suma = sum(doc["por_edad"].values()) + doc["sin_edad"]
        if suma != doc["poblacion_total"]:
            fallas.append((base + "/poblacion",
                           "La suma de los grupos de edad (%d, con la edad no especificada) debe ser "
                           "igual al total de la población (%d)." % (suma, doc["poblacion_total"])))
    elif doc["sin_edad"]:
        fallas.append((base + "/poblacion/edad_no_especificada",
                       "La edad no especificada exige el reparto por_edad."))
    if doc["sin_edad"] and not doc["politica"]:
        fallas.append((base + "/poblacion/edad_no_especificada/@politica",
                       "Falta la política (excluir o prorratear) para la población sin edad."))
    if not doc["sin_edad"] and doc["politica"]:
        fallas.append((base + "/poblacion/edad_no_especificada/@politica",
                       "No puede haber política si no hay población sin edad."))
    if doc["infectados"] > doc["poblacion_total"]:
        fallas.append((base + "/infectados_iniciales",
                       "Los infectados iniciales no pueden pasar de la población."))
    for i in doc["intervenciones"]:
        ruta = base + "/intervenciones/intervencion[@orden='%d']" % i["orden"]
        if i["fin"] is not None and i["fin"] < i["inicio"]:
            fallas.append((ruta + "/fin_dia", "El día de fin no puede ser anterior al de inicio."))
        if i["inicio"] > doc["horizonte"]:
            fallas.append((ruta + "/inicio_dia", "El día de inicio no puede pasar del horizonte."))
        if i["fin"] is not None and i["fin"] > doc["horizonte"]:
            fallas.append((ruta + "/fin_dia", "El día de fin no puede pasar del horizonte."))
    return fallas


# ------------------------------------------------------- cuerpos hacia otros servicios

def cuerpo_escenarios(doc, ids):
    """Cuerpo de POST /api/v1/scenarios (escenarios): solo los campos de CAMPOS_ALTA.

    escenarios no recibe la población por edad: la toma del censo de la región cuando
    `stratify` es verdadero. El reparto del XML se compara contra el censo en validacion
    (ver cuerpo_validacion). Los valores nulos se omiten.
    """
    cuerpo = {"name": doc["nombre"], "description": doc["descripcion"],
              "disease_id": ids["enfermedad"], "region_id": ids["region"],
              "population_size": doc["poblacion_total"], "horizon_days": doc["horizonte"],
              "initial_infected": doc["infectados"], "notes": doc["notas"],
              "stratify": doc["por_edad"] is not None}
    if doc["por_edad"] is not None and doc["politica"]:
        cuerpo["age_unknown_policy"] = doc["politica"]
    return {k: v for k, v in cuerpo.items() if v is not None}


def cuerpo_intervencion(intervencion, ids):
    """Cuerpo de POST /api/v1/versions/{vid}/interventions (intervenciones).

    intervenciones rechaza (422) todo campo fuera de code, start_day, end_day, coverage,
    compliance y params; no admite id del tipo ni región destino.
    """
    cuerpo = {"code": intervencion["tipo"], "start_day": intervencion["inicio"],
              "end_day": intervencion["fin"], "coverage": intervencion["cobertura"],
              "compliance": intervencion["cumplimiento"]}
    if intervencion["params"]:
        cuerpo["params"] = intervencion["params"]
    return {k: v for k, v in cuerpo.items() if v is not None}


def cuerpo_validacion(doc, ids):
    """Cuerpo (JSON) PLANO de POST /api/v1/validate (validacion), con los nombres del
    formulario del monolito: el escenario y, dentro, `interventions`."""
    cuerpo = {"name": doc["nombre"], "description": doc["descripcion"],
              "disease_id": ids["enfermedad"], "region_id": ids["region"],
              "population_size": doc["poblacion_total"], "horizon_days": doc["horizonte"],
              "initial_infected": doc["infectados"], "notes": doc["notas"],
              "estratificar": doc["por_edad"] is not None,
              "age_unknown_policy": doc["politica"] if doc["por_edad"] is not None else None,
              "interventions": [cuerpo_intervencion(i, ids) for i in doc["intervenciones"]]}
    if doc["por_edad"] is not None:
        cuerpo["population_by_age"] = {g: doc["por_edad"][g] for g in GRUPOS_EDAD}
    return {k: v for k, v in cuerpo.items() if v is not None}


def avisos_de_importacion(doc):
    """Avisos de lo que el XML dice y el alta no puede conservar."""
    avisos = []
    for i in doc["intervenciones"]:
        if i["region"]:
            avisos.append("Se ignoró la región %s de la intervención %s (orden %d): el servicio "
                          "intervenciones no guarda región destino." % (i["region"], i["tipo"], i["orden"]))
    return avisos


# ------------------------------------------------------ respuestas de otros servicios

def _como_lista(valor):
    if valor is None or valor == "":
        return []
    if isinstance(valor, dict) and "item" in valor:  # lista que llegó por XML
        valor = valor["item"]
    return valor if isinstance(valor, list) else [valor]


def fallas_de(cuerpo, *claves):
    """Lee la lista de errores o avisos de validacion como [(ruta, mensaje)]."""
    if not isinstance(cuerpo, dict):
        return []
    for clave in claves:
        if cuerpo.get(clave):
            salida = []
            for item in _como_lista(cuerpo[clave]):
                if isinstance(item, dict):
                    ruta = item.get("campo") or item.get("field") or item.get("ruta") or ""
                    mensaje = item.get("mensaje") or item.get("message") or item.get("detalle") or json.dumps(item, ensure_ascii=False)
                    salida.append((str(ruta), str(mensaje)))
                else:
                    salida.append(("", str(item)))
            return salida
    return []


def entero_de(cuerpo, *rutas):
    """Primer entero hallado en cuerpo siguiendo cada ruta ("id", "version.id")."""
    for ruta in rutas:
        actual = cuerpo
        for parte in ruta.split("."):
            actual = actual.get(parte) if isinstance(actual, dict) else None
        try:
            if actual is not None and not isinstance(actual, bool):
                return int(actual)
        except (TypeError, ValueError):
            pass
    return None


def ids_de_respuesta(cuerpo):
    """(scenario_id, version_id) de la respuesta de POST /api/v1/scenarios."""
    return (entero_de(cuerpo, "scenario_id", "id", "escenario.id"),
            entero_de(cuerpo, "version_id", "version.id", "version_actual.id"))
