# Cada motor tiene una cola por prioridad. Las colas son las únicas llaves sin TTL: las vacía el
# simulador. Lo que manda es PostgreSQL (la corrida queda `encolado`), así que si la cola se pierde se vuelve
# a llenar desde la base.
from .redis_compartido import requerido

ESPERA = 5


def encolar(llave, valor):
    requerido("cola_encolar", lambda r: r.lpush(llave, valor))


def _lista(llaves):
    return [llaves] if isinstance(llaves, str) else list(llaves)


# BRPOP revisa las llaves en el orden dado: con la de mayor prioridad primero, esa se vacía antes.
def tomar(llaves):
    espera = ESPERA
    par = requerido("cola_tomar", lambda r: r.brpop(_lista(llaves), timeout=espera), espera=espera)
    return par[1] if par else None


def pendientes(llaves):
    return requerido("cola_pendientes", lambda r: sum(r.llen(k) for k in _lista(llaves)))


def contenidos(llaves):
    return requerido("cola_contenidos",
                     lambda r: [x for k in _lista(llaves) for x in r.lrange(k, 0, -1)])
