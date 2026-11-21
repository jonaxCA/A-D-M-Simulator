"""
Ejecucion, estados y resultados de simulaciones.

Responsabilidades que viven aqui a proposito, separadas de queries.py
(que solo habla SQL) y de routes.py (que solo habla HTTP):

  1. Obtener la entrada del motor de una version de escenario aprobada. La
     traduccion es queries.escenario_de_version(), la misma que usa la
     revision de escenarios: lo que se aprueba es lo que se simula. Aqui solo
     se revisa que la version este aprobada y que su enfermedad sea simulable.
     Esto NO puede vivir en procesamiento/motor/: ese paquete es
     deliberadamente independiente de Flask y de la base de datos.
  2. Formato de los identificadores visibles ESC-003 / SIM-00042 y de los
     estados, que se muestran tal como estan en la base (regla 7 de AGENTS.md).
  3. La comparacion costo vs impacto de la pantalla.

La corrida en segundo plano (ejecutar_run) y las transiciones de estado ya no
estan aqui: son del servicio simulador (microservicios/simulador/ejecucion.py).
Nada de lo de aqui importa Flask.
"""

# El motor se importa como `procesamiento.motor`, igual que en queries.py.
# Con otro nombre (por ejemplo, metiendo procesamiento/ en sys.path e
# importando `motor`), Python cargaria el paquete DOS veces, con dos clases
# EscenarioInvalido distintas: un `except EscenarioInvalido` de un lado no
# atraparia lo que lanza el otro. backend_web/tests/test_integridad.py lo
# vigila. (Las pruebas del motor usan `from motor import ...` porque corren
# desde dentro de procesamiento/, en otro proceso.)
from procesamiento.analitica import ComparacionInvalida, comparar as comparar_pareto
from procesamiento.analitica import factor_de_escala, representados
from procesamiento.motor import AVISO_SIMULACION, ENGINE_VERSION, ErrorMotor, simular  # noqa: F401
from procesamiento.motor.modelo import SIMPLIFICACIONES                      # noqa: F401
from procesamiento.motor.parametros import EscenarioInvalido                  # noqa: F401
from procesamiento.motores import de_version as motor_de_version

from . import queries


# ---------------------------------------------------------------------------
# Identificadores visibles
# ---------------------------------------------------------------------------
def id_simulacion(run_id):
    """SIM-00042. Cinco digitos con cero a la izquierda; si algun dia hay mas
    de 99,999 corridas, format() simplemente deja de rellenar -- no trunca."""
    return f"SIM-{int(run_id):05d}"


def id_escenario(scenario_id):
    """ESC-003. Identifica al ESCENARIO (scenarios.id), no a la version."""
    return f"ESC-{int(scenario_id):03d}"


# ---------------------------------------------------------------------------
# Estados de la base (007/014)
# ---------------------------------------------------------------------------
# Para el badge de la pantalla: reusa las clases CSS que ya existen
# (dashboard/enfermedades), en vez de inventar una paleta nueva.
CLASE_BADGE_ESTADO = {
    "encolado": "badge-pendiente",
    "ejecutando": "badge-pendiente",
    "completado": "badge-correcto",
    "fallido": "badge-fallido",
    "cancelado": "badge-inactivo",
}


def motor_de_resultado(engine_version):
    """(version actual, simplificaciones) del motor que produjo un resultado, para mostrarlas
    junto a el. Si la version no se reconoce: (engine_version, [])."""
    motor = motor_de_version(engine_version)
    if motor is None:
        return engine_version, []
    return motor.version, list(motor.simplificaciones)


def escala(habitantes, agentes, resumen=None):
    """El factor de escala de D6 (habitantes de la region / agentes simulados) y, si llega un
    resumen, sus conteos llevados a habitantes. Lo calcula procesamiento/analitica, fuera del
    motor: el motor solo ve agentes."""
    datos = factor_de_escala(habitantes, agentes)
    datos["representados"] = representados(resumen, datos) if resumen else {}
    return datos


def estado_visible(status_db):
    """El estado de la base en mayusculas, como la columna de versiones."""
    return (status_db or "").upper()


