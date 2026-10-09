"""
Ejecucion, estados y resultados de simulaciones.

Tres responsabilidades que viven aqui a proposito, separadas de queries.py
(que solo habla SQL) y de routes.py (que solo habla HTTP):

  1. Obtener la entrada del motor de una version de escenario aprobada. La
     traduccion es queries.escenario_de_version(), la misma que usa la
     revision de escenarios: lo que se aprueba es lo que se simula. Aqui solo
     se revisa que la version este aprobada y que su enfermedad sea simulable.
     Esto NO puede vivir en procesamiento/motor/: ese paquete es
     deliberadamente independiente de Flask y de la base de datos.
  2. Formato de los identificadores visibles ESC-003 / SIM-00042 y de los
     estados, que se muestran tal como estan en la base (regla 7 de AGENTS.md).
  3. La corrida en segundo plano: lo que un hilo ejecuta despues de que la
     ruta ya respondio con el redirect al detalle.

Nada de lo de aqui importa Flask. `ejecutar_run` corre en un hilo, sin
peticion HTTP detras, asi que audita con Contexto.sin_peticion(): el usuario
que pidio la corrida, sin IP.
"""
import logging
import time

# El motor se importa como `procesamiento.motor`, igual que en queries.py.
# Con otro nombre (por ejemplo, metiendo procesamiento/ en sys.path e
# importando `motor`), Python cargaria el paquete DOS veces, con dos clases
# EscenarioInvalido distintas: un `except EscenarioInvalido` de un lado no
# atraparia lo que lanza el otro. backend_web/tests/test_integridad.py lo
# vigila. (Las pruebas del motor usan `from motor import ...` porque corren
# desde dentro de procesamiento/, en otro proceso.)
from procesamiento.motor import AVISO_SIMULACION, ENGINE_VERSION, ErrorMotor, simular  # noqa: F401
from procesamiento.motor.modelo import SIMPLIFICACIONES                      # noqa: F401
from procesamiento.motor.parametros import EscenarioInvalido
from procesamiento.motor.pareto import ComparacionInvalida, comparar as comparar_pareto

from . import queries
from .audit import log_audit
from .contexto import Contexto

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
# Comparacion costo vs impacto
# ---------------------------------------------------------------------------
def construir_comparacion_costo_impacto(run_ids, metrica="fallecimientos"):
    """Usa corridas completadas y el motor de Pareto para comparar costo e
    impacto. `run_ids` es una lista de enteros sin repetir."""
    if len(run_ids) < 2:
        return None, ["Selecciona al menos dos corridas completadas."]

    costos = {}
    for tipo in queries.get_tipos_intervencion():
        if tipo["unit_cost"] is None:
            continue
        costos[tipo["code"]] = {
            "valor": float(tipo["unit_cost"]),
            "fuente": tipo["cost_source"],
            "supuesto": bool(tipo["cost_is_assumption"]),
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
        return comparar_pareto(entradas, costos, metrica=metrica), []
    except ComparacionInvalida as exc:
        return None, exc.errores


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
    contexto = Contexto.sin_peticion(run["requested_by"])

    try:
        if not queries.marcar_run_ejecutando(run_id):
            # rowcount == 0: la fila ya no estaba en 'encolado' (otro hilo ya
            # la arranco, o alguien la cancelo entre que se encolo y que este
            # hilo empezo). No hay transicion encolado -> ejecutando que
            # auditar, y seguir de todos modos correria el motor sobre una
            # corrida que este hilo ya no es duenio de avanzar.
            log_audit(
                contexto, "RUN", "simulation_run", entity_id=str(run_id),
                data_after={
                    "estado": "abortado_antes_de_ejecutar",
                    "seed": run["seed"],
                    "motivo": "marcar_run_ejecutando no encontro la corrida en "
                              "estado 'encolado' (rowcount 0)",
                },
            )
            return
        log_audit(contexto, "RUN", "simulation_run", entity_id=str(run_id),
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
        if not queries.guardar_resultado_run(run_id, resultado):
            # Alguien cerro la corrida mientras el motor trabajaba (otro
            # proceso que arranco y la dio por interrumpida). Su estado
            # actual manda: no se guarda un resultado que lo contradiga ni se
            # audita un 'completado' que no ocurrio.
            logging.getLogger(__name__).warning(
                "La corrida %s termino en el motor, pero ya no estaba en "
                "'ejecutando'; el resultado se descarto.", run_id)
            return
        log_audit(contexto, "RUN", "simulation_run", entity_id=str(run_id),
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
        log_audit(Contexto.sin_peticion(run["requested_by"]), "RUN", "simulation_run",
                  entity_id=str(run["id"]),
                  data_after={"estado": "fallido", "seed": run["seed"], "error": mensaje[:500]})
    except Exception:
        logging.getLogger(__name__).exception(
            "La corrida %s se marco 'fallido' en DB pero no se pudo registrar "
            "la auditoria (mensaje: %s)", run["id"], mensaje,
        )


# ---------------------------------------------------------------------------
# Corridas que se quedaron sin hilo
# ---------------------------------------------------------------------------
MENSAJE_INTERRUMPIDA = (
    "Interrumpida: el servidor se reinicio antes de que la corrida terminara, "
    "y con el se perdio el hilo que la ejecutaba. No es un error del motor ni "
    "del escenario: re-ejecutala con la misma semilla y dara el mismo resultado."
)


def recupera_corridas_interrumpidas():
    """Cierra como 'fallido' las corridas que un proceso anterior dejo a medias.

    _marca_fallido_y_audita protege contra cualquier error DENTRO del hilo,
    pero no contra que el proceso entero muera: el hilo es daemon y se va con
    el. Con `FLASK_DEBUG=1` eso pasa cada vez que se guarda un .py (el
    recargador reinicia el servidor), y sin esto la corrida se quedaria en
    'ejecutando' para siempre, con la pantalla de detalle consultando su
    estado cada segundo.

    Se llama desde frontend_web/run.py al arrancar, NO desde create_app():
    las pruebas crean la app muchas veces y no deben cerrar corridas ajenas.
    Supone un solo proceso sirviendo, que es como corre hoy la app. Con
    varios procesos (gunicorn -w 4), uno que arranca cerraria corridas vivas
    de los otros; ese caso lo resuelve la cola con worker del documento de
    arquitectura, no este barrido.

    Devuelve cuantas corridas cerro.
    """
    filas = queries.marca_corridas_interrumpidas(MENSAJE_INTERRUMPIDA)
    for fila in filas:
        try:
            log_audit(Contexto.sin_peticion(fila["requested_by"]), "RUN", "simulation_run",
                      entity_id=str(fila["id"]),
                      data_after={"estado": "fallido", "seed": fila["seed"],
                                  "error": MENSAJE_INTERRUMPIDA[:500],
                                  "motivo": "reinicio del servidor"})
        except Exception:
            logging.getLogger(__name__).exception(
                "La corrida %s se cerro como interrumpida pero no se pudo auditar",
                fila["id"])
    return len(filas)
