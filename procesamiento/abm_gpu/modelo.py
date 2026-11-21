"""abm-gpu: el modelo de abm-ref en FLAME GPU 2 (D23).

Es el mismo modelo que procesamiento/abm (abm-ref), con el mismo contrato: cada persona es un
agente con su grupo de edad, su hogar y, según su edad, su salón o su centro de trabajo, y un
día tiene los mismos pasos y las mismas probabilidades. Lo que cambia es dónde corre:

- La población (grupos de contacto, escala de contactos e infectados iniciales) la arma NumPy
  con el mismo código y la misma semilla que abm-ref, así que las dos corridas empiezan igual.
  Llega a la GPU como un archivo binario, de un solo jalón.
- El día corre en la GPU, en este orden de capas:
    1. prepara_dia (host): pesos del día por capa, con las intervenciones activas; pone en cero
       los conteos por grupo de contacto.
    2. cuenta (agentes): infecciosos y vivos de cada hogar, salón y centro de trabajo.
    3. avanza (agentes): S -> E, E -> I, I -> H/D/R y H -> D/R, con las fórmulas de abm-ref.
    4. reparte_vacunas (host), solo si hay campañas: dosis por grupo de edad con la regla de
       abm-ref y orden al azar de los agentes que se pueden vacunar.
    5. vacuna (agentes), solo si hay campañas.
  y al cerrar el día (host) se cuentan los estados para la fila de la serie.
- El azar de la epidemia sale del generador de FLAME GPU (cuRAND, sembrado con la semilla), no
  del de NumPy. Con la misma semilla, abm-gpu y abm-ref arrancan con la misma población, pero
  la corrida no es la misma: se comparan sus distribuciones, no sus números.

La salida tiene la forma del contrato de los motores (docs/contratos/motor/README.md).
"""
import math
import os
import pathlib
import re
import tempfile

import numpy as np

from procesamiento.abm.modelo import SIMPLIFICACIONES as SIMPLIFICACIONES_ABM
from procesamiento.abm.modelo import _activa, _escala, _factor_aislamiento, _multiplicadores
from procesamiento.abm.poblacion import CAPAS_AGRUPADAS, arma_capas
from procesamiento.contrato import huella
from procesamiento.motor import ErrorMotor, resolver
from procesamiento.motor.indicadores import resumir

from .entorno import SinFlameGPU, carga

ENGINE_VERSION = "abm-gpu-0.1"

SIMPLIFICACIONES = SIMPLIFICACIONES_ABM + [
    "El azar de la epidemia sale del generador de FLAME GPU (cuRAND), no del de NumPy: con la "
    "misma semilla, abm-gpu arma la misma población que abm-ref, pero no sigue la misma "
    "corrida. La misma semilla repite la corrida en la misma GPU y con la misma versión de "
    "FLAME GPU.",
    "Las probabilidades de cada agente se calculan en precisión simple (float de 32 bits).",
]

S, E, I, R, H, D, V = range(7)
_FUENTE = pathlib.Path(__file__).with_name("agentes.cu")
# Columnas de la propiedad macro "poblacion" (agentes.cu, COL_*).
_POBLACION = ("grupo", "hogar", "salon", "trabajo", "infectado")


def _funciones():
    """{nombre: código} de agentes.cu, cada uno con la parte común al principio."""
    texto = _FUENTE.read_text(encoding="utf-8")
    partes = re.split(r"^//@funcion (\w+)\s*$", texto, flags=re.M)
    comun, resto = partes[0], partes[1:]
    return {resto[k]: comun + resto[k + 1] for k in range(0, len(resto), 2)}


class _Corrida:
    """Lo que las funciones de host comparten durante una corrida."""

    def __init__(self, p, pob, rng, vacunaciones, archivos):
        self.p = p
        self.pob = pob
        self.N = int(pob.sum())
        self.G = len(pob)
        self.rng = rng
        self.vacunaciones = vacunaciones
        self.archivos = archivos
        self.beta = p["r0"] / p["infeccioso_dias"]
        self.inicio_grupo = np.concatenate([[0], np.cumsum(pob)])[:-1].astype(int)
        self.dosis_grupo = np.zeros(self.G, dtype=np.int64)
        self.infecciosos = int(p["infectados_iniciales"])
        self.vivos = self.N
        self.dosis_dia = 0
        self.serie = []
        self.por_grupo = {}


