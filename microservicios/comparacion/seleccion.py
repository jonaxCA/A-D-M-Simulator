from epidemia_comun.errores import ErrorAPI
from epidemia_comun.validaciones import entero_positivo


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
