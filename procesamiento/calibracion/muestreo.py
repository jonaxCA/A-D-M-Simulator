import numpy as np


def hipercubo_latino(n, rangos, semilla):
    # Un punto por estrato en cada dimensión (McKay, Beckman y Conover 1979).
    rng = np.random.default_rng(semilla)
    puntos = {}
    for nombre, (minimo, maximo) in rangos.items():
        u = (rng.permutation(n) + rng.random(n)) / n
        puntos[nombre] = minimo + u * (maximo - minimo)
    return puntos
