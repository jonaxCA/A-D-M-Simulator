"""Las mediciones de la ficha del simulador (docs/arquitectura/ficha_simulador.md).

Desde la raíz del repositorio:

    python -m procesamiento.mediciones tiempos          # tiempo y memoria de cada motor por agentes
    python -m procesamiento.mediciones validacion       # abm-ref contra seir-ref
    python -m procesamiento.mediciones esperados        # seir-ref contra soluciones conocidas
    python -m procesamiento.mediciones sensibilidad     # un parámetro a la vez, ±20 %
    python -m procesamiento.mediciones reproducibilidad # misma semilla y versión, misma salida

Imprimen tablas en Markdown, listas para pegar en la ficha. Usan el escenario del contrato de los
motores (procesamiento/contrato.py) llevado a 180 días y al número de agentes de cada renglón.
Los tiempos dependen de la máquina: la ficha anota en cuál se midieron.

abm-gpu entra solo donde corre (pyflamegpu y una GPU de NVIDIA; ver procesamiento/abm_gpu/
README.md). Su primera corrida de cada tamaño compila las funciones de agente; la mediana de
tres la deja fuera. Su memoria pico es la de Python, no la de la GPU.
"""
import argparse
import copy
import hashlib
import json
import math
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


def r0_efectivo(r0, infeccioso_dias):
    """El R0 que corre seir-ref. En pasos de un día, quien entra a I se queda en promedio
    1 / (1 − e^(−1/D)) días, no D: con β = R0 / D, cada caso contagia β · 1/p_sale_I."""
    return r0 / infeccioso_dias / -math.expm1(-1.0 / infeccioso_dias)


def tamano_final(r0):
    """La z de z = 1 − e^(−R0·z) (Kermack y McKendrick): la fracción de la población que se
    contagia en un brote con mezcla homogénea, sin intervenciones. 0 si R0 ≤ 1."""
    if r0 <= 1:
        return 0.0
    bajo, alto = 1e-9, 1.0
    for _ in range(200):
        z = (bajo + alto) / 2
        if z - 1 + math.exp(-r0 * z) < 0:
            bajo = z
        else:
            alto = z
    return (bajo + alto) / 2


def _media(simular, esc, campo, semillas=SEMILLAS):
    return statistics.mean(simular(copy.deepcopy(esc), s)["resumen"][campo] for s in semillas)


def _escala_tasa(esc, nombre, factor):
    valor = esc["enfermedad"][nombre]["valor"]
    esc["enfermedad"][nombre]["valor"] = ({g: v * factor for g, v in valor.items()}
                                          if isinstance(valor, dict) else valor * factor)


def esperados(agentes):
    """seir-ref contra lo que debe dar: el tamaño final de un SEIR, la letalidad y la tasa de
    hospitalización acumuladas que recibe, y los casos límite."""
    seir = motores.IMPLEMENTADOS["seir-ref"].simular
    print("**Tamaño final.** Tasa de ataque media de %d semillas, %s agentes, 365 días, sin "
          "intervenciones, contra z = 1 − e^(−R0·z) con el R0 nominal y con el efectivo.\n"
          % (len(SEMILLAS), f"{agentes:,}"))
    print("| R0 nominal | R0 efectivo | z con R0 nominal | z con R0 efectivo | seir-ref | Diferencia con el efectivo |")
    print("|---|---|---|---|---|---|")
    for r0 in (0.8,) + R0S:
        esc = escenario(agentes, dias=365, r0=r0, intervenciones=False)
        efectivo = r0_efectivo(r0, esc["enfermedad"]["infeccioso_dias"]["valor"])
        medido = _media(seir, esc, "tasa_ataque")
        print("| %.1f | %.3f | %.3f | %.3f | %.3f | %+.3f |" % (
            r0, efectivo, tamano_final(r0), tamano_final(efectivo), medido,
            medido - tamano_final(efectivo)), flush=True)

    print("\n**Letalidad y hospitalización acumuladas.** Con R0 2.5 y 365 días casi todos los "
          "contagiados terminan su curso: fallecimientos / Σ casos·IFR y hospitalizaciones / "
          "Σ casos·IHR deben ser cercanos a 1.\n")
    esc = escenario(agentes, dias=365, r0=2.5, intervenciones=False)
    ifr, ihr = (esc["enfermedad"][n]["valor"] for n in ("letalidad", "tasa_hospitalizacion"))
    print("| Semilla | Fallecimientos | Esperados | Razón | Hospitalizaciones | Esperadas | Razón |")
    print("|---|---|---|---|---|---|---|")
    for s in SEMILLAS:
        r = seir(copy.deepcopy(esc), s)["resumen"]
        casos = {g["grupo"]: g["casos"] for g in r["desglose_por_grupo"]}
        muertes = sum(casos[g] * ifr[g] for g in casos)
        hosp = sum(casos[g] * ihr[g] for g in casos)
        print("| %d | %d | %.1f | %.3f | %d | %.1f | %.3f |" % (
            s, r["fallecimientos"], muertes, r["fallecimientos"] / muertes,
            r["hospitalizaciones"], hosp, r["hospitalizaciones"] / hosp), flush=True)

    print("\n**Casos límite.**\n")
    print("| Caso | Esperado | seir-ref (5 semillas) |")
    print("|---|---|---|")
    sin_muertes = escenario(agentes, dias=365, r0=2.5, intervenciones=False)
    _escala_tasa(sin_muertes, "letalidad", 0)
    sin_hosp = copy.deepcopy(sin_muertes)
    _escala_tasa(sin_hosp, "tasa_hospitalizacion", 0)
    sub = escenario(agentes, dias=365, r0=0.8, intervenciones=False)
    # Bajo el umbral, cada caso inicial deja en promedio 1 / (1 − R0) casos en total (proceso de
    # ramificación), con el R0 efectivo.
    ramificacion = sub["infectados_iniciales"] / agentes / (
        1 - r0_efectivo(0.8, sub["enfermedad"]["infeccioso_dias"]["valor"]))
    casos = [
        ("Letalidad 0", "0 fallecimientos", "%d" % max(
            seir(copy.deepcopy(sin_muertes), s)["resumen"]["fallecimientos"] for s in SEMILLAS)),
        ("Letalidad y hospitalización 0", "0 hospitalizaciones", "%d" % max(
            seir(copy.deepcopy(sin_hosp), s)["resumen"]["hospitalizaciones"] for s in SEMILLAS)),
        ("R0 0.8 (subumbral)", "Sin brote: tasa de ataque I0/N / (1 − R0 efectivo) = %.4f"
         % ramificacion, "%.4f" % _media(seir, sub, "tasa_ataque")),
    ]
    for caso in casos:
        print("| %s | %s | %s |" % caso, flush=True)


