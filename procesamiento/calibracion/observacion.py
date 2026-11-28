import numpy as np

# Mediana del periodo de incubación de Lauer et al. 2020 (migración 017): un contagio del día d
# empieza síntomas el día d + 5, y la serie observada va por inicio de síntomas (D50).
DESFASE_DIAS = 5


def casos_semanales(serie, infectados_iniciales, rho, semanas, desfase=DESFASE_DIAS):
    # nuevos_casos son contagios S → E. Los infectados iniciales ya son infecciosos el día 0:
    # se cuentan como inicio de síntomas ese día, la primera semana de la ventana.
    contagios = np.array([fila["nuevos_casos"] for fila in serie], dtype=float)
    inicio = np.zeros(7 * semanas)
    n = min(contagios.size, inicio.size - desfase)
    inicio[desfase:desfase + n] = contagios[:n]
    inicio[0] += infectados_iniciales
    return rho * inicio.reshape(semanas, 7).sum(axis=1)
