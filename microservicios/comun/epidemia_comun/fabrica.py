import json
import os
from pathlib import Path
from time import monotonic
from uuid import uuid4

TTL_ERRORES = 86400


def crear_app(nombre, contrato, registrar_rutas=None, dependencias=()):
    from flask import Flask, g, request
    from werkzeug.exceptions import HTTPException
    from psycopg2 import InterfaceError, OperationalError
    from redis import Redis
    from .ajustes import cargar_ajustes
    from .errores import ErrorAPI, respuesta_error
    from .formatos import responder
    from .archivos import BucketNoDisponible
    from .mongo import MongoNoDisponible
    from . import llaves, redis_compartido, registro, salud

    registro.configurar(nombre)
    app = Flask(nombre)
    app.config.update(cargar_ajustes(nombre))
    app.extensions["epidemia_redis"] = Redis.from_url(app.config["REDIS_URL"], socket_timeout=2)
    # Detrás de nginx (D25): confía en un solo proxy. Sin la variable se ignoran las cabeceras
    # X-Forwarded-*, para que nadie falsee su IP ni el prefijo.
    detras = os.environ.get("DETRAS_DE_PROXY", "").lower() in ("1", "true", "si")
    if detras:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    @app.before_request
    def inicio_peticion():
        g.inicio = monotonic()
        g.correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        # Regla 4 de los contratos: un ?format desconocido es 400 antes de hacer nada, no al
        # responder (E6).
        if request.path.startswith("/api/") and request.args.get("format") not in (None, "json", "xml"):
            raise ErrorAPI(400, "DATOS_INVALIDOS", "El formato debe ser json o xml.")

    @app.after_request
    def registro(respuesta):
        ms = round((monotonic() - g.inicio) * 1000, 1) if hasattr(g, "inicio") else 0
        respuesta.headers["X-Correlation-ID"] = getattr(g, "correlation_id", "")
        origen = request.headers.get("Origin")
        permitido = app.config.get("CONSOLE_ORIGIN")
        if permitido and origen == permitido:
            respuesta.headers["Access-Control-Allow-Origin"] = origen
            respuesta.headers["Vary"] = "Origin"
            # If-Match y ETag: la versión de un caso al corregirlo desde la consola (D47).
            respuesta.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Correlation-ID, If-Match"
            respuesta.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            # Sin esto, el navegador no deja que la consola lea el X-Correlation-ID ni el ETag.
            respuesta.headers["Access-Control-Expose-Headers"] = "X-Correlation-ID, ETag"
        if respuesta.status_code >= 500 and request.path != "/health":
            def contar(r):
                p = r.pipeline()
                p.set(llaves.errores(nombre), 0, nx=True, ex=TTL_ERRORES)
                p.incr(llaves.errores(nombre))
                p.execute()
            redis_compartido.opcional("contador de errores", contar)
        usuario = getattr(g, "usuario", {}).get("sub", "-")
        app.logger.info("%s %s %s %.1fms usuario=%s", request.method,
                        request.path, respuesta.status_code, ms, usuario)
        return respuesta

    @app.errorhandler(ErrorAPI)
    def error_conocido(exc):
        return respuesta_error(exc)

    @app.errorhandler(MongoNoDisponible)
    def mongo_caido(exc):
        app.logger.warning("MongoDB no disponible para %s", nombre)
        return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE",
                                        "MongoDB no está disponible.", {"Retry-After": "5"}))

    @app.errorhandler(BucketNoDisponible)
    def bucket_caido(exc):
        app.logger.warning("El bucket no está disponible para %s: %s", nombre, exc)
        return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE",
                                        "El almacenamiento de archivos no está disponible.",
                                        {"Retry-After": "5"}))

    @app.errorhandler(Exception)
    def error_inesperado(exc):
        if isinstance(exc, HTTPException):
            codigo = "NO_ENCONTRADO" if exc.code == 404 else "DATOS_INVALIDOS"
            return respuesta_error(ErrorAPI(exc.code or 500, codigo, exc.description))
        if isinstance(exc, InterfaceError) or (
                isinstance(exc, OperationalError) and (exc.pgcode or "08").startswith(("08", "57P"))):
            app.logger.warning("PostgreSQL no disponible para %s: %s", nombre, type(exc).__name__)
            return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE",
                                            "La base de datos no está disponible.", {"Retry-After": "5"}))
        app.logger.exception("Fallo interno de %s", nombre)
        return respuesta_error(ErrorAPI(500, "ERROR_INTERNO", "Ocurrió un error interno."))

    @app.route("/health")
    def health():
        from .bd import query

        def ping():
            app.extensions["epidemia_redis"].ping()
            return True

        def sql():
            query("SELECT 1 AS ok", one=True)
            return True

        sano, datos = salud.informe(ping, sql, dependencias)
        return responder(dict({"servicio": nombre, "version": app.config["VERSION_SERVICIO"],
                               "estado": "ok" if sano else "degradado"}, **datos), "salud",
                         estado=200 if sano else 503)

    ruta = Path(contrato)
    @app.route("/openapi.json")
    def openapi():
        from flask import Response
        contenido = ruta.read_bytes()
        if detras:
            contrato_json = json.loads(contenido)
            contrato_json["servers"] = [{"url": request.url_root.rstrip("/")}]
            contenido = json.dumps(contrato_json, ensure_ascii=False).encode("utf-8")
        return Response(contenido, content_type="application/json")

    @app.route("/docs")
    def swagger():
        from flask import Response
        html = '''<!DOCTYPE html><html lang="es"><head><title>Swagger EPIDEMIA</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"></head>
<body><div id="swagger-ui"></div><script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>window.onload=()=>SwaggerUIBundle({url:__URL__,dom_id:'#swagger-ui'});</script></body></html>'''
        url = json.dumps(request.script_root + "/openapi.json")
        for caracter, escapado in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")):
            url = url.replace(caracter, escapado)
        return Response(html.replace("__URL__", url),
                        content_type="text/html; charset=utf-8")

    if registrar_rutas:
        registrar_rutas(app)
    return app
