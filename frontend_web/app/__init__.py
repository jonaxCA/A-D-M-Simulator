import os
import re
from time import monotonic
from uuid import uuid4

from flask import Flask, g, has_request_context, request

from backend_web import servicios, simulaciones
from backend_web.auth import secreto_jwt
from epidemia_comun import registro
from epidemia_comun.servir import detras_de_proxy

from . import presentacion

from ..config import Config

# Un X-Correlation-ID que llega del navegador se acepta solo si es corto y sin caracteres raros:
# va a los registros, y un salto de línea ahí inventaría líneas falsas.
CORRELACION_VALIDA = re.compile(r"[A-Za-z0-9._-]{1,64}")


def navegador_de_la_peticion():
    """Las cabeceras de quien usa la web, para los servicios (D36): su navegador, para la
    bitácora; su IP en X-Forwarded-For, y el X-Correlation-ID de la petición.

    En la nube la web llama a los servicios por la red interna (URL_SERVICIOS), y ellos confían
    en X-Forwarded-For (DETRAS_DE_PROXY=1). Sin ella cada servicio vería la IP de la web, y el
    límite por IP de D31 (el del login, por ejemplo) sería uno solo para todos. La IP es
    request.remote_addr, que el cliente no puede falsear: detrás de nginx la pone waitress con
    la cabecera que nginx sobrescribe. Donde los servicios no confían en proxies, la ignoran.
    Con el mismo X-Correlation-ID, una petición a la web se sigue en los registros de cada
    servicio al que llamó (N6)."""
    if not has_request_context():
        return {}
    cabeceras = {}
    if request.headers.get("User-Agent"):
        cabeceras["User-Agent"] = request.headers["User-Agent"][:255]
    if request.remote_addr:
        cabeceras["X-Forwarded-For"] = request.remote_addr
    if getattr(g, "correlation_id", None):
        cabeceras["X-Correlation-ID"] = g.correlation_id
    return cabeceras


def registra_peticiones(app):
    """Cada petición deja una línea en el registro, con el formato de los servicios
    (epidemia_comun.registro): fecha, «web», nivel, X-Correlation-ID, método, ruta, estado y
    tiempo. En la nube van a Cloud Logging (N6)."""
    registro.configurar("web")

    @app.before_request
    def inicio_peticion():
        g.inicio = monotonic()
        recibida = request.headers.get("X-Correlation-ID") or ""
        g.correlation_id = recibida if CORRELACION_VALIDA.fullmatch(recibida) else str(uuid4())

    @app.after_request
    def fin_peticion(respuesta):
        ms = round((monotonic() - g.inicio) * 1000, 1) if hasattr(g, "inicio") else 0
        respuesta.headers["X-Correlation-ID"] = getattr(g, "correlation_id", "")
        app.logger.info("%s %s %s %.1fms", request.method, request.path,
                        respuesta.status_code, ms)
        return respuesta


def create_app():
    servicios.cabeceras_de_la_persona = navegador_de_la_peticion
    app = Flask(__name__)
    app.config.from_object(Config)
    # Falla aqui, al arrancar, con un mensaje que dice que falta: no en la
    # primera peticion que necesite firmar algo. Con D36 la web ya no firma JWT; su cookie usa
    # SECRET_KEY y, mientras no lo haya, JWT_SECRET_KEY (que secreto_jwt revisa).
    app.config["SECRET_KEY"] = (os.environ.get("SECRET_KEY") or "").strip() or secreto_jwt()
    # Detrás de nginx todo llega por HTTPS: la cookie de Flask solo viaja cifrada.
    app.config["SESSION_COOKIE_SECURE"] = detras_de_proxy()
    registra_peticiones(app)

    from .routes import bp
    app.register_blueprint(bp)

    # Identificadores visibles (SIM-00042 / ESC-003): se filtran aqui para
    # poder usarlos en CUALQUIER plantilla con `run.id | id_sim` o
    # `scenario_id | id_esc`, sin repetir el formato f-string en cada .html.
    app.jinja_env.filters["id_sim"] = simulaciones.id_simulacion
    app.jinja_env.filters["id_esc"] = simulaciones.id_escenario
    app.jinja_env.filters["estado_sim"] = simulaciones.estado_visible
    app.jinja_env.filters["badge_sim"] = simulaciones.clase_badge_estado
    app.jinja_env.filters["fecha_corta"] = presentacion.fecha_corta
    app.jinja_env.filters["fecha_hora"] = presentacion.fecha_hora
    app.jinja_env.filters["tendencia_etiqueta"] = presentacion.tendencia_etiqueta
    app.jinja_env.filters["estado_version"] = presentacion.estado_version
    app.jinja_env.filters["actividad_etiqueta"] = presentacion.actividad_etiqueta
    app.jinja_env.filters["estado_catalogo"] = presentacion.estado_catalogo
    app.jinja_env.filters["valor_parametro"] = presentacion.valor_parametro
    app.jinja_env.filters["texto_informativo"] = presentacion.texto_informativo
    app.jinja_env.filters["fuente_etiqueta"] = presentacion.fuente_etiqueta
    app.jinja_env.filters["fuente_detalle"] = presentacion.fuente_detalle
    app.jinja_env.filters["estado_usuario"] = presentacion.estado_usuario

    return app