def clase_badge_estado(status_db):
    return CLASE_BADGE_ESTADO.get(status_db, "badge-inactivo")


# ---------------------------------------------------------------------------
# Traduccion: version de escenario -> entrada del motor
# ---------------------------------------------------------------------------
def construir_escenario_desde_version(version_id):
    """Entrada del motor para una scenario_version aprobada.

    Devuelve (escenario, version, errores). `version` viaja siempre que la fila
    exista, incluso si hay errores despues -- routes.py y el runner en
    segundo plano lo necesitan para el mensaje y para la auditoria.
    """
    version = queries.get_version_simulacion(version_id)
    if not version:
        return None, None, ["La version de escenario no existe."]

    if version["status"] != "aprobado":
        return None, version, [
            f"La version {version['version_number']} de "
            f"{id_escenario(version['scenario_id'])} no esta aprobada "
            f"(estado: {version['status']}); solo se puede simular una "
            f"version aprobada."
        ]

    detalle = queries.get_escenario_detalle(version["scenario_id"], version["version_number"])
    if not detalle:
        return None, version, ["La version de escenario no existe."]

    # Los parametros que valen para la version: los congelados al enviarla a
    # revision (024), o los vivos si salio de borrador antes de esa migracion.
    estado = queries.estado_parametros(detalle["parametros_enfermedad"])
    if not estado["simulable"]:
        return None, version, [
            f"La enfermedad de este escenario no se puede simular: "
            f"{queries.motivo_no_simulable(len(estado['faltan']), len(estado['sin_fuente']))}."
        ]

    return queries.escenario_de_version(detalle), version, []


# ---------------------------------------------------------------------------
# Comparacion costo vs impacto
# ---------------------------------------------------------------------------
def construir_comparacion_costo_impacto(run_ids, metrica="fallecimientos"):
    """Usa corridas completadas y el motor de Pareto para comparar costo e
    impacto. `run_ids` es una lista de enteros sin repetir."""
    if len(run_ids) < 2:
        return None, ["Selecciona al menos dos corridas completadas."]

    # Pesos por tipo y, para los tipos por dosis, personas-dia por dosis (D3).
    costos, factores = {}, {}
    for tipo in queries.get_tipos_intervencion():
        if tipo["unit_cost"] is not None:
            costos[tipo["code"]] = {
                "valor": float(tipo["unit_cost"]),
                "fuente": tipo["cost_source"],
                "supuesto": bool(tipo["cost_is_assumption"]),
            }
        if tipo.get("person_days_per_unit") is not None:
            factores[tipo["code"]] = {
                "valor": float(tipo["person_days_per_unit"]),
                "fuente": tipo["person_days_source"],
                "supuesto": bool(tipo["person_days_is_assumption"]),
            }

    entradas = []
    errores = []

    for run_id in run_ids:
        run = queries.get_run(run_id)
        if not run or run["status"] != "completado":
            errores.append(f"La corrida {id_simulacion(run_id)} no esta completada.")
            continue

        escenario, _version, errores_escenario = construir_escenario_desde_version(
            run["scenario_version_id"]
        )
        if errores_escenario:
            errores.extend(f"{id_simulacion(run_id)}: {e}" for e in errores_escenario)
            continue

        guardado = queries.get_resultado_run(run_id)
        if not guardado:
            errores.append(f"{id_simulacion(run_id)} no tiene resultados guardados.")
            continue

        resultado = {
            "huella_escenario": guardado["scenario_checksum"],
            "resumen": guardado["resumen"],
            "semilla": run["seed"],
            "engine_version": guardado["engine_version"],
            "dias": run["horizon_days"],
            "poblacion": run["population_size"],
        }

        entradas.append({
            "id": run_id,
            "nombre": f"{id_simulacion(run_id)} - {run['scenario_name']}",
            "escenario": escenario,
            "resultado": resultado,
        })

    if errores:
        return None, errores

    try:
        return comparar_pareto(entradas, costos, metrica=metrica, factores=factores), []
    except ComparacionInvalida as exc:
        return None, exc.errores
