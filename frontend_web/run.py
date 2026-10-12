"""Arranque local. Desde la raiz del repositorio:  python -m frontend_web.run

Por omision escucha solo en esta maquina y sin depurador. Para desarrollar:

    FLASK_DEBUG=1          depurador y recarga automatica al guardar
    EPIDEMIA_HOST=0.0.0.0  visible para la red local (p.ej. para probar desde
                           un celular); no se puede combinar con FLASK_DEBUG
    EPIDEMIA_PORT=5001     otro puerto

Se ponen en el .env o en la terminal antes de arrancar.
"""
import os

from backend_web import simulaciones
from frontend_web.app import create_app

HOSTS_LOCALES = {"127.0.0.1", "localhost", "::1"}

app = create_app()


def opciones_arranque(entorno=None):
    """(host, puerto, debug) a partir del entorno.

    El depurador de Werkzeug ejecuta Python arbitrario desde el navegador. Con
    `host="0.0.0.0"` eso queda al alcance de cualquiera en la misma red, asi
    que esa combinacion se rechaza en vez de confiar en que nadie la use.
    """
    entorno = os.environ if entorno is None else entorno
    debug = (entorno.get("FLASK_DEBUG") or "").strip().lower() in ("1", "true", "yes")
    host = (entorno.get("EPIDEMIA_HOST") or "127.0.0.1").strip()
    crudo = (entorno.get("EPIDEMIA_PORT") or "5000").strip()
    try:
        puerto = int(crudo)
    except ValueError:
        raise SystemExit(f"EPIDEMIA_PORT debe ser un numero de puerto, no «{crudo}».")
    if debug and host not in HOSTS_LOCALES:
        raise SystemExit(
            f"FLASK_DEBUG=1 con EPIDEMIA_HOST={host} expondria el depurador de "
            f"Werkzeug (que ejecuta codigo) a toda la red. Usa uno u otro.")
    return host, puerto, debug


if __name__ == "__main__":
    host, puerto, debug = opciones_arranque()
    # Aqui y no en create_app(): ver el docstring de la funcion. Con el
    # recargador de FLASK_DEBUG este bloque corre de nuevo en cada reinicio,
    # que es justo cuando hay corridas huerfanas que cerrar.
    cerradas = simulaciones.recupera_corridas_interrumpidas()
    if cerradas:
        print(f" * {cerradas} corrida(s) interrumpida(s) por un reinicio anterior "
              f"quedaron como FALLIDO; se pueden re-ejecutar con la misma semilla.")
    app.run(host=host, port=puerto, debug=debug)
