"""
Bloque F -- Ejecucion, estados y resultados de simulaciones.

Tres responsabilidades que viven aqui a proposito, separadas de queries.py
(que solo habla SQL) y de routes.py (que solo habla HTTP):

  1. Traducir una version de escenario aprobada (scenarios + scenario_versions
     + diseases.default_params + regions/region_age_groups +
     scenario_interventions) al diccionario que espera motor.simular(). Esta
     traduccion NO puede vivir en procesamiento/motor/: ese paquete es
     deliberadamente independiente de Flask y de la base de datos (ver su
     docstring), y por eso el puente esta de este lado.
  2. Formato de los identificadores visibles ESC-003 / SIM-00042 y el mapeo de
     estados de la base (encolado/ejecutando/completado/fallido) a los rotulos
     que pide el checklist (PENDIENTE/EJECUTANDO/COMPLETADA/ERROR).
  3. La corrida en segundo plano: lo que un hilo ejecuta despues de que la
     ruta ya respondio con el redirect al detalle.

Nada de lo de aqui importa Flask. `ejecutar_run` sí registra auditoria y por
eso importa backend_web.audit.log_audit, que ya sabe operar sin contexto de
peticion (ver el guard en audit.py) -- indispensable porque este modulo corre
dentro de un hilo, no dentro de una peticion HTTP.
"""
import logging
import os
import sys
import time

# motor/ es un paquete independiente (sin __init__.py en procesamiento/, tal
# como lo consumen sus propias pruebas con `from motor import ...` corriendo
# dentro de esa carpeta). Se agrega procesamiento/ al sys.path una sola vez en
# vez de instalarlo, para no acoplar el arranque de la app a un paso de
# empaquetado que este avance no tiene.
_PROCESAMIENTO_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "procesamiento")
)
if _PROCESAMIENTO_DIR not in sys.path:
    sys.path.insert(0, _PROCESAMIENTO_DIR)

from motor import ENGINE_VERSION, ErrorMotor, simular          # noqa: E402
from motor.parametros import EscenarioInvalido                 # noqa: E402

from . import queries                                           # noqa: E402
from .audit import log_audit                                    # noqa: E402

# Los cinco grupos de edad que usa el motor (motor/parametros.py) y que trae
# region_age_groups (migracion 021). 'edad_no_especificada' se excluye a
# proposito: aqui no se simula la poblacion real de la region, se REPARTE
# population_size (el tamano de la version del escenario) con la MISMA
# proporcion por edad que tiene la region -- igual que hace
# motor/__main__.py::poblacion_por_edad con la estructura de NL. Sumar la
# categoria administrativa metería una imputacion sin que el escenario la
# haya pedido.
GRUPOS_EDAD_MOTOR = ("0-19", "20-39", "40-59", "60-79", "80+")

MENSAJE_ERROR_FORZADO = (
    "Error forzado de prueba: se solicito explicitamente desde la pantalla de "
    "simulaciones (opcion visible solo para ADMINISTRADOR). Demuestra el "
    "camino PENDIENTE -> EJECUTANDO -> ERROR sin depender de que un escenario "
    "real este incompleto."
)


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
# Estados: de la base (007/014) a lo que pide el checklist
# ---------------------------------------------------------------------------
ESTADOS_VISIBLES = {
    "encolado": "PENDIENTE",
    "ejecutando": "EJECUTANDO",
    "completado": "COMPLETADA",
    "fallido": "ERROR",
    "cancelado": "CANCELADA",
}

# Para el badge de la pantalla: reusa las clases CSS que ya existen
# (dashboard/enfermedades), en vez de inventar una paleta nueva.
CLASE_BADGE_ESTADO = {
    "encolado": "badge-pendiente",
    "ejecutando": "badge-pendiente",
    "completado": "badge-correcto",
    "fallido": "badge-fallido",
    "cancelado": "badge-inactivo",
}


def estado_visible(status_db):
    return ESTADOS_VISIBLES.get(status_db, (status_db or "").upper())


def clase_badge_estado(status_db):
    return CLASE_BADGE_ESTADO.get(status_db, "badge-inactivo")


