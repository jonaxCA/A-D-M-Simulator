"""Arranque de la web con waitress, en su contenedor: python -m frontend_web.servir.

Detrás de nginx (DETRAS_DE_PROXY=1, D25) confía en un solo proxy y en sus cabeceras
X-Forwarded-For, -Proto y -Host; sin la variable, en ninguno.
"""
from waitress import serve

from frontend_web.app import detras_de_proxy
from frontend_web.run import app

if __name__ == "__main__":
    opciones = {"listen": "0.0.0.0:8000"}
    if detras_de_proxy():
        opciones.update(trusted_proxy="*", trusted_proxy_count=1,
                        trusted_proxy_headers={"x-forwarded-for", "x-forwarded-host", "x-forwarded-proto"})
    serve(app, **opciones)
