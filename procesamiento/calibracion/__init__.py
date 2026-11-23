# Calibración de seir-ref contra una serie semanal observada: ABC por rechazo (D50). No toca la
# base ni Flask (regla 2).
#
# `observado` es [{"inicio": "2020-03-01", "valor": 7}, ...], una semana por punto. `base` trae
# `enfermedad` (los parámetros del catálogo, con su trazabilidad), `poblacion` (por grupo de edad)
# y, si hay gente sin edad, `poblacion_edad_desconocida` y `politica_edad_desconocida`.
import copy

import numpy as np

from procesamiento.contrato import huella
from procesamiento.motor import CAPAS_CONTACTO_SUPUESTO, ENGINE_VERSION, simular

from .ajuste import metricas, perdida, ventanas
from .escenario import escenario_de_muestra, infectados_iniciales, jornada
from .muestreo import hipercubo_latino
from .observacion import DESFASE_DIAS, casos_semanales

METODO = "abc-rechazo"
VERSION_METODO = "calibracion-0.1"
MOTOR = "seir-ref"
PARAMETROS = ("r0", "rho", "phi")
# Rangos del análisis, todos supuesto (regla 8). El de r0 contiene el IC 2.39-3.44 de Billah et al.
# 2020 (017) con holgura; el de ρ casi todo el intervalo, porque no hay fuente local del subregistro.
RANGOS = {"r0": (1.0, 5.0), "rho": (0.01, 1.0), "phi": (0.0, 1.0)}
CONFIGURACION = {"muestras": 5000, "semillas": 3, "cuantil": 0.01, "semilla_muestreo": 1}
TOPES = {"muestras": (100, 10000), "semillas": (1, 5), "cuantil": (0.001, 0.2)}
SEMILLAS_EVALUACION = tuple(range(1, 6))
SEMANAS_MINIMAS = 6
REVISA_CADA = 200


class CalibracionCancelada(Exception):
    pass


def revisa_configuracion(config):
    errores = []
    for clave, (minimo, maximo) in TOPES.items():
        valor = config.get(clave)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not minimo <= valor <= maximo:
            errores.append("%s debe estar entre %s y %s." % (clave, minimo, maximo))
    for clave in ("muestras", "semillas"):
        if not isinstance(config.get(clave), int):
            errores.append("%s debe ser un entero." % clave)
    semilla = config.get("semilla_muestreo")
    if isinstance(semilla, bool) or not isinstance(semilla, int) or semilla < 0:
        errores.append("semilla_muestreo debe ser un entero >= 0.")
    if not errores and round(config["cuantil"] * config["muestras"]) < 10:
        errores.append("cuantil × muestras debe dejar al menos 10 aceptadas.")
    return errores


def revisa_parametros(theta):
    return ["%s debe estar entre %s y %s." % (p, *RANGOS[p]) for p in PARAMETROS
            if not isinstance(theta.get(p), (int, float)) or not RANGOS[p][0] <= theta[p] <= RANGOS[p][1]]


def _preparar(observado):
    if len(observado) < SEMANAS_MINIMAS:
        raise ValueError("La serie necesita al menos %d semanas." % SEMANAS_MINIMAS)
    fechas = [str(p["inicio"]) for p in observado]
    valores = np.array([p["valor"] for p in observado], dtype=float)
    dias = 7 * len(valores)
    return fechas, valores, dias, jornada(fechas[0], dias)


