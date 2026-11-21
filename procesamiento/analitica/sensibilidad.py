from statistics import mean

from procesamiento.categoria import categoria
from procesamiento.motor import EscenarioInvalido, simular
from procesamiento.trazabilidad import desempaca, es_numero

from .pareto import METRICAS_IMPACTO

PARAMETROS = ("r0", "incubacion_dias", "infeccioso_dias", "dias_hospitalizacion")
SEMILLAS = (1, 2, 3, 4, 5)
MAXIMO_VALORES = 9
FUENTE = "barrido de sensibilidad (D46)"
METODO = ("Un factor a la vez: se cambia un parametro de la enfermedad, los demas quedan como "
          "en el escenario, y se corre el motor de referencia con las mismas semillas por valor. "
          "Los valores probados son supuestos del analisis, no datos.")


class SensibilidadInvalida(ValueError):
    def __init__(self, errores):
        self.errores = errores
        super().__init__("; ".join(errores))


def valor_base(escenario, parametro):
    return desempaca(escenario["enfermedad"][parametro])[0]


def valores_por_porcentaje(escenario, parametro, porcentajes):
    base = valor_base(escenario, parametro)
    return [round(base * (1 + p / 100), 6) for p in porcentajes]


def _promedios(escenario, parametro, valor, metrica, semillas):
    esc = {**escenario, "enfermedad": {**escenario["enfermedad"],
                                       parametro: {"valor": valor, "fuente": FUENTE, "supuesto": True}}}
    corridas = [simular(esc, s) for s in semillas]
    return [c["resumen"][metrica] for c in corridas], corridas[0]


def sensibilidad(escenario, parametro, valores, metrica="fallecimientos", semillas=SEMILLAS):
    errores = []
    if parametro not in PARAMETROS:
        errores.append("Parametro '%s' no valido; usa uno de: %s." % (parametro, ", ".join(PARAMETROS)))
    if metrica not in METRICAS_IMPACTO:
        errores.append("Metrica '%s' no valida; usa una de: %s." % (metrica, ", ".join(METRICAS_IMPACTO)))
    if not isinstance(valores, (list, tuple)) or not valores or len(valores) > MAXIMO_VALORES:
        errores.append("Indica de 1 a %d valores." % MAXIMO_VALORES)
    elif not all(es_numero(v) and v > 0 for v in valores):
        errores.append("Los valores deben ser numeros mayores que 0.")
    if errores:
        raise SensibilidadInvalida(errores)

    base = valor_base(escenario, parametro)
    if not es_numero(base):
        raise SensibilidadInvalida(["El escenario no trae un valor numerico de '%s'." % parametro])
    try:
        filas = []
        for v in sorted({base, *valores}):
            muestras, corrida = _promedios(escenario, parametro, v, metrica, semillas)
            filas.append({"valor": v, "es_base": v == base, "media": round(mean(muestras), 2),
                          "minimo": min(muestras), "maximo": max(muestras), "_c": corrida})
    except EscenarioInvalido as ex:
        raise SensibilidadInvalida(ex.errores)

    ref = next(f for f in filas if f["es_base"])
    for f in filas:
        f["cambio_parametro_pct"] = round((f["valor"] / base - 1) * 100, 2)
        f["diferencia_vs_base"] = round(f["media"] - ref["media"], 2)
        f["cambio_metrica_pct"] = (round((f["media"] / ref["media"] - 1) * 100, 2)
                                   if ref["media"] else None)
    version = ref["_c"]["engine_version"]
    clase = categoria(version, ref["_c"]["trazabilidad_parametros"])
    for f in filas:
        del f["_c"]
    return {"parametro": parametro, "metrica": metrica, "valor_base": base,
            "semillas": list(semillas), "engine_version": version, "metodo": METODO,
            "categoria": clase["categoria"], "modelo_verificado": clase["modelo_verificado"],
            "motivo": clase["motivo"], "texto_categoria": clase["texto"], "filas": filas}
