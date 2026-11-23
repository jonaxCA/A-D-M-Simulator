"""De una versión de escenario (filas de la base) a la entrada del motor. Sin Flask ni base."""

# ---------------------------------------------------------------------------
# Parametros de simulacion de una enfermedad
# ---------------------------------------------------------------------------
# Regla del proyecto: no se inventan parametros desde la interfaz. Cada valor
# se guarda con su fuente o marcado explicitamente como supuesto del equipo.
# El formato es el que consume el motor (ver motor/parametros.py):
#
#     "r0": {"valor": 1.3, "fuente": "Biggerstaff et al. 2014", "supuesto": false}
#
# El motor tambien acepta el numero pelon y el formato de distribucion que trae
# 010_datos_iniciales.sql ({"dist": "lognormal", "media": 5.1, ...}). Aqui se
# leen los tres para no romper lo ya cargado, pero lo que se ESCRIBE siempre
# lleva fuente o marca de supuesto.
#
# Son los seis que el motor exige para poder correr. Si falta uno, la
# enfermedad no se puede simular y la pantalla lo dice.

PARAMETROS_SIMULACION = [
    {"clave": "r0", "etiqueta": "R₀ — número reproductivo básico",
     "unidad": "contagios por caso", "min": 0.01, "max": 20.0, "paso": "0.01",
     "ayuda": "Contagios que genera un caso en una población sin inmunidad."},
    {"clave": "incubacion_dias", "etiqueta": "Período de incubación",
     "unidad": "días", "min": 0.1, "max": 60.0, "paso": "0.1",
     "ayuda": "Del contagio al inicio de síntomas. El motor usa la media."},
    {"clave": "infeccioso_dias", "etiqueta": "Período infeccioso",
     "unidad": "días", "min": 0.1, "max": 60.0, "paso": "0.1",
     "ayuda": "Cuánto tiempo puede contagiar una persona."},
    {"clave": "dias_hospitalizacion", "etiqueta": "Estancia hospitalaria",
     "unidad": "días", "min": 0.1, "max": 120.0, "paso": "0.1",
     "ayuda": "Duración promedio de la hospitalización."},
    {"clave": "tasa_hospitalizacion", "etiqueta": "Tasa de hospitalización",
     "unidad": "%", "porcentaje": True, "min": 0.0, "max": 100.0, "paso": "0.001",
     "ayuda": "De cada 100 infectados, cuántos terminan hospitalizados."},
    {"clave": "letalidad", "etiqueta": "Letalidad (IFR)",
     "unidad": "%", "porcentaje": True, "min": 0.0, "max": 100.0, "paso": "0.0001",
     "ayuda": "De cada 100 infectados, cuántos fallecen."},
]

# Claves que el esquema ya trae y que este formulario no edita. Se muestran
# como informativas y se conservan intactas al guardar: son del contrato con el
# motor de agentes que viene despues, no de este formulario.
PARAMETROS_INFORMATIVOS = {
    "prob_asintomatico": "Proporción de asintomáticos",
    "transmisibilidad_base": "Transmisibilidad base (modelo de agentes)",
    "letalidad_por_edad": "Letalidad por grupo de edad",
}


def _desarma_param(bruto):
    """(valor, fuente, supuesto) a partir de cualquiera de los tres formatos."""
    if isinstance(bruto, dict):
        if "valor" in bruto:
            return bruto.get("valor"), bruto.get("fuente"), bool(bruto.get("supuesto", False))
        if "media" in bruto:                      # formato de 010_datos_iniciales
            return bruto.get("media"), None, False
        return None, None, False
    if isinstance(bruto, (int, float)) and not isinstance(bruto, bool):
        return bruto, None, False
    return None, None, False