# ---------------------------------------------------------------------------
# Traduccion: version de escenario -> entrada del motor
# ---------------------------------------------------------------------------
def _reparte_por_edad(estructura, total):
    """Reparte `total` (entero) entre los grupos de `estructura` en la misma
    proporcion que tienen sus poblaciones reales. Mismo criterio que
    motor/__main__.py::poblacion_por_edad: el residuo del redondeo se le suma
    al grupo mas grande, para que la suma cuadre exacto con `total`.

    Es una funcion pura (nada de DB, nada de Flask) para poder probarla sin
    levantar Postgres.
    """
    base = sum(estructura.values())
    if base <= 0:
        raise ValueError(
            "La region no tiene poblacion por grupo de edad capturada; no se "
            "puede repartir el tamano de la version del escenario."
        )
    reparto = {g: round(n * total / base) for g, n in estructura.items()}
    mayor = max(reparto, key=reparto.get)
    reparto[mayor] += total - sum(reparto.values())
    return reparto


def construir_escenario(*, population_size, horizon_days, initial_infected,
                        estructura_edad, default_params, intervenciones=None):
    """Construye el diccionario que espera motor.simular(), a partir de datos
    YA resueltos por el llamador (nada de SQL aqui). Devuelve (escenario,
    errores): si `errores` no esta vacio, `escenario` es None.

    No repite las validaciones de motor/parametros.py (r0 > 0, letalidad entre
    0 y 1, etc.) -- esas las hace motor.simular() al llamar a resolver(), y su
    EscenarioInvalido ya trae mensajes claros por parametro. Aqui solo se
    valida lo que es responsabilidad de ESTA traduccion: que haya con que
    construir la poblacion por edad y los parametros de la enfermedad.
    """
    errores = []
    if not isinstance(default_params, dict) or not default_params:
        errores.append(
            "La enfermedad de este escenario no tiene parametros de "
            "simulacion capturados en el catalogo."
        )
    if not isinstance(estructura_edad, dict) or not estructura_edad:
        errores.append(
            "La region de este escenario no tiene poblacion por grupo de "
            "edad capturada (region_age_groups); no se puede construir la "
            "poblacion de la simulacion."
        )
    if errores:
        return None, errores

    try:
        poblacion = _reparte_por_edad(estructura_edad, int(population_size))
    except ValueError as exc:
        return None, [str(exc)]

    escenario = {
        "poblacion": poblacion,
        "infectados_iniciales": int(initial_infected),
        "dias": int(horizon_days),
        "enfermedad": default_params,
        "intervenciones": intervenciones or [],
    }
    return escenario, []


