from flask import Flask

from backend_web import simulaciones
from backend_web.auth import secreto_jwt

from . import presentacion

from ..config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    # Falla aqui, al arrancar, con un mensaje que dice que falta: no en la
    # primera peticion que necesite firmar algo.
    app.config["SECRET_KEY"] = secreto_jwt()

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
