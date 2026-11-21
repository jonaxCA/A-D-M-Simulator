import logging
import time

from procesamiento.entrada_motor import entrada_de_version
from procesamiento.motor import ErrorMotor
from procesamiento.motor.parametros import EscenarioInvalido
from procesamiento.motores import MOTOR_REFERENCIA, del_nombre

from epidemia_comun.auditoria import Contexto, log_audit

from . import datos

AGENTE_SIN_PETICION = "hilo de simulacion (sin peticion HTTP)"


def sin_peticion(user_id):
    return Contexto(user_id, None, AGENTE_SIN_PETICION)


def escenario_de_version(version_id):
    version, intervenciones = datos.version_para_motor(version_id)
    return entrada_de_version(version, intervenciones)


MENSAJE_ERROR_FORZADO = (
    "Error forzado de prueba: se solicito explicitamente desde la pantalla de "
    "simulaciones (opcion visible solo para ADMINISTRADOR). Demuestra el "
    "camino encolado -> ejecutando -> fallido sin depender de que un escenario "
    "real este incompleto."
)


def id_simulacion(run_id):
    return f"SIM-{int(run_id):05d}"


def ejecutar_run(run_id, forzar_error=False, demora_seg=1.5, al_avanzar=None,
                 guardar_serie=None, descartar_serie=None):
    run = datos.get_run(run_id)
    if not run:
        return None
    contexto = sin_peticion(run["requested_by"])
    avanza = al_avanzar or (lambda porcentaje: None)

    try:
        if not datos.marcar_run_ejecutando(run_id):
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
            return None
        log_audit(contexto, "RUN", "simulation_run", entity_id=str(run_id),
                  data_after={"estado": "ejecutando", "seed": run["seed"],
                              "engine_version": run["engine_version"]})
        avanza(10)

        if demora_seg:
            time.sleep(demora_seg)

        if forzar_error:
            # Camino de ERROR deliberado -- ver MENSAJE_ERROR_FORZADO. No se
            # llega ni a construir el escenario: es un fallo pedido a
            # proposito, no uno real del motor ni de los datos.
            raise ValueError(MENSAJE_ERROR_FORZADO)

        # El motor es el del lote (D2): cada simulador toma de la cola solo los suyos, pero el
        # que manda es el lote. Uno que no esta implementado aqui falla con su nombre.
        motor = del_nombre(datos.get_motor_run(run_id) or MOTOR_REFERENCIA)

        escenario, _version, errores = escenario_de_version(run["scenario_version_id"])
        if errores:
            raise ValueError("; ".join(errores))
        avanza(30)

        resultado = motor.simular(escenario, run["seed"])
        avanza(90)
        # La serie va antes de confirmar: si el proceso muere entre los dos
        # pasos, la corrida se queda 'ejecutando' con su serie, nunca
        # 'completado' sin ella.
        if guardar_serie:
            try:
                guardar_serie(run, motor.nombre, resultado)
            except Exception:
                logging.getLogger(__name__).exception(
                    "No se pudo guardar la serie de la corrida %s; se confirma con su "
                    "resumen.", run_id)
        if not datos.guardar_resultado_run(run_id, resultado):
            # Alguien cerro la corrida mientras el motor trabajaba (otro
            # proceso que arranco y la dio por interrumpida). Su estado
            # actual manda: no se guarda un resultado que lo contradiga ni se
            # audita un 'completado' que no ocurrio.
            logging.getLogger(__name__).warning(
                "La corrida %s termino en el motor, pero ya no estaba en "
                "'ejecutando'; el resultado se descarto.", run_id)
            if descartar_serie:
                try:
                    descartar_serie(run_id)
                except Exception:
                    logging.getLogger(__name__).exception(
                        "No se pudo descartar la serie de la corrida %s.", run_id)
            return None
        log_audit(contexto, "RUN", "simulation_run", entity_id=str(run_id),
                  data_after={
                      "estado": "completado", "seed": run["seed"],
                      "engine_version": resultado["engine_version"],
                      "indicadores": resultado["resumen"],
                  })
        avanza(100)
        return "completado"

    except EscenarioInvalido as exc:
        mensaje = "; ".join(exc.errores)
        cerrada = _marca_fallido_y_audita(run, mensaje)
    except (ValueError, ErrorMotor) as exc:
        cerrada = _marca_fallido_y_audita(run, str(exc))
    except Exception as exc:  # pragma: no cover - red de seguridad del hilo
        # Cualquier otra falla (conexion caida, bug del motor, etc.) tiene que
        # quedar en error_message y en la bitacora, no perderse en el hilo:
        # un hilo que muere en silencio deja la corrida en 'ejecutando' para
        # siempre, sin explicacion.
        cerrada = _marca_fallido_y_audita(run, f"Error inesperado del motor: {exc}")
    return "fallido" if cerrada else None


def _marca_fallido_y_audita(run, mensaje):
    mensaje = (mensaje or "Error desconocido en la simulacion.")[:2000]
    try:
        cambio = datos.marcar_run_fallido(run["id"], mensaje)
    except Exception:
        logging.getLogger(__name__).exception(
            "No se pudo marcar la corrida %s como fallida (mensaje original: %s)",
            run["id"], mensaje,
        )
        return False

    if not cambio:
        # rowcount == 0: la corrida ya estaba en un estado terminal
        # (completado/fallido/cancelado). No hubo transicion real a
        # 'fallido' -- auditarla como si hubiera ocurrido seria mentir en la
        # bitacora.
        return False

    try:
        log_audit(sin_peticion(run["requested_by"]), "RUN", "simulation_run",
                  entity_id=str(run["id"]),
                  data_after={"estado": "fallido", "seed": run["seed"], "error": mensaje[:500]})
    except Exception:
        logging.getLogger(__name__).exception(
            "La corrida %s se marco 'fallido' en DB pero no se pudo registrar "
            "la auditoria (mensaje: %s)", run["id"], mensaje,
        )
    return True


MENSAJE_INTERRUMPIDA = (
    "Interrumpida: el servidor se reinicio antes de que la corrida terminara, "
    "y con el se perdio el hilo que la ejecutaba. No es un error del motor ni "
    "del escenario: re-ejecutala con la misma semilla y dara el mismo resultado."
)


def reencola_corridas_interrumpidas(engine, engine_version, max_intentos=3):
    reencoladas = datos.reencola_corridas_interrumpidas(engine, engine_version, max_intentos)
    for fila in reencoladas:
        try:
            log_audit(sin_peticion(fila["requested_by"]), "RUN", "simulation_run",
                      entity_id=str(fila["id"]),
                      data_after={"estado": "encolado", "seed": fila["seed"],
                                  "intento": fila["attempts"],
                                  "motivo": "reinicio del trabajador (D38)"})
        except Exception:
            logging.getLogger(__name__).exception(
                "La corrida %s se reencoló pero no se pudo auditar", fila["id"])
    cerradas = datos.marca_corridas_interrumpidas(MENSAJE_INTERRUMPIDA, estados=("ejecutando",),
                                                    engine=engine)
    for fila in cerradas:
        try:
            log_audit(sin_peticion(fila["requested_by"]), "RUN", "simulation_run",
                      entity_id=str(fila["id"]),
                      data_after={"estado": "fallido", "seed": fila["seed"],
                                  "error": MENSAJE_INTERRUMPIDA[:500],
                                  "motivo": "sin intentos o con otra versión de motor (D38)"})
        except Exception:
            logging.getLogger(__name__).exception(
                "La corrida %s se cerró como interrumpida pero no se pudo auditar", fila["id"])
    return [f["id"] for f in reencoladas], [f["id"] for f in cerradas]
