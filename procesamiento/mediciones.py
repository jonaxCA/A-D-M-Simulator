"""Las mediciones de la ficha del simulador (docs/arquitectura/ficha_simulador.md).

Desde la raíz del repositorio:

    python -m procesamiento.mediciones tiempos      # tiempo y memoria de cada motor por agentes
    python -m procesamiento.mediciones validacion   # abm-ref contra seir-ref

Imprimen tablas en Markdown, listas para pegar en la ficha. Usan el escenario del contrato de los
motores (procesamiento/contrato.py) llevado a 180 días y al número de agentes de cada renglón.
Los tiempos dependen de la máquina: la ficha anota en cuál se midieron.

abm-gpu entra solo donde corre (pyflamegpu y una GPU de NVIDIA; ver procesamiento/abm_gpu/
README.md). Su primera corrida de cada tamaño compila las funciones de agente; la mediana de
tres la deja fuera. Su memoria pico es la de Python, no la de la GPU.
"""
import argparse
import copy
import platform
import statistics
import sys
import time
import tracemalloc

import numpy as np

from procesamiento import contrato, motores
from procesamiento.abm import poblacion

DIAS = 180
AGENTES = (10_000, 100_000, 500_000, 1_000_000, 2_000_000)
R0S = (1.3, 1.6, 2.5)
SEMILLAS = range(1, 6)


def escenario(agentes, dias=DIAS, r0=None, intervenciones=True):
    """El escenario del contrato con `agentes` personas, repartidas como en el ejemplo."""
    esc = copy.deepcopy(contrato.ESCENARIO_EJEMPLO)
    base = sum(esc["poblacion"].values())
    factor = agentes / base
    grupos = list(esc["poblacion"])
    esc["poblacion"] = {g: round(n * factor) for g, n in esc["poblacion"].items()}
    # El redondeo no debe cambiar el total.
    esc["poblacion"][grupos[0]] += agentes - sum(esc["poblacion"].values())
    esc["infectados_iniciales"] = max(1, round(contrato.ESCENARIO_EJEMPLO["infectados_iniciales"] * factor))
    esc["dias"] = dias
    if r0 is not None:
        esc["enfermedad"]["r0"]["valor"] = r0
    if intervenciones:
        for iv in esc["intervenciones"]:
            if iv["tipo"] == "VACUNACION":
                iv["params"]["dosis_diarias"] = max(1, round(iv["params"]["dosis_diarias"] * factor))
    else:
        esc["intervenciones"] = []
    return esc


def mide(simular, esc, repeticiones):
    """(mediana de segundos, memoria pico en MB de una corrida aparte)."""
    tiempos = []
    for semilla in range(repeticiones):
        inicio = time.perf_counter()
        simular(copy.deepcopy(esc), semilla)
        tiempos.append(time.perf_counter() - inicio)
    tracemalloc.start()
    simular(copy.deepcopy(esc), 0)
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return statistics.median(tiempos), pico / 2 ** 20


def tiempos(agentes, repeticiones):
    print("| Motor | Agentes | Días | Segundos (mediana de %d) | Memoria pico (MB) |" % repeticiones)
    print("|---|---|---|---|---|")
    for nombre, motor in motores.IMPLEMENTADOS.items():
        if not motor.disponible()[0]:
            continue
        for n in agentes:
            segundos, memoria = mide(motor.simular, escenario(n), repeticiones)
            print("| `%s` | %s | %d | %.2f | %.0f |" % (nombre, f"{n:,}", DIAS, segundos, memoria),
                  flush=True)


def _ataque(simular, esc):
    return statistics.mean(simular(copy.deepcopy(esc), s)["resumen"]["tasa_ataque"]
                           for s in SEMILLAS)


def validacion(agentes):
    """abm-ref con un solo grupo por capa debe dar la tasa de ataque de seir-ref: la fórmula
    del ABM no cambia nada más que la agrupación. Con hogares, salones y trabajos, baja."""
    seir = motores.IMPLEMENTADOS["seir-ref"].simular
    abms = [m for m in (motores.IMPLEMENTADOS["abm-ref"], motores.IMPLEMENTADOS["abm-gpu"])
            if m.disponible()[0]]
    columnas = ["seir-ref"]
    for m in abms:
        columnas += ["%s con un solo grupo por capa" % m.nombre,
                     "%s con hogares, salones y trabajos" % m.nombre]
    print("| R0 | " + " | ".join(columnas) + " |")
    print("|---" * (len(columnas) + 1) + "|")
    for r0 in R0S:
        esc = escenario(agentes, r0=r0, intervenciones=False)
        fila = [_ataque(seir, esc)]
        for m in abms:
            original = dict(poblacion.TAMANO_MEDIO)
            poblacion.TAMANO_MEDIO.update({capa: 10 ** 9 for capa in original})
            try:
                fila.append(_ataque(m.simular, esc))
            finally:
                poblacion.TAMANO_MEDIO.update(original)
            fila.append(_ataque(m.simular, esc))
        print("| %.1f | " % r0 + " | ".join("%.3f" % x for x in fila) + " |", flush=True)


def maquina():
    return "Python %s, NumPy %s, %s" % (platform.python_version(), np.__version__,
                                         platform.platform(terse=True))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="medicion", required=True)
    t = sub.add_parser("tiempos")
    t.add_argument("--agentes", type=int, nargs="+", default=list(AGENTES))
    t.add_argument("--repeticiones", type=int, default=3)
    v = sub.add_parser("validacion")
    v.add_argument("--agentes", type=int, default=100_000)
    args = ap.parse_args(argv)
    print("<!-- %s -->" % maquina())
    if args.medicion == "tiempos":
        tiempos(args.agentes, args.repeticiones)
    else:
        print("<!-- Tasa de ataque media de %d semillas, %s agentes, %d días, sin intervenciones -->"
              % (len(SEMILLAS), f"{args.agentes:,}", DIAS))
        validacion(args.agentes)


if __name__ == "__main__":
    sys.exit(main())
