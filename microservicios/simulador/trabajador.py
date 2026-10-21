"""El proceso trabajador: toma corridas de la cola de Redis y las ejecuta.

La corrida la ejecuta simulaciones.ejecutar_run(), la misma del monolito: marca
'ejecutando' con la transición condicionada (dos trabajadores no corren la
misma), corre el motor, guarda el resultado y audita. Aquí solo se lee la
cola, se publica el avance en Redis y se avisa a notificaciones.
"""
import json
import logging
import socket

from backend_web import queries, simulaciones
from epidemia_comun import cola, llaves
from epidemia_comun.http import llamar
from epidemia_comun.redis_compartido import RedisNoDisponible, opcional
from epidemia_comun.seguridad import token_servicio

log = logging.getLogger("simulador")

PROGRESO_TTL = 86400
PAUSA_SIN_REDIS = 5
AVISOS = {"completado": ("RUN_FINISHED", "La corrida %s terminó"),
          "fallido": ("RUN_FAILED", "La corrida %s falló")}

# Lo que reporta /api/v1/worker/status. Solo lo escribe el hilo del trabajador.
estado = {"trabajador": socket.gethostname(), "activo": False, "corrida_actual": None,
          "procesadas": 0, "ultima": None}


def recuperar():
    # Las encoladas no se tocan: siguen esperando en la cola.
    cerradas = simulaciones.recupera_corridas_interrumpidas(estados=("ejecutando",))
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
                crudo = cola.tomar(llaves.COLA_SIMULACIONES)
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
