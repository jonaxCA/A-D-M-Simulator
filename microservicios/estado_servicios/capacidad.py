"""Colas y capacidad de procesamiento por motor (F7).

Cuántas corridas esperan en cada cola (`queue:simulaciones:<motor>`, con `:alta` y `:baja` de
D44) y cuántos simuladores de ese motor están vivos y ocupados. Un simulador está vivo mientras
renueve su latido (`worker:<motor>:<simulador>`, ver microservicios/simulador/trabajador.py); el
de abm-gpu de la PC con GPU (D23) cuenta igual, porque escribe en el mismo Redis por el túnel.
"""
import json
from datetime import datetime, timezone

from epidemia_comun import llaves
from epidemia_comun.redis_compartido import requerido

# Los de procesamiento/contrato.py (D2), que no viene en la imagen de estado-servicios; una
# prueba revisa que coincidan. Un motor aparece aunque no tenga simulador: sus corridas esperan.
MOTORES = ("seir-ref", "abm-ref", "abm-gpu")
# Lo que dura un latido sin renovarse (trabajador.LATIDO_TTL).
LATIDO_SEGUNDOS = 30


def _lee(r):
    colas = [llaves.cola_con_prioridad(m, p) for m in MOTORES for p in llaves.prioridades]
    tubo = r.pipeline(transaction=False)
    for cola in colas:
        tubo.llen(cola)
    largos = dict(zip(colas, tubo.execute()))
    nombres = sorted(r.scan_iter(match=llaves.latido("*", "*"), count=500))
    # Un latido puede vencer entre el SCAN y el MGET: llega como None y no cuenta.
    latidos = [json.loads(v) for v in (r.mget(nombres) if nombres else []) if v]
    return largos, latidos


def _simulador(latido):
    return {"nombre": latido.get("nombre"), "corrida_actual": latido.get("corrida_actual"),
            "procesadas": latido.get("procesadas"), "visto": latido.get("visto")}


def por_motor():
    """Regresa la respuesta de /api/v1/services/capacity. Sin Redis no hay ni colas ni latidos:
    levanta RedisNoDisponible (503)."""
    largos, latidos = requerido("estado-servicios: colas y simuladores", _lee)
    motores = list(MOTORES) + sorted({l.get("motor") for l in latidos} - set(MOTORES) - {None})
    resultado = []
    for motor in motores:
        por_prioridad = {p: int(largos.get(llaves.cola_con_prioridad(motor, p), 0))
                         for p in reversed(llaves.prioridades)}
        simuladores = [_simulador(l) for l in latidos if l.get("motor") == motor]
        ocupados = sum(s["corrida_actual"] is not None for s in simuladores)
        resultado.append({"nombre": motor, "en_cola": sum(por_prioridad.values()),
                          "en_cola_por_prioridad": por_prioridad, "vivos": len(simuladores),
                          "ocupados": ocupados, "libres": len(simuladores) - ocupados,
                          "simuladores": simuladores})
    return {"revisado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "latido_segundos": LATIDO_SEGUNDOS, "motores": resultado}
