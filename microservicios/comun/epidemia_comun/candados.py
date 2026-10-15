import secrets
from contextlib import contextmanager

from .redis_compartido import opcional, requerido


class CandadoOcupado(Exception):
    codigo = "CONFLICTO"
    http = 409


@contextmanager
def candado(llave, ttl):
    marca = secrets.token_hex(16)
    if not requerido("candado_tomar", lambda r: r.set(llave, marca, nx=True, ex=ttl)):
        raise CandadoOcupado("Otra petición está haciendo lo mismo; intenta de nuevo.")
    try:
        yield
    finally:
        # Solo lo suelta si sigue siendo suyo: si el trabajo tardó más que ttl, el
        # candado ya venció y quizá lo tomó otra petición.
        def soltar(p):
            if p.get(llave) == marca:
                p.multi()
                p.delete(llave)

        # Si Redis no responde al soltarlo, vence solo con su TTL.
        opcional("candado_soltar", lambda r: r.transaction(soltar, llave))
