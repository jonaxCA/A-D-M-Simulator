# El trabajador de calibracion: toma calibraciones de queue:calibraciones y las corre con
# procesamiento.calibracion (D50). La base manda sobre Redis (D19): lo encolado en la base que
# falte en la cola se vuelve a meter, y lo que quedó a medias se reencola hasta 3 intentos (D38).
import json
import logging

import psycopg2

from epidemia_comun import cola, llaves
from epidemia_comun.auditoria import Contexto
from epidemia_comun.redis_compartido import RedisNoDisponible, opcional
from procesamiento import calibracion
from procesamiento.motor import ENGINE_VERSION, ErrorMotor

from . import datos

log = logging.getLogger("calibracion")

AGENTE_SIN_PETICION = "trabajador de calibracion (sin peticion HTTP)"
AVANCE_TTL = 86400
PAUSA_SIN_REDIS = 5
COLA = llaves.cola_calibraciones()

estado = {"activo": False, "calibracion_actual": None, "procesadas": 0, "ultima": None}
pendiente = []


def sin_peticion(user_id):
    return Contexto(user_id, None, AGENTE_SIN_PETICION)


def _en_cola(crudo):
    try:
        pedido = json.loads(crudo)
    except ValueError:
        return None
    return pedido.get("id") if isinstance(pedido, dict) else pedido


def reencolar():
    presentes = {_en_cola(c) for c in cola.contenidos(COLA)}
    faltan = [i for i in datos.encoladas() if i not in presentes]
    for cal_id in faltan:
        cola.encolar(COLA, json.dumps({"id": cal_id}))
    if faltan:
        log.warning("Se volvieron a encolar %d calibraciones encoladas en la base.", len(faltan))
    return len(faltan)


def recuperar():
    reencoladas, cerradas = datos.reencola_interrumpidas(ENGINE_VERSION, sin_peticion)
    if reencoladas:
        log.warning("Se reencolaron %d calibraciones que quedaron a medias.", len(reencoladas))
    if cerradas:
        log.warning("Se cerraron como fallidas %d calibraciones sin intentos.", len(cerradas))
    try:
        reencolar()
    except RedisNoDisponible:
        pendiente.append(True)
        log.warning("Redis no responde: se reintentará reencolar dentro del ciclo.")
    return reencoladas, cerradas


def _avance(cal_id, porcentaje):
    opcional("calibracion: avance",
             lambda r: r.set(llaves.avance_calibracion(cal_id), porcentaje, ex=AVANCE_TTL))


def ejecutar(cal_id):
    cal = datos.get(cal_id)
    if cal is None:
        return None
    contexto = sin_peticion(cal["requested_by"])
    # Si no estaba encolada (otro trabajador la tomó, o se canceló), no es de este.
    if not datos.marcar_ejecutando(cal_id, contexto=contexto):
        return None
    _avance(cal_id, 0)
    try:
        if cal["engine_version"] != ENGINE_VERSION:
            raise ValueError("Se pidió con %s y este trabajador corre %s."
                             % (cal["engine_version"], ENGINE_VERSION))
        base, errores = datos.base(datos.conjunto(cal["dataset_id"]))
        if errores:
            raise ValueError(" ".join(errores))
        resultado = calibracion.calibrar(
            datos.puntos(cal["dataset_id"]), base, cal["config"],
            avance=lambda p: _avance(cal_id, p),
            cancelada=lambda: datos.estado(cal_id) != "ejecutando")
    except calibracion.CalibracionCancelada:
        return "cancelado"
    except (ValueError, ErrorMotor) as exc:
        datos.fallar(cal_id, str(exc), contexto=contexto)
        return "fallido"
    resultado["conjunto"] = {"id": cal["dataset_id"], "code": cal["dataset_code"],
                             "version": cal["dataset_version"]}
    if datos.completar(cal_id, resultado, contexto=contexto):
        _avance(cal_id, 100)
        return "completado"
    return datos.estado(cal_id)


def procesar(crudo):
    cal_id = _en_cola(crudo)
    if not isinstance(cal_id, int):
        log.warning("Se descartó %r de la cola: no es una calibración.", crudo)
        return None
    estado["calibracion_actual"] = cal_id
    try:
        final = ejecutar(cal_id)
    finally:
        estado["calibracion_actual"] = None
    estado["procesadas"] += 1
    estado["ultima"] = {"id": cal_id, "status": final}
    return final


def ciclo(detener):
    estado["activo"] = True
    try:
        while not detener.is_set():
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
                procesar(crudo)
            except Exception:
                log.exception("No se pudo procesar %r de la cola", crudo)
    finally:
        estado["activo"] = False
