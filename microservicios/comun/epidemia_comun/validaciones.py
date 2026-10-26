import math

from .errores import ErrorAPI


def diccionario(datos):
    if not isinstance(datos, dict):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Se esperaba un objeto con campos.")
    return datos


def entero_positivo(valor, campo="id"):
    if isinstance(valor, bool):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El campo %s debe ser entero positivo." % campo)
    try:
        numero = int(valor)
    except (TypeError, ValueError, OverflowError):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El campo %s debe ser entero positivo." % campo)
    if numero < 1 or str(numero) != str(valor).strip():
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El campo %s debe ser entero positivo." % campo)
    return numero


def corridas_a_comparar(texto, maximo):
    # `runs=12,15,12`: de 2 a `maximo` ids distintos, en el orden en que llegaron.
    piezas = [p.strip() for p in (texto or "").split(",")]
    if not any(piezas):
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "Indica las corridas en runs, separadas por comas (por ejemplo, runs=12,15).")
    ids = []
    for pieza in piezas:
        numero = entero_positivo(pieza, "runs")
        if numero not in ids:
            ids.append(numero)
    if len(ids) < 2:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Se necesitan al menos dos corridas distintas.")
    if len(ids) > maximo:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "Se pueden comparar hasta %d corridas a la vez." % maximo)
    return ids


def parametros_epidemiologicos(nuevos, existentes=None):
    """Valida y une parámetros usando los límites que ya utiliza el monolito.

    Los porcentajes se reciben como fracciones (0 a 1) en la API.
    Las unidades 0 a 100 de PARAMETROS_SIMULACION son exclusivas del formulario.
    """
    from backend_web import queries
    diccionario(nuevos)
    permitidos = {s["clave"]: s for s in queries.PARAMETROS_SIMULACION}
    desconocidos = set(nuevos) - set(permitidos)
    if desconocidos:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Parámetros no reconocidos: " + ", ".join(sorted(desconocidos)))
    resultado = dict(existentes or {})
    for clave, crudo in nuevos.items():
        if crudo is None:
            resultado.pop(clave, None)
            continue
        if not isinstance(crudo, dict) or isinstance(crudo.get("valor"), bool):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "El parámetro %s necesita un valor numérico." % clave)
        numero = crudo.get("valor")
        # En XML sin atributos de tipo se reciben números como texto.
        if isinstance(numero, str):
            try:
                numero = float(numero)
            except ValueError:
                pass
        if not isinstance(numero, (float, int)) or not math.isfinite(numero):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "El valor de %s debe ser un número finito." % clave)
        spec = permitidos[clave]
        maximo = spec["max"] / 100.0 if spec.get("porcentaje") else spec["max"]
        minimo = spec["min"] / 100.0 if spec.get("porcentaje") else spec["min"]
        if not minimo <= numero <= maximo:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "El valor de %s está fuera de rango." % clave)
        fuente = crudo.get("fuente")
        supuesto = crudo.get("supuesto", False)
        if isinstance(supuesto, str) and supuesto.lower() in ("true", "false"):
            supuesto = supuesto.lower() == "true"
        if not isinstance(supuesto, bool) or (fuente is not None and not isinstance(fuente, str)):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Fuente o supuesto inválido para %s." % clave)
        if not (fuente and fuente.strip()) and not supuesto:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "El parámetro %s requiere fuente o marcar supuesto." % clave)
        if set(crudo) - {"valor", "fuente", "supuesto"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Campos desconocidos en %s." % clave)
        resultado[clave] = {"valor": numero, "fuente": fuente.strip() if fuente else None, "supuesto": supuesto}
    return resultado
