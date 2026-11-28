import math

import numpy as np


def ventanas(semanas):
    """(n de calibración, n de validación): las primeras ⅔ calibran y el resto valida (D50)."""
    calibra = min(semanas - 1, max(1, round(2 * semanas / 3)))
    return calibra, semanas - calibra


def perdida(observado, simulado):
    """Σ (log(1 + o) − log(1 + s))² (D50)."""
    return float(np.sum((np.log1p(observado) - np.log1p(simulado)) ** 2))


def metricas(observado, mediana, p5, p95):
    observado = np.asarray(observado, dtype=float)
    error = observado - np.asarray(mediana, dtype=float)
    dispersion = float(np.sum((observado - observado.mean()) ** 2))
    dentro = (np.asarray(p5) <= observado) & (observado <= np.asarray(p95))
    return {
        "semanas": int(observado.size),
        "rmse": math.sqrt(float(np.mean(error ** 2))),
        "r2": 1 - float(np.sum(error ** 2)) / dispersion if dispersion else None,
        "cobertura": float(np.mean(dentro)),
    }
