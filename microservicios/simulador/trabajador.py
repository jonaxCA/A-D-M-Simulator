"""El proceso trabajador: toma corridas de la cola de Redis de su motor y las ejecuta.

Hay un simulador por motor (D2): SIMULADOR_MOTOR dice cuál (seir-ref si no viene) y de qué
cola toma, queue:simulaciones:<motor>. Así uno sin GPU nunca toma una corrida de abm-gpu, y una
corrida larga del ABM no detiene las del SEIR.

La corrida la ejecuta simulaciones.ejecutar_run(), la misma del monolito: marca
'ejecutando' con la transición condicionada (dos trabajadores no corren la
misma), corre el motor, guarda el resultado y audita. Aquí solo se lee la
cola, se publica el avance en Redis y se avisa a notificaciones.
"""
import json
import logging
import os
import socket

from backend_web import queries, simulaciones
from epidemia_comun import cola, llaves
from epidemia_comun.http import llamar
from epidemia_comun.redis_compartido import RedisNoDisponible, opcional
from epidemia_comun.seguridad import token_servicio
from procesamiento.motores import MOTOR_REFERENCIA, del_nombre

log = logging.getLogger("simulador")

PROGRESO_TTL = 86400
PAUSA_SIN_REDIS = 5
AVISOS = {"completado": ("RUN_FINISHED", "La corrida %s terminó"),
          "fallido": ("RUN_FAILED", "La corrida %s falló")}
# Un motor que no está implementado (abm-gpu sin FLAME GPU) detiene el arranque: sin esto, el
# simulador tomaría corridas que no puede correr.
MOTOR = del_nombre((os.environ.get("SIMULADOR_MOTOR") or MOTOR_REFERENCIA).strip()).nombre
COLA = llaves.cola_simulaciones(MOTOR)

# Lo que reporta /api/v1/worker/status. Solo lo escribe el hilo del trabajador.
estado = {"trabajador": socket.gethostname(), "motor": MOTOR, "activo": False,
          "corrida_actual": None, "procesadas": 0, "ultima": None}


def recuperar():
    # Las encoladas no se tocan: siguen esperando en la cola. Y solo las de su motor: las de
    # otro las está corriendo el simulador de ese motor.
    cerradas = simulaciones.recupera_corridas_interrumpidas(estados=("ejecutando",),
                                                           engine=MOTOR)
    if cerradas:
        log.warning("Se cerraron como fallidas %d corridas que quedaron a medias.", cerradas)
    return cerradas


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
                                          al_avanzar=lambda p: _avance(run_id, p))
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
    try:
        while not detener.is_set():
            try:
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
