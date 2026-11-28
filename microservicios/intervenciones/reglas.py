# Las reglas de una intervención (antes en backend_web.queries, E8): sus parámetros salen del
# param_schema de su tipo, así que un tipo nuevo es una fila del catálogo y no código. Las usan
# las rutas de alta y POST /interventions/validate, que pide validacion (D37).
import math

from epidemia_comun import conversion


def valida_costo_intervencion(texto, fuente, supuesto, nombre="El importe"):
    # También el factor de personas-día por dosis (D3): las reglas y las llaves son las mismas.
    errores = []
    texto = (texto or "").strip()
    if not texto:
        return None, ["%s es obligatorio." % nombre]
    try:
        costo = float(texto)
    except ValueError:
        costo = None
    # "nan" e "inf" convierten sin error y la columna numeric los guardaría.
    if costo is None or not math.isfinite(costo):
        return None, ["%s debe ser numerico." % nombre]
    if costo < 0:
        errores.append("%s no puede ser negativo." % nombre)
    supuesto = bool(supuesto)
    if not supuesto and not (fuente or "").strip():
        que = "Un costo" if nombre == "El importe" else nombre
        errores.append("%s que no es supuesto debe incluir una fuente." % que)
    return {"unit_cost": costo, "cost_source": (fuente or "").strip() or None,
            "cost_is_assumption": supuesto}, errores


def params_desde_schema(form, schema, errores, prefijo="p_"):
    esquema = schema or {}
    requeridos = set(esquema.get("required") or [])
    salida = {}
    for clave, spec in (esquema.get("properties") or {}).items():
        etiqueta = "«%s»" % clave
        crudo = (form.get(prefijo + clave) or "").strip()
        if crudo == "":
            if clave in requeridos:
                errores.append("%s es obligatorio para este tipo de intervención." % etiqueta)
            continue
        if spec.get("enum"):
            if crudo not in spec["enum"]:
                errores.append("%s debe ser uno de: %s." % (etiqueta, ", ".join(spec["enum"])))
                continue
            salida[clave] = crudo
        elif spec.get("type") in ("integer", "number"):
            valor = conversion.numero_de_esquema(
                crudo, errores, etiqueta=etiqueta, spec=spec,
                tipo=int if spec["type"] == "integer" else float)
            if valor is not None:
                salida[clave] = valor
        elif spec.get("type") == "array":
            partes = [p.strip() for p in crudo.split(",") if p.strip()]
            if partes:
                salida[clave] = partes
        else:
            salida[clave] = crudo
    return salida


def se_traslapan(inicio_a, fin_a, inicio_b, fin_b, horizonte):
    # Dos del mismo tipo encimadas en el tiempo duplican su efecto. Sin fin, hasta el horizonte.
    fin_a = horizonte if fin_a is None else fin_a
    fin_b = horizonte if fin_b is None else fin_b
    return inicio_a <= fin_b and inicio_b <= fin_a


def valida_intervencion(form, tipos, version, existentes):
    # El traslape es más amplio que el índice único de la base, que solo atrapa el mismo tipo
    # empezando el mismo día.
    errores = []
    horizonte = version["horizon_days"]
    code = (form.get("code") or "").strip()
    tipo = {t["code"]: t for t in tipos}.get(code)
    if tipo is None:
        errores.append("Elige un tipo de intervención del catálogo.")
    inicio = conversion.entero(form.get("start_day"), errores, etiqueta="El día de inicio",
                               minimo=0, maximo=horizonte)
    fin = None
    crudo_fin = (form.get("end_day") or "").strip()
    if crudo_fin:
        fin = conversion.entero(crudo_fin, errores, etiqueta="El día de fin", minimo=0, maximo=horizonte)
        if fin is not None and inicio is not None and fin < inicio:
            errores.append("El día de fin no puede ser anterior al de inicio.")
            fin = None
    factores = {}
    for campo, etiqueta in (("coverage", "La cobertura"), ("compliance", "El cumplimiento")):
        crudo = (form.get(campo) or "").strip()
        if crudo == "":
            factores[campo] = None
            continue
        try:
            valor = float(crudo)
        except ValueError:
            errores.append("%s debe ser un número entre 0 y 1." % etiqueta)
            continue
        if not 0 <= valor <= 1:
            errores.append("%s debe estar entre 0 y 1." % etiqueta)
            continue
        factores[campo] = valor
    # El prefijo lleva el tipo: CIERRE_ESCUELAS, CIERRE_TRABAJO y REDUCCION_AFORO comparten
    # «reduccion», y con un prefijo común se tomaría el de otro tipo sin avisar.
    params = params_desde_schema(form, tipo["param_schema"] if tipo else None, errores,
                                 prefijo="p_%s_" % code if code else "p_")
    if tipo and inicio is not None:
        for otra in existentes:
            if otra["code"] == code and se_traslapan(inicio, fin, otra["start_day"], otra["end_day"],
                                                     horizonte):
                fin_otra = otra["end_day"] if otra["end_day"] is not None else horizonte
                errores.append(
                    "Ya hay una intervención «%s» del día %s al %s, y esta se traslapa. Dos del "
                    "mismo tipo encimadas contarían su efecto dos veces: ajusta las fechas o quita "
                    "la otra." % (tipo["name"], otra["start_day"], fin_otra))
                break
    return {"intervention_type_id": tipo["id"] if tipo else None, "code": code, "start_day": inicio,
            "end_day": fin, "coverage": factores.get("coverage"),
            "compliance": factores.get("compliance"), "params": params}, errores
