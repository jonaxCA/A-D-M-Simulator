"""
Bloque F -- Ejecucion, estados y resultados de simulaciones.

Tres responsabilidades que viven aqui a proposito, separadas de queries.py
(que solo habla SQL) y de routes.py (que solo habla HTTP):

  1. Obtener la entrada del motor de una version de escenario aprobada. La
     traduccion es queries.escenario_de_version(), la misma que usa la
     revision del bloque D: lo que se aprueba es lo que se simula. Aqui solo
     se revisa que la version este aprobada y que su enfermedad sea simulable.
     Esto NO puede vivir en procesamiento/motor/: ese paquete es
     deliberadamente independiente de Flask y de la base de datos.
  2. Formato de los identificadores visibles ESC-003 / SIM-00042 y de los
     estados, que se muestran tal como estan en la base (regla 7 de AGENTS.md).
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

from motor import AVISO_SIMULACION, ENGINE_VERSION, ErrorMotor, simular  # noqa: E402,F401
from motor.modelo import SIMPLIFICACIONES                      # noqa: E402,F401
from motor.parametros import EscenarioInvalido                 # noqa: E402

from . import queries                                           # noqa: E402
from .audit import log_audit                                    # noqa: E402

MENSAJE_ERROR_FORZADO = (
    "Error forzado de prueba: se solicito explicitamente desde la pantalla de "
    "simulaciones (opcion visible solo para ADMINISTRADOR). Demuestra el "
    "camino encolado -> ejecutando -> fallido sin depender de que un escenario "
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
# Corrida en segundo plano
# ---------------------------------------------------------------------------
def ejecutar_run(run_id, forzar_error=False, demora_seg=1.5):
    """Cuerpo del hilo que corre una simulation_run ya encolada.

    Cada paso usa su propia conexion a PostgreSQL (backend_web.db.get_conn
    abre y cierra una por llamada dentro de queries.py), asi que no hace falta
    compartir conexiones ni contexto de Flask entre el hilo y la peticion que
    lo lanzo -- routes.py ya respondio con el redirect antes de que esto
    termine.

    `demora_seg` deja visible la transicion encolado -> ejecutando en la
    pantalla de detalle (que hace polling cada segundo); en pruebas se pasa 0.
    """
    run = queries.get_run(run_id)
    if not run:
        return

    try:
        if not queries.marcar_run_ejecutando(run_id):
            # rowcount == 0: la fila ya no estaba en 'encolado' (otro hilo ya
            # la arranco, o alguien la cancelo entre que se encolo y que este
            # hilo empezo). No hay transicion encolado -> ejecutando que
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
