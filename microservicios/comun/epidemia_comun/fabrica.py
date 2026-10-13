from pathlib import Path
from time import monotonic
from uuid import uuid4


def crear_app(nombre, contrato, registrar_rutas=None):
    from flask import Flask, g, request
    from werkzeug.exceptions import HTTPException
    from redis import Redis
    from .ajustes import cargar_ajustes
    from .errores import ErrorAPI, respuesta_error
    from .formatos import responder

    app = Flask(nombre)
    app.config.update(cargar_ajustes(nombre))
    app.extensions["epidemia_redis"] = Redis.from_url(app.config["REDIS_URL"], socket_timeout=2)

    @app.before_request
    def inicio_peticion():
        g.inicio = monotonic()
        g.correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())

    @app.after_request
    def registro(respuesta):
        ms = round((monotonic() - g.inicio) * 1000, 1) if hasattr(g, "inicio") else 0
        respuesta.headers["X-Correlation-ID"] = getattr(g, "correlation_id", "")
        origen = request.headers.get("Origin")
        permitido = app.config.get("CONSOLE_ORIGIN")
        if permitido and origen == permitido:
            respuesta.headers["Access-Control-Allow-Origin"] = origen
            respuesta.headers["Vary"] = "Origin"
            respuesta.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Correlation-ID"
            respuesta.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        usuario = getattr(g, "usuario", {}).get("sub", "-")
        app.logger.info("%s %s %s %.1fms usuario=%s id=%s", request.method,
                        request.path, respuesta.status_code, ms, usuario,
                        getattr(g, "correlation_id", "-"))
        return respuesta

    @app.errorhandler(ErrorAPI)
    def error_conocido(exc):
        return respuesta_error(exc)

    @app.errorhandler(Exception)
    def error_inesperado(exc):
        if isinstance(exc, HTTPException):
            codigo = "NO_ENCONTRADO" if exc.code == 404 else "DATOS_INVALIDOS"
            return respuesta_error(ErrorAPI(exc.code or 500, codigo, exc.description))
        app.logger.exception("Fallo interno de %s", nombre)
        return respuesta_error(ErrorAPI(500, "ERROR_INTERNO", "Ocurrió un error interno."))

    @app.route("/health")
    def health():
        from backend_web.db import query
        redis_ok, postgres_ok = True, True
        try:
            app.extensions["epidemia_redis"].ping()
        except Exception:
            redis_ok = False
        try:
            query("SELECT 1 AS ok", one=True)
        except Exception:
            postgres_ok = False
        sano = redis_ok and postgres_ok
        return responder({"servicio": nombre, "version": app.config["VERSION_SERVICIO"],
                          "estado": "ok" if sano else "degradado",
                          "postgresql": postgres_ok, "redis": redis_ok}, "salud",
                         estado=200 if sano else 503)

    ruta = Path(contrato)
    @app.route("/openapi.json")
    def openapi():
        from flask import Response
        return Response(ruta.read_bytes(), content_type="application/json")

    @app.route("/docs")
    def swagger():
        from flask import Response
        html = '''<!DOCTYPE html><html lang="es"><head><title>Swagger EPIDEMIA</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"></head>
<body><div id="swagger-ui"></div><script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>window.onload=()=>SwaggerUIBundle({url:'/openapi.json',dom_id:'#swagger-ui'});</script></body></html>'''
        return Response(html, content_type="text/html; charset=utf-8")

    if registrar_rutas:
        registrar_rutas(app)
    return app