def _hosts(fg, corrida):
    """Las funciones de host de la corrida (clases de pyflamegpu.HostFunction)."""
    c = corrida
    p = c.p

    class Carga(fg.HostFunction):
        def run(self, F):
            F.environment.importMacroProperty("poblacion", c.archivos["poblacion"])
            F.environment.importMacroProperty("escala_de", c.archivos["escala_de"])

    class PreparaDia(fg.HostFunction):
        def run(self, F):
            dia = F.getStepCounter() + 1
            activas = [iv for iv in p["intervenciones"] if _activa(iv, dia)]
            env = F.environment
            env.setPropertyUInt("dia", dia)
            b = c.beta * _factor_aislamiento(activas)
            mult = _multiplicadores(p["capas_contacto"], activas)
            w = {capa: b * peso * mult[capa] for capa, peso in p["capas_contacto"].items()}
            mezcla = sum(v for capa, v in w.items() if capa not in CAPAS_AGRUPADAS)
            env.setPropertyFloat("lam_mezcla", mezcla * c.infecciosos / max(c.vivos, 1))
            env.setPropertyFloat("w_hogar", w.get("hogar", 0.0))
            env.setPropertyFloat("w_escuela", w.get("escuela", 0.0))
            env.setPropertyFloat("w_trabajo", w.get("trabajo", 0.0))
            for nombre in ("inf_hogar", "viv_hogar", "inf_salon", "viv_salon", "inf_trabajo",
                           "viv_trabajo", "eventos"):
                env.getMacroPropertyUInt(nombre).zero()
            if c.vacunaciones:
                hoy = any(_activa(iv, dia) for iv in c.vacunaciones)
                env.setPropertyUInt("vacuna_hoy", int(hoy))
                env.setPropertyUInt("aplica_vacuna", 0)
                env.getMacroPropertyUInt("disp_grupo").zero()
            c.dosis_dia = 0

    class RepartaVacunas(fg.HostFunction):
        """Las dosis de cada campaña por grupo de edad, como en abm-ref (_vacuna): hasta el
        tope de su población, solo a quien se puede vacunar y nadie dos veces."""

        def run(self, F):
            dia = F.getStepCounter() + 1
            if not any(_activa(iv, dia) for iv in c.vacunaciones):
                return
            env = F.environment
            disp = env.getMacroPropertyUInt("disp_grupo")
            disponibles = np.array([int(disp[g]) for g in range(c.G)], dtype=np.int64)
            lo = np.zeros((len(c.vacunaciones), c.G), dtype=np.int64)
            hi = np.zeros_like(lo)
            usados = np.zeros(c.G, dtype=np.int64)
            for k, iv in enumerate(c.vacunaciones):
                lo[k] = hi[k] = usados
                if not _activa(iv, dia):
                    continue
                objetivo = np.zeros(c.G, dtype=bool)
                objetivo[iv["grupos_objetivo"]] = True
                tope = np.floor(iv["tope"] * c.pob).astype(np.int64) - c.dosis_grupo
                cupo = np.where(objetivo,
                                np.clip(np.minimum(tope, disponibles - usados), 0, None), 0)
                a_repartir = min(iv["dosis_diarias"], int(cupo.sum()))
                if a_repartir == 0:
                    continue
                if iv["prioridad"] == "edad_desc":
                    dosis = np.zeros(c.G, dtype=np.int64)
                    restante = a_repartir
                    for g in sorted(range(c.G), key=lambda g: -p["edad_minima_grupo"][g]):
                        dosis[g] = min(restante, cupo[g])
                        restante -= dosis[g]
                else:
                    dosis = c.rng.multivariate_hypergeometric(cupo, a_repartir)
                hi[k] = usados + dosis
                usados += dosis
                c.dosis_grupo += dosis
            if not usados.any():
                return
            env.setPropertyArrayInt("corte_lo", _arreglo([int(x) for x in lo.ravel()]))
            env.setPropertyArrayInt("corte_hi", _arreglo([int(x) for x in hi.ravel()]))
            env.setPropertyUInt("aplica_vacuna", 1)
            F.agent("persona").sortUInt64("clave", fg.HostAgentAPI.Asc)
            c.dosis_dia = int(usados.sum())

    class CierraDia(fg.HostFunction):
        def run(self, F):
            dia = F.getStepCounter() + 1
            agente = F.agent("persona")
            cuenta = [agente.countInt("estado", k) for k in range(7)]
            if sum(cuenta) != c.N:
                raise ErrorMotor(f"Se rompió la conservación de la población en el día {dia}.")
            eventos = F.environment.getMacroPropertyUInt("eventos")
            nuevos, hosp, defs = (int(eventos[k]) for k in range(3))
            c.infecciosos = cuenta[I]
            c.vivos = c.N - cuenta[D]
            c.serie.append(_fila(dia, cuenta, nuevos, hosp, defs, c.dosis_dia))
            if dia == p["dias"]:
                for nombre in ("casos_grupo", "muertes_grupo", "protegidos_grupo"):
                    m = F.environment.getMacroPropertyUInt(nombre)
                    c.por_grupo[nombre] = np.array([int(m[g]) for g in range(c.G)])

    return Carga(), PreparaDia(), RepartaVacunas(), CierraDia()