PARAMETROS = ("r0", "incubacion_dias", "infeccioso_dias", "tasa_hospitalizacion", "letalidad")
METRICAS = ("tasa_ataque", "pico_casos_activos", "dia_pico", "hospitalizaciones",
            "fallecimientos")


def sensibilidad(agentes, factores=(0.8, 1.2)):
    """Un parámetro a la vez, multiplicado por cada factor; la media de las semillas de cada
    métrica, relativa al caso base."""
    seir = motores.IMPLEMENTADOS["seir-ref"].simular
    base = escenario(agentes, dias=365, intervenciones=False)
    referencia = {m: _media(seir, base, m) for m in METRICAS}
    print("Media de %d semillas, %s agentes, 365 días, sin intervenciones. Cada celda es la "
          "métrica con el parámetro cambiado dividida entre la del caso base.\n"
          % (len(SEMILLAS), f"{agentes:,}"))
    print("| Parámetro | Factor | " + " | ".join(METRICAS) + " |")
    print("|---|---|" + "---|" * len(METRICAS))
    print("| (base) | 1.0 | " + " | ".join("%.4g" % referencia[m] for m in METRICAS) + " |")
    filas = {}
    for nombre in PARAMETROS:
        for factor in factores:
            esc = copy.deepcopy(base)
            _escala_tasa(esc, nombre, factor)
            fila = {m: _media(seir, esc, m) / referencia[m] for m in METRICAS}
            filas[(nombre, factor)] = fila
            print("| %s | %.1f | " % (nombre, factor)
                  + " | ".join("%.3f" % fila[m] for m in METRICAS) + " |", flush=True)
    return referencia, filas


def _huella_salida(salida):
    return hashlib.sha256(json.dumps(salida, sort_keys=True).encode("utf-8")).hexdigest()


def reproducibilidad():
    """Cada motor que corre aquí, con el escenario del contrato: dos corridas con la misma
    semilla dan la misma salida bit a bit, y otra semilla da otra."""
    print("| Motor | engine_version | Semilla | Huella de la salida, 1.ª corrida | 2.ª corrida | Iguales | Otra semilla da otra salida |")
    print("|---|---|---|---|---|---|---|")
    for nombre, motor in motores.IMPLEMENTADOS.items():
        if not motor.disponible()[0]:
            print("| `%s` | — | — | no corre en esta máquina | | | |" % nombre)
            continue
        semilla = contrato.SEMILLA_EJEMPLO
        una = motor.simular(copy.deepcopy(contrato.ESCENARIO_EJEMPLO), semilla)
        otra = motor.simular(copy.deepcopy(contrato.ESCENARIO_EJEMPLO), semilla)
        distinta = motor.simular(copy.deepcopy(contrato.ESCENARIO_EJEMPLO), semilla + 1)
        h1, h2 = _huella_salida(una), _huella_salida(otra)
        print("| `%s` | %s | %d | `%s…` | `%s…` | %s | %s |" % (
            nombre, una["engine_version"], semilla, h1[:16], h2[:16], "sí" if h1 == h2 else "NO",
            "sí" if _huella_salida(distinta) != h1 else "NO"), flush=True)


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
    for nombre in ("esperados", "sensibilidad"):
        sub.add_parser(nombre).add_argument("--agentes", type=int, default=1_000_000)
    sub.add_parser("reproducibilidad")
    args = ap.parse_args(argv)
    print("<!-- %s -->" % maquina())
    if args.medicion == "tiempos":
        tiempos(args.agentes, args.repeticiones)
    elif args.medicion == "esperados":
        esperados(args.agentes)
    elif args.medicion == "sensibilidad":
        sensibilidad(args.agentes)
    elif args.medicion == "reproducibilidad":
        reproducibilidad()
    else:
        print("<!-- Tasa de ataque media de %d semillas, %s agentes, %d días, sin intervenciones -->"
              % (len(SEMILLAS), f"{args.agentes:,}", DIAS))
        validacion(args.agentes)


if __name__ == "__main__":
    sys.exit(main())