def construir_escenario_desde_version(version_id):
    """Version con acceso a datos: resuelve una scenario_version por su id y
    delega la construccion pura a construir_escenario().

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

    enfermedad = queries.get_enfermedad(version["disease_id"])
    if not enfermedad:
        return None, version, ["La enfermedad de este escenario ya no existe en el catálogo."]

    estructura = queries.get_estructura_edad_region(version["region_id"])
    intervenciones = queries.get_intervenciones_version(version_id)

    escenario, errores = construir_escenario(
        population_size=version["population_size"],
        horizon_days=version["horizon_days"],
        initial_infected=version["initial_infected"],
        estructura_edad=estructura,
        default_params=enfermedad["default_params"],
        intervenciones=intervenciones,
    )
    return escenario, version, errores


# ---------------------------------------------------------------------------
# Corrida en segundo plano
# ---------------------------------------------------------------------------
def ejecutar_run(run_id, forzar_error=False, demora_seg=1.5):
    """Cuerpo del hilo que corre una simulation_run ya encolada.

    Cada paso usa su propia conexion a PostgreSQL (backend_web.db.get_conn
    abre y cierra una por llamada dentro de queries.py), asi que no hace falta
    compartir conexiones ni contexto de Flask entre el hilo y la peticion que
    lo lanzo -- routes.py ya respondio con el redirect antes de que esto
    termine.

    `demora_seg` deja visible la transicion PENDIENTE -> EJECUTANDO en la
    pantalla de detalle (que hace polling cada segundo); en pruebas se pasa 0.
    """
    run = queries.get_run(run_id)
    if not run:
        return

    try:
        if not queries.marcar_run_ejecutando(run_id):
            # rowcount == 0: la fila ya no estaba en 'encolado' (otro hilo ya
            # la arranco, o alguien la cancelo entre que se encolo y que este
            # hilo empezo). No hay transicion PENDIENTE -> EJECUTANDO que
            # auditar, y seguir de todos modos correria el motor sobre una
            # corrida que este hilo ya no es duenio de avanzar.
            log_audit(
                run["requested_by"], "RUN", "simulation_run", entity_id=str(run_id),
                data_after={
                    "estado": "abortado_antes_de_ejecutar",
                    "seed": run["seed"],
                    "motivo": "marcar_run_ejecutando no encontro la corrida en "
                              "estado 'encolado' (rowcount 0)",
                },
            )
            return
        log_audit(run["requested_by"], "RUN", "simulation_run", entity_id=str(run_id),
                  data_after={"estado": "ejecutando", "seed": run["seed"],
                              "engine_version": run["engine_version"]})

        if demora_seg:
            time.sleep(demora_seg)

        if forzar_error:
            # Camino de ERROR deliberado -- ver MENSAJE_ERROR_FORZADO. No se
            # llega ni a construir el escenario: es un fallo pedido a
            # proposito, no uno real del motor ni de los datos.
            raise ValueError(MENSAJE_ERROR_FORZADO)

        escenario, _version, errores = construir_escenario_desde_version(
            run["scenario_version_id"]
        )
        if errores:
            raise ValueError("; ".join(errores))

        resultado = simular(escenario, run["seed"])
        queries.guardar_resultado_run(run_id, resultado)
        log_audit(run["requested_by"], "RUN", "simulation_run", entity_id=str(run_id),
                  data_after={
                      "estado": "completado", "seed": run["seed"],
                      "engine_version": resultado["engine_version"],
                      "indicadores": resultado["resumen"],
                  })

    except EscenarioInvalido as exc:
        mensaje = "; ".join(exc.errores)
        _marca_fallido_y_audita(run, mensaje)
    except (ValueError, ErrorMotor) as exc:
        _marca_fallido_y_audita(run, str(exc))
    except Exception as exc:  # pragma: no cover - red de seguridad del hilo
        # Cualquier otra falla (conexion caida, bug del motor, etc.) tiene que
        # quedar en error_message y en la bitacora, no perderse en el hilo:
        # un hilo que muere en silencio deja la corrida en 'ejecutando' para
        # siempre, sin explicacion.
        _marca_fallido_y_audita(run, f"Error inesperado del motor: {exc}")


def _marca_fallido_y_audita(run, mensaje):
    """Ultima linea de defensa de ejecutar_run: se llama desde CADA except de
    ese try, asi que una corrida jamas puede quedar atascada en 'ejecutando'.
    Por eso esta funcion misma esta blindada -- si marcar_run_fallido() o
    log_audit() lanzaran (conexion caida, etc.), se atrapa y se deja
    constancia en el logger de la app en vez de perder el hilo en silencio
    sin que quede ningun rastro de que la corrida se quedo sin cerrar.
    """
    mensaje = (mensaje or "Error desconocido en la simulacion.")[:2000]
    try:
        cambio = queries.marcar_run_fallido(run["id"], mensaje)
    except Exception:
        logging.getLogger(__name__).exception(
            "No se pudo marcar la corrida %s como fallida (mensaje original: %s)",
            run["id"], mensaje,
        )
        return

    if not cambio:
        # rowcount == 0: la corrida ya estaba en un estado terminal
        # (completado/fallido/cancelado). No hubo transicion real a
        # 'fallido' -- auditarla como si hubiera ocurrido seria mentir en la
        # bitacora.
        return

    try:
        log_audit(run["requested_by"], "RUN", "simulation_run", entity_id=str(run["id"]),
                  data_after={"estado": "fallido", "seed": run["seed"], "error": mensaje[:500]})
    except Exception:
        logging.getLogger(__name__).exception(
            "La corrida %s se marco 'fallido' en DB pero no se pudo registrar "
            "la auditoria (mensaje: %s)", run["id"], mensaje,
        )