def _fila(dia, cuenta, nuevos_casos=0, nuevas_hosp=0, nuevas_def=0, dosis=0):
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


def _modelo(fg, corrida, hosts):
    c = corrida
    p = c.p
    C = len(c.vacunaciones)
    carga, prepara, reparte, cierra = hosts

    modelo = fg.ModelDescription("epidemia_abm_gpu")
    env = modelo.Environment()
    env.newPropertyUInt("dia", 0)
    env.newPropertyFloat("lam_mezcla", 0.0)
    for capa in ("hogar", "escuela", "trabajo"):
        env.newPropertyFloat("w_" + capa, 0.0)
    env.newPropertyFloat("p_ei", -math.expm1(-1.0 / p["incubacion_dias"]))
    env.newPropertyFloat("p_sale_i", -math.expm1(-1.0 / p["infeccioso_dias"]))
    env.newPropertyFloat("p_sale_h", -math.expm1(-1.0 / p["dias_hospitalizacion"]))

    # Reparto de quien sale de I, como en abm-ref: [a H, muerte directa, recupera].
    ihr = np.array(p["tasa_hospitalizacion"], dtype=float)
    ifr = np.array(p["letalidad"], dtype=float)
    muerte_directa = np.maximum(0.0, ifr - ihr)
    reparto = np.clip(np.column_stack([ihr, muerte_directa, 1.0 - ihr - muerte_directa]), 0.0, 1.0)
    reparto /= reparto.sum(axis=1, keepdims=True)
    muerte_en_h = np.divide(np.minimum(ifr, ihr), ihr, out=np.zeros_like(ihr), where=ihr > 0)
    env.newPropertyArrayFloat("hasta_h", _arreglo([float(x) for x in reparto[:, 0]]))
    env.newPropertyArrayFloat("hasta_d", _arreglo([float(x) for x in reparto[:, 0] + reparto[:, 1]]))
    env.newPropertyArrayFloat("muerte_en_h", _arreglo([float(x) for x in muerte_en_h]))

    env.newMacroPropertyInt("poblacion", c.N, len(_POBLACION))
    env.newMacroPropertyFloat("escala_de", c.N)
    for nombre in ("inf_hogar", "viv_hogar", "inf_salon", "viv_salon", "inf_trabajo",
                   "viv_trabajo"):
        env.newMacroPropertyUInt(nombre, c.N)
    env.newMacroPropertyUInt("eventos", 3)
    for nombre in ("casos_grupo", "muertes_grupo", "protegidos_grupo", "disp_grupo"):
        env.newMacroPropertyUInt(nombre, max(c.G, 2))
    if C:
        env.newPropertyUInt("vacuna_hoy", 0)
        env.newPropertyUInt("aplica_vacuna", 0)
        env.newPropertyArrayInt("inicio_grupo", _arreglo([int(x) for x in c.inicio_grupo]))
        env.newPropertyArrayInt("corte_lo", _arreglo([0] * (C * c.G)))
        env.newPropertyArrayInt("corte_hi", _arreglo([0] * (C * c.G)))
        env.newPropertyArrayFloat("eficacia", _arreglo([float(iv["eficacia"]) for iv in c.vacunaciones]))

    agente = modelo.newAgent("persona")
    for nombre in ("estado", "grupo", "hogar", "salon", "trabajo", "vacunado"):
        agente.newVariableInt(nombre)
    agente.newVariableFloat("escala")
    agente.newVariableUInt64("clave")

    prologo = ("#define AGENTES %du\n#define GRUPOS %du\n#define GRUPOS_M %du\n#define CAMPANAS %d\n"
               % (c.N, c.G, max(c.G, 2), C))
    funciones = {nombre: agente.newRTCFunction(nombre, prologo + codigo)
                 for nombre, codigo in _funciones().items() if C or nombre != "vacuna"}

    modelo.addInitFunction(carga)
    modelo.newLayer("prepara_dia").addHostFunction(prepara)
    modelo.newLayer("cuenta").addAgentFunction(funciones["cuenta"])
    modelo.newLayer("avanza").addAgentFunction(funciones["avanza"])
    if C:
        modelo.newLayer("reparte_vacunas").addHostFunction(reparte)
        modelo.newLayer("vacuna").addAgentFunction(funciones["vacuna"])
    modelo.addStepFunction(cierra)
    return modelo, agente


def _arreglo(valores):
    """Una lista para un arreglo del entorno. FLAME GPU guarda uno de un solo elemento como
    valor simple y entonces no se puede leer por índice: se agrega un elemento de relleno."""
    return list(valores) + [type(valores[0])(0)] if len(valores) else [0, 0]


