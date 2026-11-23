# Los rangos de los parámetros epidemiológicos (D37: la regla es de parametros; antes vivía en
# epidemia_comun/validaciones.py y leía los límites de backend_web). Los límites son los de
# procesamiento.entrada_motor, los mismos que usa el motor. Las tasas van como fracción (0 a 1).
import math

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.validaciones import diccionario
from procesamiento.entrada_motor import PARAMETROS_SIMULACION

# Cómo se obtuvo el intervalo de incertidumbre (D58).
TIPOS_INTERVALO = ("IC95", "RIC", "rango")


def _invalido(mensaje):
    return ErrorAPI(422, "DATOS_INVALIDOS", mensaje)


def _numero(crudo, mensaje):
    # En XML sin atributos de tipo los números llegan como texto.
    if isinstance(crudo, str):
        try:
            crudo = float(crudo)
        except ValueError:
            pass
    if isinstance(crudo, bool) or not isinstance(crudo, (float, int)) or not math.isfinite(crudo):
        raise _invalido(mensaje)
    return crudo


def _intervalo(crudo, clave, valor, minimo, maximo):
    if not isinstance(crudo, dict) or set(crudo) - {"min", "max", "tipo"} or not {"min", "max"} <= set(crudo):
        raise _invalido("El intervalo de %s lleva min, max y, opcional, tipo." % clave)
    bajo = _numero(crudo["min"], "El intervalo de %s debe tener números finitos." % clave)
    alto = _numero(crudo["max"], "El intervalo de %s debe tener números finitos." % clave)
    if not minimo <= bajo <= valor <= alto <= maximo:
        raise _invalido("El intervalo de %s debe contener el valor y caber en el rango del parámetro." % clave)
    tipo = crudo.get("tipo", "rango")
    if tipo not in TIPOS_INTERVALO:
        raise _invalido("El tipo de intervalo de %s debe ser uno de: %s." % (clave, ", ".join(TIPOS_INTERVALO)))
    return {"min": bajo, "max": alto, "tipo": tipo}


def parametros_epidemiologicos(nuevos, existentes=None):
    """Valida los parámetros nuevos y los une a los que ya había; None borra uno."""
    diccionario(nuevos)
    permitidos = {s["clave"]: s for s in PARAMETROS_SIMULACION}
    desconocidos = set(nuevos) - set(permitidos)
    if desconocidos:
        raise _invalido("Parámetros no reconocidos: " + ", ".join(sorted(desconocidos)))
    resultado = dict(existentes or {})
    for clave, crudo in nuevos.items():
        if crudo is None:
            resultado.pop(clave, None)
            continue
        if not isinstance(crudo, dict) or isinstance(crudo.get("valor"), bool):
            raise _invalido("El parámetro %s necesita un valor numérico." % clave)
        if set(crudo) - {"valor", "fuente", "supuesto", "intervalo"}:
            raise _invalido("Campos desconocidos en %s." % clave)
        numero = _numero(crudo.get("valor"), "El valor de %s debe ser un número finito." % clave)
        spec = permitidos[clave]
        escala = 100.0 if spec.get("porcentaje") else 1.0
        minimo, maximo = spec["min"] / escala, spec["max"] / escala
        if not minimo <= numero <= maximo:
            raise _invalido("El valor de %s está fuera de rango." % clave)
        fuente = crudo.get("fuente")
        supuesto = crudo.get("supuesto", False)
        if isinstance(supuesto, str) and supuesto.lower() in ("true", "false"):
            supuesto = supuesto.lower() == "true"
        if not isinstance(supuesto, bool) or (fuente is not None and not isinstance(fuente, str)):
            raise _invalido("Fuente o supuesto inválido para %s." % clave)
        if not (fuente and fuente.strip()) and not supuesto:
            raise _invalido("El parámetro %s requiere fuente o marcar supuesto." % clave)
        resultado[clave] = {"valor": numero, "fuente": fuente.strip() if fuente else None, "supuesto": supuesto}
        if crudo.get("intervalo") is not None:
            resultado[clave]["intervalo"] = _intervalo(crudo["intervalo"], clave, numero, minimo, maximo)
    return resultado
