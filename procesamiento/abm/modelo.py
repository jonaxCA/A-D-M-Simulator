"""abm-ref: modelo basado en agentes, en Python y en CPU (D22, D23).

Cada persona simulada es un agente con su grupo de edad, su hogar y, según su edad, su salón o
su centro de trabajo (poblacion.py). Un día tiene los mismos pasos que seir-ref, con las mismas
probabilidades diarias:

    S -> E   cada susceptible se contagia con probabilidad 1 - exp(-lambda_j)
    E -> I   con probabilidad 1 - exp(-1 / incubacion_dias)
    I -> sale con probabilidad 1 - exp(-1 / infeccioso_dias), y va a H con
             tasa_hospitalizacion, a D directo con max(0, letalidad - tasa_hospitalizacion)
             o a R
    H -> sale con probabilidad 1 - exp(-1 / dias_hospitalizacion), y muere con
             min(letalidad, tasa_hospitalizacion) / tasa_hospitalizacion
    S -> V   por vacunación, con eficacia parcial

Lo que cambia es la fuerza de infección. En seir-ref es la misma para todos; aquí es de cada
agente j y suma lo que le llega de cada capa de contacto:

    lambda_j = beta * aislamiento(t) * escala_j * sum_capa peso_capa * contactos_capa(t) * x_capa_j
    beta = R0 / infeccioso_dias

con x_capa_j la fracción de infecciosos entre los demás vivos de su hogar, salón o centro de
trabajo, y entre todos los vivos en la comunidad. escala_j reparte el peso de las capas a las
que el agente no pertenece (escuela o trabajo) entre las suyas, para que su contacto total sea
el de seir-ref. Si todos estuvieran en un solo grupo de cada capa, la fórmula sería la de
seir-ref; con grupos chicos, el contagio se queda dentro y se agota antes. Esa diferencia es lo
que el ABM aporta frente al SEIR (D2), y no otra.

El motor no toca la base ni la red, y todo el azar sale de np.random.default_rng(semilla), en
un orden fijo: cambiarlo obliga a subir ENGINE_VERSION.
"""
import math

import numpy as np

from procesamiento.contrato import huella
from procesamiento.motor import ErrorMotor, resolver
from procesamiento.motor.indicadores import resumir

from .poblacion import CAPAS_AGRUPADAS, arma_capas

ENGINE_VERSION = "abm-ref-0.1"

SIMPLIFICACIONES = [
    "Los hogares, salones y centros de trabajo se arman al azar al inicio de la corrida, con "
    "tamaños medios supuestos (no salen del censo) y sin la composición por edad real de un "
    "hogar.",
    "Va a la escuela el grupo de edad que empieza antes de los 18 años y trabaja el que empieza "
    "entre los 18 y los 59. Quien no estudia o no trabaja reparte esos contactos entre sus "
    "otras capas, para que su contacto total sea el de seir-ref.",
    "Dentro de un hogar, salón o centro de trabajo todos se contactan por igual, y la comunidad "
    "es una mezcla homogénea, como en seir-ref.",
    "Duraciones geométricas en pasos de un día, con las mismas medias que seir-ref.",
    "Los hospitalizados no transmiten.",
    "El testeo y aislamiento reduce por igual la transmisión de todos los infecciosos, como en "
    "seir-ref; no se aísla a personas concretas.",
    "La vacuna se aplica sin conocer el estado inmunológico de la persona, y cada persona recibe "
    "a lo más una dosis.",
    "Las intervenciones sobre una capa reducen sus contactos en reducción x cobertura x "
    "cumplimiento, igual para todos sus grupos.",
    "El modelo es de contagio directo persona a persona: dengue, zika y malaria (transmitidas "
    "por vector) se aproximan sin mosquitos, estacionalidad ni dinámica del vector; sus "
    "resultados se leen como orden de magnitud, no como pronóstico.",
]

# Códigos de estado de cada agente.
S, E, I, R, H, D, V = range(7)


def _activa(iv, dia):
    return iv["dia_inicio"] <= dia and (iv["dia_fin"] is None or dia <= iv["dia_fin"])


def _multiplicadores(capas, activas):
    """Cuánto queda de los contactos de cada capa con las intervenciones activas."""
    resultado = {}
    for capa in capas:
        factor = 1.0
        for iv in activas:
            if iv["clase"] == "capa" and iv["capa"] in (capa, "todas"):
                factor *= 1.0 - iv["efecto"]
        resultado[capa] = factor
    return resultado


def _factor_aislamiento(activas):
    factor = 1.0
    for iv in activas:
        if iv["clase"] == "aislamiento":
            factor *= 1.0 - iv["efecto"]
    return factor


def _escala(capas, pesos, n):
    """Por agente: el peso total de las capas entre el de las capas a las que pertenece. Con
    ella, cada agente tiene el mismo contacto total que en seir-ref."""
    total = sum(pesos.values())
    suyo = np.full(n, sum(peso for capa, peso in pesos.items() if capa not in capas))
    for capa, (numero, _) in capas.items():
        suyo += pesos[capa] * (numero >= 0)
    return np.divide(total, suyo, out=np.zeros(n), where=suyo > 0).astype(np.float32)