def _simula(base, intervenciones, dias, c0, theta, semilla):
    escenario = escenario_de_muestra(base, intervenciones, dias, c0, **theta)
    serie = simular(escenario, semilla)["serie"]
    return casos_semanales(serie, escenario["infectados_iniciales"], theta["rho"], dias // 7)


def _ajuste(fechas, valores, trayectorias, calibra):
    p5, p50, p95 = np.percentile(trayectorias, (5, 50, 95), axis=0)
    semanas = [{"inicio": f, "observado": int(v), "mediana": float(m), "p5": float(a),
                "p95": float(b), "ventana": "calibracion" if i < calibra else "validacion"}
               for i, (f, v, m, a, b) in enumerate(zip(fechas, valores, p50, p5, p95))]
    tramos = {"calibracion": slice(0, calibra), "validacion": slice(calibra, None)}
    return semanas, {nombre: metricas(valores[t], p50[t], p5[t], p95[t]) for nombre, t in tramos.items()}


def _ventanas(fechas, calibra):
    return {"calibracion": {"desde": fechas[0], "hasta": fechas[calibra - 1], "semanas": calibra},
            "validacion": {"desde": fechas[calibra], "hasta": fechas[-1],
                           "semanas": len(fechas) - calibra}}


def _valor(parametro):
    return parametro["valor"] if isinstance(parametro, dict) and "valor" in parametro else parametro


def huella_configuracion(base, r0, iniciales):
    # Lo que la calibración dejó fijo o estimó (D50): enfermedad, capas, población e iniciales.
    enfermedad = {k: _valor(v) for k, v in base["enfermedad"].items()}
    enfermedad["r0"] = r0
    return huella({"enfermedad": enfermedad, "capas_contacto": CAPAS_CONTACTO_SUPUESTO,
                   "poblacion": base["poblacion"],
                   "poblacion_edad_desconocida": base.get("poblacion_edad_desconocida", 0),
                   "politica_edad_desconocida": base.get("politica_edad_desconocida"),
                   "infectados_iniciales": iniciales})


def calibrar(observado, base, configuracion=None, avance=None, cancelada=None):
    config = {**CONFIGURACION, **(configuracion or {})}
    errores = revisa_configuracion(config)
    if errores:
        raise ValueError(" ".join(errores))
    fechas, valores, dias, intervenciones = _preparar(observado)
    calibra, _ = ventanas(len(valores))
    c0 = float(valores[0])
    n, semillas = config["muestras"], list(range(1, config["semillas"] + 1))
    muestras = hipercubo_latino(n, RANGOS, config["semilla_muestreo"])

    trayectorias = np.empty((n, len(semillas), len(valores)))
    distancias = np.empty(n)
    total, hechas = n * len(semillas), 0
    for i in range(n):
        theta = {p: float(muestras[p][i]) for p in PARAMETROS}
        for j, semilla in enumerate(semillas):
            trayectorias[i, j] = _simula(base, intervenciones, dias, c0, theta, semilla)
            hechas += 1
            if hechas % REVISA_CADA == 0:
                if cancelada and cancelada():
                    raise CalibracionCancelada()
                if avance:
                    avance(100 * hechas // total)
        distancias[i] = np.mean([perdida(valores[:calibra], t[:calibra]) for t in trayectorias[i]])

    aceptadas = np.argsort(distancias, kind="stable")[:round(config["cuantil"] * n)]
    parametros = []
    for p in PARAMETROS:
        p5, p50, p95 = np.percentile(muestras[p][aceptadas], (5, 50, 95))
        parametros.append({"nombre": p, "mediana": float(p50), "p5": float(p5), "p95": float(p95),
                           "minimo": RANGOS[p][0], "maximo": RANGOS[p][1]})
    medianas = {p["nombre"]: p["mediana"] for p in parametros}
    semanas, ajuste = _ajuste(fechas, valores,
                              trayectorias[aceptadas].reshape(-1, len(valores)), calibra)
    return {
        "metodo": METODO,
        "version_metodo": VERSION_METODO,
        "motor": MOTOR,
        "engine_version": ENGINE_VERSION,
        "configuracion": {
            "muestras": n, "semillas": semillas, "cuantil": config["cuantil"],
            "semilla_muestreo": config["semilla_muestreo"],
            "rangos": {p: {"min": RANGOS[p][0], "max": RANGOS[p][1]} for p in PARAMETROS},
            "desfase_dias": DESFASE_DIAS, "c0": c0, "dias": dias,
            "ventanas": _ventanas(fechas, calibra),
            "intervenciones": copy.deepcopy(intervenciones),
        },
        "parametros": parametros,
        "perdida": {"minima": float(distancias[aceptadas[0]]),
                    "umbral": float(distancias[aceptadas[-1]]),
                    "aceptadas": int(aceptadas.size), "corridas": total},
        "aceptadas": [{**{p: float(muestras[p][i]) for p in PARAMETROS},
                       "distancia": float(distancias[i])} for i in aceptadas],
        "semanas": semanas,
        "metricas": ajuste,
        "huella_configuracion": huella_configuracion(
            base, medianas["r0"], infectados_iniciales(c0, medianas["rho"])),
    }


def evaluar(observado, base, theta, semillas=SEMILLAS_EVALUACION):
    errores = revisa_parametros(theta)
    if errores:
        raise ValueError(" ".join(errores))
    fechas, valores, dias, intervenciones = _preparar(observado)
    calibra, _ = ventanas(len(valores))
    trayectorias = np.array([_simula(base, intervenciones, dias, float(valores[0]), theta, s)
                             for s in semillas])
    semanas, ajuste = _ajuste(fechas, valores, trayectorias, calibra)
    return {
        "motor": MOTOR, "engine_version": ENGINE_VERSION,
        "parametros": {p: float(theta[p]) for p in PARAMETROS},
        "semillas": list(semillas),
        "perdida": float(np.mean([perdida(valores[:calibra], t[:calibra]) for t in trayectorias])),
        "ventanas": _ventanas(fechas, calibra),
        "semanas": semanas,
        "metricas": ajuste,
    }


def configuracion_calibrada(resultado):
    # La entrada de una versión con las medianas: el escritorio la crea, y pasa por revisión (D4, D5).
    medianas = {p["nombre"]: p for p in resultado["parametros"]}
    config = resultado["configuracion"]
    phi = medianas["phi"]["mediana"]
    return {
        "horizon_days": config["dias"],
        "initial_infected": infectados_iniciales(config["c0"], medianas["rho"]["mediana"]),
        "interventions": [{
            "code": iv["tipo"], "start_day": iv["dia_inicio"], "end_day": None,
            "coverage": 1.0, "compliance": 1.0,
            "params": {"reduccion": phi if iv["reduccion"] == "phi" else iv["reduccion"]},
            "fuente": iv["fuente"],
        } for iv in config["intervenciones"]],
        "r0": medianas["r0"],
        "rho": medianas["rho"],
        "phi": medianas["phi"],
    }
