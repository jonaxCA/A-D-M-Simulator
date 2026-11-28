"""Arranque de un servicio con waitress: `python -m epidemia_comun.servir microservicios.<x>.app:app`.

Lo usa el CMD de cada Dockerfile. Detrás de nginx (DETRAS_DE_PROXY=1, D25) waitress tiene que
confiar en las cabeceras X-Forwarded-For, -Proto y -Host del proxy: por omisión las borra antes
de que lleguen a la aplicación (clear_untrusted_proxy_headers). Sin ellas, el servicio ve la IP
de nginx en vez de la del cliente, así que los límites por IP de D31 serían uno solo para
todos, y ve http en vez de https.

Con la variable, waitress confía en un solo proxy y aplica esas tres cabeceras; sin ella, no
confía en ninguno, como siempre. Solo se prende cuando los servicios no publican su puerto
(infra/docker-compose.nginx.yml): si alguien pudiera llegar directo, falsearía su IP.
"""
import importlib
import os
import sys

ESCUCHA = "0.0.0.0:8000"
CABECERAS_DEL_PROXY = ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto")


def detras_de_proxy():
    return os.environ.get("DETRAS_DE_PROXY", "").lower() in ("1", "true", "si")


def opciones(escucha=ESCUCHA):
    """Los argumentos de waitress.serve para este proceso."""
    resultado = {"listen": escucha}
    if detras_de_proxy():
        resultado.update(trusted_proxy="*", trusted_proxy_count=1,
                         trusted_proxy_headers=set(CABECERAS_DEL_PROXY))
    return resultado


def servir(app, escucha=ESCUCHA):
    from waitress import serve
    serve(app, **opciones(escucha))


def main(argumentos):
    modulo, _, nombre = argumentos[0].partition(":")
    app = getattr(importlib.import_module(modulo), nombre or "app")
    servir(app, argumentos[1] if len(argumentos) > 1 else ESCUCHA)


if __name__ == "__main__":
    main(sys.argv[1:])