def _fuerza_de_infeccion(susceptibles, estado, capas, pesos, multiplicadores, beta):
    """lambda de cada susceptible, en el orden de `susceptibles`, sin la escala por agente."""
    infeccioso = estado == I
    vivo = estado != D
    lam = np.zeros(len(susceptibles))
    for capa, peso in pesos.items():
        w = beta * peso * multiplicadores[capa]
        if w == 0:
            continue
        if capa not in capas:
            # Comunidad: la fracción de infecciosos entre todos los vivos.
            lam += w * infeccioso.sum() / max(int(vivo.sum()), 1)
            continue
        numero, cuantos = capas[capa]
        miembro = numero >= 0
        infecciosos = np.bincount(numero[miembro & infeccioso], minlength=cuantos)
        vivos = np.bincount(numero[miembro & vivo], minlength=cuantos)
        suyo = numero[susceptibles]
        dentro = suyo >= 0
        grupo_j = suyo[dentro]
        # El susceptible cuenta entre los vivos de su grupo, pero no entre los infecciosos.
        lam[dentro] += w * infecciosos[grupo_j] / np.maximum(vivos[grupo_j] - 1, 1)
    return lam


def simular(escenario, semilla):
    """Corre el escenario y regresa serie diaria, resumen y trazabilidad, con la forma del
    contrato de los motores (docs/contratos/motor/README.md).

    Levanta EscenarioInvalido si la entrada no es simulable y ErrorMotor si algo falla durante
    la corrida."""
    if isinstance(semilla, bool) or not isinstance(semilla, int) or semilla < 0:
        raise ValueError("La semilla debe ser un entero >= 0.")

    p = resolver(escenario)
    rng = np.random.default_rng(semilla)

    pob = np.array(p["poblacion"], dtype=np.int64)
    N = int(p["N"])
    G = len(pob)
    inicio_grupo = np.concatenate([[0], np.cumsum(pob)])
    grupo = np.repeat(np.arange(G, dtype=np.int16), pob)
    capas, traza_capas, avisos_capas = arma_capas(grupo, p["edad_minima_grupo"], rng)
    capas = {c: capas[c] for c in CAPAS_AGRUPADAS if c in p["capas_contacto"]}
    escala = _escala(capas, p["capas_contacto"], N)

    ihr = np.array(p["tasa_hospitalizacion"], dtype=float)
    ifr = np.array(p["letalidad"], dtype=float)
    beta = p["r0"] / p["infeccioso_dias"]
    p_ei = -math.expm1(-1.0 / p["incubacion_dias"])
    p_sale_i = -math.expm1(-1.0 / p["infeccioso_dias"])
    p_sale_h = -math.expm1(-1.0 / p["dias_hospitalizacion"])

    # Reparto de quien sale de I, como en seir-ref: [a H, muerte directa, recupera].
    muerte_directa = np.maximum(0.0, ifr - ihr)
    reparto = np.clip(np.column_stack([ihr, muerte_directa, 1.0 - ihr - muerte_directa]), 0.0, 1.0)
    reparto /= reparto.sum(axis=1, keepdims=True)
    hasta_h = reparto[:, 0]
    hasta_d = reparto[:, 0] + reparto[:, 1]
    muerte_en_h = np.divide(np.minimum(ifr, ihr), ihr, out=np.zeros_like(ihr), where=ihr > 0)

    estado = np.full(N, S, dtype=np.int8)
    vacunado = np.zeros(N, dtype=bool)
    casos_grupo = np.zeros(G, dtype=np.int64)
    dosis_grupo = np.zeros(G, dtype=np.int64)

    iniciales = rng.choice(N, size=p["infectados_iniciales"], replace=False)
    estado[iniciales] = I
    casos_grupo += np.bincount(grupo[iniciales], minlength=G)

    def fila(dia, nuevos_casos=0, nuevas_hosp=0, nuevas_def=0, dosis=0):
        cuenta = np.bincount(estado, minlength=7)
        return {
            "dia": dia,
            "S": int(cuenta[S]), "E": int(cuenta[E]), "I": int(cuenta[I]), "R": int(cuenta[R]),
            "H": int(cuenta[H]), "D": int(cuenta[D]), "V": int(cuenta[V]),
            "casos_activos": int(cuenta[E] + cuenta[I] + cuenta[H]),
            "nuevos_casos": int(nuevos_casos),
            "nuevas_hospitalizaciones": int(nuevas_hosp),
            "nuevas_defunciones": int(nuevas_def),
            "dosis_aplicadas": int(dosis),
        }

    serie = [fila(0)]
    vacunaciones = [iv for iv in p["intervenciones"] if iv["clase"] == "vacunacion"]

    for dia in range(1, p["dias"] + 1):
        activas = [iv for iv in p["intervenciones"] if _activa(iv, dia)]

        # Todo se decide sobre el estado al empezar el día, así que el orden en que se aplica
        # no cambia nada; el orden de los sorteos sí es parte de la reproducibilidad.
        susceptibles = np.flatnonzero(estado == S)
        lam = _fuerza_de_infeccion(susceptibles, estado, capas, p["capas_contacto"],
                                   _multiplicadores(p["capas_contacto"], activas),
                                   beta * _factor_aislamiento(activas)) * escala[susceptibles]
        nuevos_e = susceptibles[rng.random(len(susceptibles)) < -np.expm1(-lam)]

        expuestos = np.flatnonzero(estado == E)
        nuevos_i = expuestos[rng.random(len(expuestos)) < p_ei]

        infecciosos = np.flatnonzero(estado == I)
        salen_i = infecciosos[rng.random(len(infecciosos)) < p_sale_i]
        sorteo = rng.random(len(salen_i))
        g = grupo[salen_i]
        a_h = salen_i[sorteo < hasta_h[g]]
        a_d = salen_i[(sorteo >= hasta_h[g]) & (sorteo < hasta_d[g])]
        a_r = salen_i[sorteo >= hasta_d[g]]

        hospitalizados = np.flatnonzero(estado == H)
        salen_h = hospitalizados[rng.random(len(hospitalizados)) < p_sale_h]
        muere = rng.random(len(salen_h)) < muerte_en_h[grupo[salen_h]]

        estado[nuevos_e] = E
        estado[nuevos_i] = I
        estado[a_h] = H
        estado[a_d] = D
        estado[a_r] = R
        estado[salen_h[muere]] = D
        estado[salen_h[~muere]] = R
        casos_grupo += np.bincount(grupo[nuevos_e], minlength=G)

        dosis_dia = 0
        for iv in vacunaciones:
            if not _activa(iv, dia):
                continue
            dosis_dia += _vacuna(iv, estado, vacunado, grupo, pob, inicio_grupo, dosis_grupo,
                                 p["edad_minima_grupo"], rng)

        if estado.min() < S or estado.max() > V:
            raise ErrorMotor(f"Un agente quedó en un estado desconocido el día {dia}.")

        serie.append(fila(dia, len(nuevos_e), len(a_h), len(a_d) + int(muere.sum()), dosis_dia))

    fallecidos = np.bincount(grupo[estado == D], minlength=G)
    protegidos = np.bincount(grupo[estado == V], minlength=G)
    desglose = [
        {"grupo": nombre, "poblacion": int(pob[i]), "casos": int(casos_grupo[i]),
         "fallecimientos": int(fallecidos[i]), "vacunados_protegidos": int(protegidos[i]),
         "dosis_aplicadas": int(dosis_grupo[i])}
        for i, nombre in enumerate(p["grupos"])
    ]

    return {
        "engine_version": ENGINE_VERSION,
        "semilla": semilla,
        "numpy_version": np.__version__,
        "huella_escenario": huella(escenario),
        "dias": p["dias"],
        "poblacion": N,
        "serie": serie,
        "resumen": resumir(serie, N, p["infectados_iniciales"], desglose),
        "trazabilidad_parametros": p["trazabilidad"] + traza_capas,
        "simplificaciones": SIMPLIFICACIONES,
        "avisos": p["avisos"] + avisos_capas,
    }