def estado_parametros(default_params):
    """Todo lo que la pantalla necesita saber de los parametros de una
    enfermedad: valor, procedencia y si alcanza para simular."""
    params = default_params or {}
    por_edad = params.get("letalidad_por_edad")
    tiene_por_edad = isinstance(por_edad, dict) and bool(por_edad)

    detalle, faltan, supuestos, sin_fuente = [], [], [], []
    for spec in PARAMETROS_SIMULACION:
        bruto = params.get(spec["clave"])
        valor, fuente, supuesto = _desarma_param(bruto)
        # El motor acepta letalidad_por_edad como alias de letalidad, asi que
        # una enfermedad con la tabla por edad ya cumple ese requisito.
        heredado = valor is None and spec["clave"] == "letalidad" and tiene_por_edad

        if valor is None and not heredado:
            estado = "falta"
            faltan.append(spec["clave"])
        elif heredado:
            estado = "por_grupo"
        elif supuesto:
            estado = "supuesto"
            supuestos.append(spec["clave"])
        elif fuente:
            estado = "con_fuente"
        else:
            estado = "sin_fuente"
            sin_fuente.append(spec["clave"])

        detalle.append({
            **spec,
            "valor": valor,
            # El formulario trabaja en % para las tasas; la base guarda 0–1.
            "valor_form": ("" if valor is None
                           else f"{valor * 100:g}" if spec.get("porcentaje") else f"{valor:g}"),
            "fuente": fuente or "",
            "supuesto": supuesto,
            # Incertidumbre (D58): {min, max, tipo} si la fuente la da. El motor no la usa.
            "intervalo": bruto.get("intervalo") if isinstance(bruto, dict) else None,
            "estado": estado,
        })

    # Un informativo puede venir pelado ({"0-19": 0.0001, ...}, como lo dejo
    # 010) o con trazabilidad ({"valor": {...}, "fuente": ..., "supuesto": ...},
    # como lo deja 020). Se desenvuelve aqui para que `valor` sea siempre el
    # dato, sin la fuente; el texto lo arma frontend_web.
    informativos = []
    for clave, etiqueta in PARAMETROS_INFORMATIVOS.items():
        bruto = params.get(clave)
        if bruto in (None, {}, ""):
            continue
        valor, fuente, supuesto = _desarma_param(bruto)
        if valor is None and isinstance(bruto, dict):
            valor = bruto                      # formato pelado: el valor es el dict
        if valor in (None, {}, ""):
            continue
        informativos.append({"etiqueta": etiqueta, "valor": valor,
                             "fuente": fuente or "", "supuesto": supuesto})

    return {
        "detalle": detalle,
        "informativos": informativos,
        "faltan": faltan,
        "supuestos": supuestos,
        "sin_fuente": sin_fuente,
        # Un valor sin fuente ni marca de supuesto tampoco alcanza: el sistema
        # se niega a simular con una cifra de la que nadie responde.
        "simulable": not faltan and not sin_fuente,
    }


def motivo_no_simulable(faltan, sin_fuente):
    """Por que una enfermedad no se puede simular, dado cuantos parametros le
    faltan y cuantos no tienen fuente ni marca de supuesto."""
    partes = []
    if faltan:
        partes.append(f"le faltan {faltan} parámetro(s)")
    if sin_fuente:
        partes.append(f"{sin_fuente} parámetro(s) no tienen fuente ni marca de supuesto")
    return " y ".join(partes)


def escenario_para_motor(datos, enfermedad_params, intervenciones=None):
    """Traduce una version de escenario al diccionario que consume el motor.

    Los nombres del motor se eligieron a proposito iguales a las columnas
    (`horizon_days` -> `dias`, `start_day` -> `dia_inicio`), asi que esto es un
    mapeo y no una conversion: si algun dia dejan de coincidir, se rompe aqui y
    no en medio de una corrida.
    """
    escenario = {
        "poblacion": datos["population_by_age"] or datos["population_size"],
        "infectados_iniciales": datos["initial_infected"],
        "dias": datos["horizon_days"],
        "enfermedad": enfermedad_params or {},
        "intervenciones": intervenciones or [],
    }
    if datos.get("population_age_unknown"):
        escenario["poblacion_edad_desconocida"] = datos["population_age_unknown"]
        escenario["politica_edad_desconocida"] = datos["age_unknown_policy"]
    return escenario


def escenario_de_version(detalle):
    """Entrada del motor para la version de `detalle` (get_escenario_detalle).

    La usan la revision (revisa_version) y la corrida
    (backend_web.simulaciones): lo que el epidemiologo aprueba y lo que se
    simula salen de la misma traduccion, con la misma poblacion por edad y los
    mismos parametros congelados.
    """
    version = detalle["version"]
    datos = {
        "population_by_age": version["population_by_age"],
        "population_size": version["population_size"],
        "population_age_unknown": version["population_age_unknown"],
        "age_unknown_policy": version["age_unknown_policy"],
        "initial_infected": version["initial_infected"],
        "horizon_days": version["horizon_days"],
    }
    return escenario_para_motor(datos, detalle["parametros_enfermedad"],
                                intervenciones_para_motor(detalle["intervenciones"]))



def intervenciones_para_motor(filas):
    """Filas de scenario_interventions -> lista que consume el motor."""
    return [{
        "tipo": f["code"],
        "dia_inicio": f["start_day"],
        "dia_fin": f["end_day"],
        "cobertura": float(f["coverage"]) if f["coverage"] is not None else None,
        "cumplimiento": float(f["compliance"]) if f["compliance"] is not None else None,
        "params": f["params"] or {},
    } for f in filas]




def entrada_de_version(version, intervenciones):
    if not version:
        return None, None, ["La version de escenario no existe."]
    if version["status"] != "aprobado":
        return None, version, [
            f"La version {version['version_number']} de ESC-{int(version['scenario_id']):03d} no "
            f"esta aprobada (estado: {version['status']}); solo se puede simular una version "
            f"aprobada."
        ]
    parametros = version["disease_params"] or version["default_params"]
    estado = estado_parametros(parametros)
    if not estado["simulable"]:
        return None, version, [
            f"La enfermedad de este escenario no se puede simular: "
            f"{motivo_no_simulable(len(estado['faltan']), len(estado['sin_fuente']))}."
        ]
    detalle = {"version": version, "parametros_enfermedad": parametros,
               "intervenciones": intervenciones}
    return escenario_de_version(detalle), version, []
