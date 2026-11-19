"""El proceso trabajador: toma corridas de la cola de Redis de su motor y las ejecuta.

Hay un simulador por motor (D2): SIMULADOR_MOTOR dice cuál (seir-ref si no viene) y de qué
cola toma, queue:simulaciones:<motor>. Así uno sin GPU nunca toma una corrida de abm-gpu, y una
corrida larga del ABM no detiene las del SEIR.

La corrida la ejecuta simulaciones.ejecutar_run(), la misma del monolito: marca
'ejecutando' con la transición condicionada (dos trabajadores no corren la
misma), corre el motor, guarda el resumen en simulation_runs y audita. Aquí se
lee la cola, se publica el avance en Redis, se guarda la serie diaria en MongoDB
(series_corridas, D28) antes de que ejecutar_run confirme la corrida, y se avisa a
notificaciones.
"""
import json
import logging
import os
import socket
import time

import psycopg2

from backend_web import queries, simulaciones
from epidemia_comun import cola, llaves, mongo, series_corridas
from epidemia_comun.http import llamar
from epidemia_comun.redis_compartido import RedisNoDisponible, opcional
from epidemia_comun.seguridad import token_servicio
from procesamiento.motores import MOTOR_REFERENCIA, del_nombre

log = logging.getLogger("simulador")

PROGRESO_TTL = 86400
PAUSA_SIN_REDIS = 5
REINTENTO_SERIES = 30
AVISOS = {"completado": ("RUN_FINISHED", "La corrida %s terminó"),
          "fallido": ("RUN_FAILED", "La corrida %s falló")}
# Un motor que no está implementado (abm-gpu sin FLAME GPU) detiene el arranque: sin esto, el
# simulador tomaría corridas que no puede correr.
MOTOR = del_nombre((os.environ.get("SIMULADOR_MOTOR") or MOTOR_REFERENCIA).strip()).nombre
COLA = llaves.cola_simulaciones(MOTOR)

# Lo que reporta /api/v1/worker/status. Solo lo escribe el hilo del trabajador.
estado = {"trabajador": socket.gethostname(), "motor": MOTOR, "activo": False,
          "corrida_actual": None, "procesadas": 0, "ultima": None}

pendiente = []
# Series que MongoDB no aceptó, por run_id; el ciclo las reintenta (RNF-C08). Si el proceso
# muere se pierden, pero la misma semilla vuelve a dar la misma serie (ver «Límites conocidos»
# en el README).
series_pendientes = {}


def _en_cola(crudo):
    try:
        pedido = json.loads(crudo)
    except ValueError:
        return None
    return pedido.get("id") if isinstance(pedido, dict) else pedido


def reencolar():
    presentes = {_en_cola(c) for c in cola.contenidos(COLA)}
    faltan = [i for i in simulaciones.corridas_encoladas(MOTOR) if i not in presentes]
    for run_id in faltan:
        cola.encolar(COLA, json.dumps({"id": run_id}))
    if faltan:
        log.warning("Se volvieron a encolar %d corridas que estaban encoladas en la base.",
                    len(faltan))
    return len(faltan)


def recuperar():
    # D38: las 'ejecutando' que dejó un trabajador muerto vuelven a 'encolado' y se repiten con
    # la misma semilla (su serie se reescribe por {run_id, dia}); sin intentos o con otra
    # versión de motor se cierran como fallidas y su serie se borra. Luego las encoladas se
    # meten a la cola (D19). Solo las de su motor: las de otro las atiende su simulador.
    reencoladas, cerradas = simulaciones.reencola_corridas_interrumpidas(
        MOTOR, del_nombre(MOTOR).version)
    if reencoladas:
        log.warning("Se reencolaron %d corridas que quedaron a medias.", len(reencoladas))
    for run_id in cerradas:
        descartar_serie(run_id)
    if cerradas:
        log.warning("Se cerraron como fallidas %d corridas sin intentos o de otra versión.",
                    len(cerradas))
    try:
        reencolar()
    except RedisNoDisponible:
        pendiente.append(True)
        log.warning("Redis no responde: se reintentará reencolar dentro del ciclo.")
    return reencoladas, cerradas