def _escribe_poblacion(directorio, grupo, capas, iniciales, escala):
    """La población en dos archivos binarios, con el orden de memoria de la propiedad macro."""
    n = len(grupo)
    tabla = np.full((n, len(_POBLACION)), -1, dtype=np.int32)
    tabla[:, 0] = grupo
    for col, capa in ((1, "hogar"), (2, "escuela"), (3, "trabajo")):
        if capa in capas:
            tabla[:, col] = capas[capa][0]
    tabla[:, 4] = 0
    tabla[iniciales, 4] = 1
    archivos = {"poblacion": os.path.join(directorio, "poblacion.bin"),
                "escala_de": os.path.join(directorio, "escala_de.bin")}
    tabla.tofile(archivos["poblacion"])
    np.asarray(escala, dtype=np.float32).tofile(archivos["escala_de"])
    return archivos


def simular(escenario, semilla):
    """Corre el escenario en la GPU y regresa serie diaria, resumen y trazabilidad, con la
    forma del contrato de los motores.

    Levanta EscenarioInvalido si la entrada no es simulable, SinFlameGPU si falta pyflamegpu
    y ErrorMotor si algo falla durante la corrida."""
    if isinstance(semilla, bool) or not isinstance(semilla, int) or semilla < 0:
        raise ValueError("La semilla debe ser un entero >= 0.")

    p = resolver(escenario)
    fg = carga()

    # La población, igual que en abm-ref: mismo generador, mismos sorteos y en el mismo orden.
    rng = np.random.default_rng(semilla)
    pob = np.array(p["poblacion"], dtype=np.int64)
    N = int(p["N"])
    G = len(pob)
    grupo = np.repeat(np.arange(G, dtype=np.int16), pob)
    capas, traza_capas, avisos_capas = arma_capas(grupo, p["edad_minima_grupo"], rng)
    capas = {k: capas[k] for k in CAPAS_AGRUPADAS if k in p["capas_contacto"]}
    escala = _escala(capas, p["capas_contacto"], N)
    iniciales = rng.choice(N, size=p["infectados_iniciales"], replace=False)

    vacunaciones = [iv for iv in p["intervenciones"] if iv["clase"] == "vacunacion"]
    with tempfile.TemporaryDirectory(prefix="abm-gpu-") as directorio:
        archivos = _escribe_poblacion(directorio, grupo, capas, iniciales, escala)
        corrida = _Corrida(p, pob, rng, vacunaciones, archivos)
        hosts = _hosts(fg, corrida)
        modelo, agente = _modelo(fg, corrida, hosts)
        try:
            sim = fg.CUDASimulation(modelo)
            sim.SimulationConfig().steps = p["dias"]
            sim.SimulationConfig().random_seed = semilla
            sim.SimulationConfig().verbosity = fg.Verbosity_Quiet
            sim.SimulationConfig().telemetry = False
            sim.setPopulationData(fg.AgentVector(agente, N))
            sim.simulate()
        except ErrorMotor:
            raise
        except fg.FLAMEGPURuntimeException as exc:
            raise ErrorMotor("FLAME GPU no pudo correr la simulación: %s" % exc) from exc

    casos_iniciales = np.bincount(grupo[iniciales], minlength=G)
    inicio = [0] * 7
    inicio[S], inicio[I] = N - int(p["infectados_iniciales"]), int(p["infectados_iniciales"])
    serie = [_fila(0, inicio)] + corrida.serie
    por_grupo = corrida.por_grupo
    desglose = [
        {"grupo": nombre, "poblacion": int(pob[i]),
         "casos": int(casos_iniciales[i] + por_grupo["casos_grupo"][i]),
         "fallecimientos": int(por_grupo["muertes_grupo"][i]),
         "vacunados_protegidos": int(por_grupo["protegidos_grupo"][i]),
         "dosis_aplicadas": int(corrida.dosis_grupo[i])}
        for i, nombre in enumerate(p["grupos"])
    ]

    return {
        "engine_version": ENGINE_VERSION,
        "semilla": semilla,
        "numpy_version": np.__version__,
        "flamegpu_version": fg.__version__,
        "huella_escenario": huella(escenario),
        "dias": p["dias"],
        "poblacion": N,
        "serie": serie,
        "resumen": resumir(serie, N, p["infectados_iniciales"], desglose),
        "trazabilidad_parametros": p["trazabilidad"] + traza_capas,
        "simplificaciones": SIMPLIFICACIONES,
        "avisos": p["avisos"] + avisos_capas,
    }


__all__ = ["ENGINE_VERSION", "SIMPLIFICACIONES", "SinFlameGPU", "simular"]
