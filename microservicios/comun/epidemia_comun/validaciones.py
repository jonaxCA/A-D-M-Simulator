from datetime import date

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


def fecha(valor, campo):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser una fecha AAAA-MM-DD." % campo)