def guardar_serie(run, motor, resultado):
    docs = series_corridas.documentos(run, motor, resultado)
    if mongo.opcional("simulador: guardar la serie", lambda: series_corridas.guardar(docs)) is None:
        series_pendientes[run["id"]] = docs
        log.warning("MongoDB no guardó la serie de la corrida %s; se reintentará.", run["id"])


def descartar_serie(run_id):
    # ejecutar_run no confirmó la corrida (otro proceso la cerró): su serie no se queda sola.
    series_pendientes.pop(run_id, None)
    mongo.opcional("simulador: descartar la serie", lambda: series_corridas.borrar(run_id))


def reintentar_series():
    for run_id, docs in list(series_pendientes.items()):
        if mongo.opcional("simulador: reintentar la serie",
                          lambda: series_corridas.guardar(docs)) is None:
            return
        del series_pendientes[run_id]
        log.info("Se guardó la serie pendiente de la corrida %s.", run_id)


def _avance(run_id, porcentaje):
    opcional("progreso", lambda r: r.set(llaves.progreso(run_id), porcentaje, ex=PROGRESO_TTL))


def avisar(run_id, final, ajustes):
    """Best-effort: si notificaciones no responde, la corrida ya quedó cerrada."""
    corrida = queries.get_run(run_id)
    tipo, titulo = AVISOS[final]
    cuerpo = "%s, versión %d." % (corrida["scenario_name"], corrida["version_number"])
    if final == "fallido":
        cuerpo += " " + (corrida["error_message"] or "")
    try:
        resp = llamar("notificaciones", "POST", "/api/v1/notifications", timeout=3,
                      token=token_servicio(ajustes, "simulador"),
                      cuerpo={"user_id": corrida["requested_by"], "type": tipo,
                              "title": titulo % simulaciones.id_simulacion(run_id),
                              "body": cuerpo.strip(),
                              "payload": {"run_id": run_id, "status": final,
                                          "scenario_id": corrida["scenario_id"],
                                          "scenario_version_id": corrida["scenario_version_id"]}})
        if resp.status_code >= 400:
            log.warning("notificaciones respondió %d al avisar de la corrida %s",
                        resp.status_code, run_id)
    except Exception as exc:  # incluye el 503 de llamar(): nunca tumba al trabajador
        log.warning("No se pudo avisar de la corrida %s: %s", run_id, exc)


def procesar(crudo, ajustes):
    pedido = json.loads(crudo)
    # Una corrida vuelta a encolar a mano puede llegar como el id solo.
    if isinstance(pedido, int):
        pedido = {"id": pedido}
    run_id = pedido["id"]
    estado["corrida_actual"] = run_id
    try:
        final = simulaciones.ejecutar_run(run_id, forzar_error=bool(pedido.get("forzar_error")),
                                          al_avanzar=lambda p: _avance(run_id, p),
                                          guardar_serie=guardar_serie,
                                          descartar_serie=descartar_serie)
    finally:
        estado["corrida_actual"] = None
    estado["procesadas"] += 1
    estado["ultima"] = {"id": run_id, "status": final}
    # None: otro trabajador la tomó o alguien la cerró antes; el aviso no es de este.
    if final:
        avisar(run_id, final, ajustes)
    return final


def ciclo(ajustes, detener):
    estado["activo"] = True
    ultimo_reintento = 0.0
    try:
        while not detener.is_set():
            if series_pendientes and time.monotonic() - ultimo_reintento >= REINTENTO_SERIES:
                ultimo_reintento = time.monotonic()
                reintentar_series()
            try:
                if pendiente:
                    try:
                        reencolar()
                        pendiente.clear()
                    except psycopg2.Error as exc:
                        log.warning("No se pudo reencolar, se reintenta: %s", exc)
                        detener.wait(PAUSA_SIN_REDIS)
                        continue
                crudo = cola.tomar(COLA)
            except RedisNoDisponible:
                detener.wait(PAUSA_SIN_REDIS)
                continue
            if crudo is None:
                continue
            try:
                procesar(crudo, ajustes)
            except Exception:
                log.exception("No se pudo procesar %r de la cola", crudo)
    finally:
        estado["activo"] = False
