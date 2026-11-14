"""La población de agentes y sus grupos de contacto, para abm-ref.

Cada persona simulada es un agente con su grupo de edad. Al inicio de la corrida, y siempre
con el mismo generador de la semilla, se arman tres capas agrupadas:

- hogar: toda la población, en hogares al azar;
- escuela: los grupos de edad escolar, en salones;
- trabajo: los grupos de edad laboral, en centros de trabajo.

La cuarta capa, comunidad, no se agrupa: es la mezcla de toda la población, como en seir-ref.

Los tamaños de hogar, salón y centro de trabajo son supuestos del motor, no datos del censo,
y la salida los reporta como tales en la trazabilidad (regla 8).
"""
import math

import numpy as np

FUENTE_SUPUESTO = "Supuesto del motor abm-ref, no calibrado"

# Tamaño medio de cada grupo de contacto. El tamaño de cada uno es 1 + Poisson(medio - 1).
TAMANO_MEDIO = {
    "hogar": 3.5,
    "escuela": 25.0,
    "trabajo": 15.0,
}

# Va a la escuela el grupo de edad que empieza antes de esta edad, y trabaja el que empieza
# desde ella y antes de EDAD_RETIRO.
EDAD_FIN_ESCUELA = 18
EDAD_RETIRO = 60

# Sin grupos de edad no se sabe quién estudia o trabaja. Se toma la proporción de 0 a 19 años
# (escuela) y de 20 a 59 (trabajo) de Nuevo León en el Censo 2020 de INEGI
# (datos/censo/nl_estructura_edad_2020.tsv), con la misma regla de arriba.
_CENSO_NL_2020 = {"0-19": 1_853_344, "20-39": 1_867_264, "40-59": 1_391_652,
                  "60-79": 564_795, "80+": 89_255}
_TOTAL_NL_2020 = sum(_CENSO_NL_2020.values())
FRACCION_SIN_EDAD = {
    "escuela": _CENSO_NL_2020["0-19"] / _TOTAL_NL_2020,
    "trabajo": (_CENSO_NL_2020["20-39"] + _CENSO_NL_2020["40-59"]) / _TOTAL_NL_2020,
}

CAPAS_AGRUPADAS = ("hogar", "escuela", "trabajo")


def agrupa(indices, tamano_medio, rng):
    """Reparte `indices` (ya en orden aleatorio) en grupos consecutivos de tamaño
    1 + Poisson(tamano_medio - 1). Regresa el número de grupo de cada índice y cuántos hay."""
    n = len(indices)
    if n == 0:
        return np.zeros(0, dtype=np.int32), 0
    tamanos = 1 + rng.poisson(tamano_medio - 1, size=math.ceil(n / tamano_medio * 1.2) + 10)
    limites = np.cumsum(tamanos)
    while limites[-1] < n:
        extra = 1 + rng.poisson(tamano_medio - 1, size=len(tamanos))
        tamanos = np.concatenate([tamanos, extra])
        limites = np.cumsum(tamanos)
    numero = np.searchsorted(limites, np.arange(n), side="right").astype(np.int32)
    return numero, int(numero[-1]) + 1


def arma_capas(grupo, edad_minima_grupo, rng):
    """Los grupos de contacto de cada agente.

    `grupo` trae el grupo de edad de cada agente y `edad_minima_grupo`, el inicio de cada grupo
    (None si la población no viene por edad). Regresa:

    - capas: {capa: (numero, cuantos)}, con `numero` del tamaño de la población y -1 en quien
      no pertenece a esa capa;
    - trazabilidad: los supuestos usados, con el formato de la salida del motor;
    - avisos: lo que la corrida hace distinto de lo que podría esperarse.
    """
    n = len(grupo)
    avisos = []
    if all(e is None for e in edad_minima_grupo):
        sorteo = rng.random(n)
        miembros = {
            "hogar": np.ones(n, dtype=bool),
            "escuela": sorteo < FRACCION_SIN_EDAD["escuela"],
            "trabajo": (sorteo >= FRACCION_SIN_EDAD["escuela"])
            & (sorteo < FRACCION_SIN_EDAD["escuela"] + FRACCION_SIN_EDAD["trabajo"]),
        }
        avisos.append("La población no viene por grupo de edad: quién va a la escuela y quién "
                      "trabaja se sortea con las proporciones de Nuevo León en el Censo 2020.")
    else:
        inicio = np.array([e if e is not None else 0 for e in edad_minima_grupo])
        escolar = inicio < EDAD_FIN_ESCUELA
        laboral = (inicio >= EDAD_FIN_ESCUELA) & (inicio < EDAD_RETIRO)
        miembros = {
            "hogar": np.ones(n, dtype=bool),
            "escuela": escolar[grupo],
            "trabajo": laboral[grupo],
        }

    capas = {}
    for capa in CAPAS_AGRUPADAS:
        numero = np.full(n, -1, dtype=np.int32)
        quienes = np.flatnonzero(miembros[capa])
        orden = rng.permutation(quienes)
        numero[orden], cuantos = agrupa(orden, TAMANO_MEDIO[capa], rng)
        capas[capa] = (numero, cuantos)

    trazabilidad = [
        {"parametro": "tamano_medio_%s" % capa, "valor": TAMANO_MEDIO[capa],
         "fuente": FUENTE_SUPUESTO, "estado": "supuesto"}
        for capa in CAPAS_AGRUPADAS
    ]
    if all(e is None for e in edad_minima_grupo):
        trazabilidad.append({
            "parametro": "fraccion_escuela_trabajo",
            "valor": {k: round(v, 4) for k, v in FRACCION_SIN_EDAD.items()},
            "fuente": "Censo 2020 de INEGI, Nuevo León (0-19 y 20-59 años); el reparto en "
                      "escuela y trabajo es supuesto",
            "estado": "supuesto",
        })
    return capas, trazabilidad, avisos