def _vacuna(iv, estado, vacunado, grupo, pob, inicio_grupo, dosis_grupo, edad_minima, rng):
    """Aplica las dosis del día de una campaña. Regresa cuántas aplicó.

    El cupo por grupo es el de seir-ref: hasta `tope` de su población y solo entre vivos no
    hospitalizados. Aquí, además, nadie recibe dos dosis."""
    G = len(pob)
    disponible = (estado != D) & (estado != H) & ~vacunado
    disponibles = np.bincount(grupo[disponible], minlength=G)
    objetivo = np.zeros(G, dtype=bool)
    objetivo[iv["grupos_objetivo"]] = True
    tope = np.floor(iv["tope"] * pob).astype(np.int64) - dosis_grupo
    cupo = np.where(objetivo, np.clip(np.minimum(tope, disponibles), 0, None), 0)
    a_repartir = min(iv["dosis_diarias"], int(cupo.sum()))
    if a_repartir == 0:
        return 0

    if iv["prioridad"] == "edad_desc":
        dosis = np.zeros(G, dtype=np.int64)
        restante = a_repartir
        for g in sorted(range(G), key=lambda g: -edad_minima[g]):
            dosis[g] = min(restante, cupo[g])
            restante -= dosis[g]
    else:
        dosis = rng.multivariate_hypergeometric(cupo, a_repartir)

    for g in range(G):
        if dosis[g] == 0:
            continue
        desde, hasta = inicio_grupo[g], inicio_grupo[g + 1]
        candidatos = desde + np.flatnonzero(disponible[desde:hasta])
        elegidos = rng.choice(candidatos, size=int(dosis[g]), replace=False)
        vacunado[elegidos] = True
        protegen = elegidos[(estado[elegidos] == S) & (rng.random(len(elegidos)) < iv["eficacia"])]
        estado[protegen] = V
        dosis_grupo[g] += dosis[g]
    return int(dosis.sum())
