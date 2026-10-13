# La cola es la única llave sin TTL: la vacía el simulador. Lo que manda es
# PostgreSQL (la corrida queda `encolado`), así que si la cola se pierde se vuelve
# a llenar desde la base.
from .redis_compartido import requerido

ESPERA = 5


def encolar(llave, valor):
    requerido("cola_encolar", lambda r: r.lpush(llave, valor))


def tomar(llave):
    espera = ESPERA
    par = requerido("cola_tomar", lambda r: r.brpop([llave], timeout=espera), espera=espera)
    return par[1] if par else None


def pendientes(llave):
    return requerido("cola_pendientes", lambda r: r.llen(llave))
