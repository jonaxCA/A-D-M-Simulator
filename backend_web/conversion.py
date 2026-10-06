"""Conversion del texto de un formulario a int, float o date.

Cada funcion devuelve el valor convertido, o None si el campo falta o no pasa;
en ese caso el motivo, listo para mostrarse, queda en `errores`. Las reglas de
dominio (que una fecha no sea futura, que el inicio no pase del fin) no viven
aqui: las aplican las valida_* de queries.py.

No importa Flask: recibe el texto, venga de un formulario web o de cualquier
otro lado.
"""
from datetime import date


def _texto(valor):
    return "" if valor is None else str(valor).strip()


def _a_numero(texto, errores, etiqueta, tipo):
    try:
        return tipo(texto)
    except ValueError:
        errores.append(f"{etiqueta} debe ser un número{' entero' if tipo is int else ''}.")
        return None


def _en_rango(n, errores, etiqueta, minimo, maximo, miles):
    if minimo <= n <= maximo:
        return n
    rango = f"{minimo:,} y {maximo:,}" if miles else f"{minimo} y {maximo}"
    errores.append(f"{etiqueta} debe estar entre {rango}.")
    return None


def entero(valor, errores, *, etiqueta, minimo, maximo, obligatorio=True,
           falta=None, miles=True):
    """Entero entre `minimo` y `maximo`, ambos incluidos.

    Con `miles` acepta "1,000" y escribe los limites del mensaje con separador
    de miles. `falta` sustituye al mensaje de campo vacio
    ("<etiqueta> es obligatoria.").
    """
    texto = _texto(valor)
    if not texto:
        if obligatorio:
            errores.append(falta or f"{etiqueta} es obligatoria.")
        return None
    n = _a_numero(texto.replace(",", "") if miles else texto, errores, etiqueta, int)
    return None if n is None else _en_rango(n, errores, etiqueta, minimo, maximo, miles)


def decimal(valor, errores, *, etiqueta, minimo, maximo):
    """Numero entre `minimo` y `maximo`. Es opcional: vacio devuelve None sin error."""
    texto = _texto(valor)
    if not texto:
        return None
    n = _a_numero(texto, errores, etiqueta, float)
    return None if n is None else _en_rango(n, errores, etiqueta, minimo, maximo, miles=False)


def fecha(valor, errores, *, etiqueta, obligatorio=True):
    """Fecha en formato AAAA-MM-DD."""
    texto = _texto(valor)
    if not texto:
        if obligatorio:
            errores.append(f"{etiqueta} es obligatoria.")
        return None
    try:
        return date.fromisoformat(texto)
    except ValueError:
        errores.append(f"{etiqueta} no tiene un formato de fecha válido.")
        return None


def numero_de_esquema(texto, errores, *, etiqueta, spec, tipo):
    """Numero (`tipo` int o float) acotado por el `minimum` y el `maximum` de un
    JSON Schema; cualquiera de los dos puede faltar. `texto` ya viene sin
    espacios y no vacio."""
    valor = _a_numero(texto, errores, etiqueta, tipo)
    if valor is None:
        return None
    minimo, maximo = spec.get("minimum"), spec.get("maximum")
    if minimo is not None and valor < minimo:
        errores.append(f"{etiqueta} no puede ser menor que {minimo}.")
        return None
    if maximo is not None and valor > maximo:
        errores.append(f"{etiqueta} no puede ser mayor que {maximo}.")
        return None
    return valor
