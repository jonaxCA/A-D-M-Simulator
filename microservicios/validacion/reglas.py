# Las reglas con que se revisa un escenario contra el motor (antes en backend_web.queries, E8). Son
# de validacion, cuya tarea es esa (catálogo): escenarios le pide el alta y las versiones nuevas por
# HTTP, y las intervenciones las revisa intervenciones (D37).
from epidemia_comun import conversion
from procesamiento.entrada_motor import escenario_de_version, escenario_para_motor, motivo_no_simulable
from procesamiento.motor.parametros import (DIAS_MAX, DIAS_MIN, POBLACION_MAX, POBLACION_MIN,
                                            POLITICAS_EDAD_DESCONOCIDA, EscenarioInvalido, resolver,
                                            validar_escenario)


def valida_escenario(form, regiones, enfermedades, parametros_de):
    # (datos, errores). Sin estratificar, la población sale de la región y se puede editar;
    # estratificando, no: el reparto por edad es censal, y escalarlo lo volvería una invención.
    # `parametros_de(disease_id)` da los default_params; solo se consulta si el formulario cuadra.
    errores = []
    nombre = (form.get("name") or "").strip()
    if not nombre:
        errores.append("El nombre del escenario es obligatorio.")
    elif len(nombre) > 160:
        errores.append("El nombre no puede pasar de 160 caracteres.")
    region_id = conversion.entero(form.get("region_id"), errores, etiqueta="La región",
                                  minimo=1, maximo=2**31 - 1)
    region = {r["id"]: r for r in regiones}.get(region_id)
    if region_id is not None and region is None:
        errores.append("Esa región no está en el catálogo de Nuevo León.")
    disease_id = conversion.entero(form.get("disease_id"), errores, etiqueta="La enfermedad",
                                   minimo=1, maximo=2**31 - 1)
    enfermedad = {e["id"]: e for e in enfermedades}.get(disease_id)
    if disease_id is not None and enfermedad is None:
        errores.append("Esa enfermedad no está activa en el catálogo.")
    elif enfermedad and not enfermedad["simulable"]:
        errores.append(
            "«%s» no se puede simular todavía: %s. Complétalos en Enfermedades."
            % (enfermedad["name"], motivo_no_simulable(enfermedad["faltan"], enfermedad["sin_fuente"])))
    dias, poblacion, grupos, sin_edad, politica, iniciales = valida_parametros_version(form, region, errores)
    datos = {
        "name": nombre, "description": (form.get("description") or "").strip() or None,
        "disease_id": disease_id, "region_id": region_id,
        "population_size": poblacion, "horizon_days": dias,
        "initial_infected": iniciales, "population_by_age": grupos,
        "population_age_unknown": sin_edad or 0, "age_unknown_policy": politica,
        "notes": (form.get("notes") or "").strip() or None,
    }
    if errores:
        return datos, errores
    # El motor solo se consulta si el formulario cuadra: sus errores hablan de parámetros de la
    # enfermedad, y mezclarlos con «falta el nombre» confunde.
    errores += ["El motor rechaza el escenario: %s" % e
                for e in validar_escenario(escenario_para_motor(datos, parametros_de(disease_id)))]
    return datos, errores


def valida_parametros_version(form, region, errores):
    # Lo que cambia de una versión a otra; lo comparten el alta y las versiones nuevas.
    dias = conversion.entero(form.get("horizon_days"), errores,
                             etiqueta="La duración en días", minimo=DIAS_MIN, maximo=DIAS_MAX)
    grupos = sin_edad = politica = poblacion = None
    if form.get("estratificar"):
        if region is None:
            pass
        elif not region["grupos"]:
            errores.append("Esa región no tiene población por grupo de edad cargada; "
                           "no se puede estratificar.")
        else:
            grupos = {g: int(n) for g, n in region["grupos"].items()}
            sin_edad = int(region["sin_edad"])
            poblacion = sum(grupos.values()) + sin_edad
            if sin_edad:
                politica = form.get("age_unknown_policy")
                if politica not in POLITICAS_EDAD_DESCONOCIDA:
                    errores.append("%s personas de esta región no declararon su edad: "
                                   "elige qué hacer con ellas." % format(sin_edad, ","))
                    politica = None
    else:
        poblacion = conversion.entero(form.get("population_size"), errores, etiqueta="La población",
                                      minimo=POBLACION_MIN, maximo=POBLACION_MAX)
    iniciales = conversion.entero(form.get("initial_infected"), errores,
                                  etiqueta="Los infectados iniciales", minimo=1, maximo=POBLACION_MAX)
    if iniciales is not None and poblacion is not None and iniciales > poblacion:
        errores.append("Los infectados iniciales no pueden superar la población.")
    return dias, poblacion, grupos, sin_edad, politica, iniciales


def valida_version(form, region, enfermedad_params):
    # El nombre, la enfermedad y la región no cambian entre versiones. El comentario sí se exige:
    # un historial sin el motivo de cada cambio no explica cómo llegó el escenario a donde está.
    errores = []
    dias, poblacion, grupos, sin_edad, politica, iniciales = valida_parametros_version(form, region, errores)
    notas = (form.get("notes") or "").strip()
    if not notas:
        errores.append("Explica en el comentario qué cambia esta versión.")
    elif len(notas) > 1000:
        errores.append("El comentario no puede pasar de 1,000 caracteres.")
    datos = {
        "population_size": poblacion, "horizon_days": dias,
        "initial_infected": iniciales, "population_by_age": grupos,
        "population_age_unknown": sin_edad or 0, "age_unknown_policy": politica,
        "notes": notas or None,
    }
    if errores:
        return datos, errores
    errores += ["El motor rechaza el escenario: %s" % e
                for e in validar_escenario(escenario_para_motor(datos, enfermedad_params))]
    return datos, errores


def revisa_version(detalle):
    # (errores, avisos) de la versión completa contra el motor. Los avisos importan: ahí dice el
    # motor, por ejemplo, que una prioridad de vacunación se degrada a aleatoria.
    if not detalle["version"]:
        return ["El escenario no tiene una versión vigente."], []
    try:
        return [], resolver(escenario_de_version(detalle))["avisos"]
    except EscenarioInvalido as exc:
        return list(exc.errores), []
