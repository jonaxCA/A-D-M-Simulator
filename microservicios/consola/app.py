import os
from pathlib import Path

from flask import Flask, send_from_directory

from epidemia_comun.formatos import responder

ESTATICO = Path(__file__).resolve().parent / "estatico"
SWAGGER = "https://unpkg.com"

# La página habla con los servicios desde el navegador, en la URL que dé el directorio, así
# que connect-src no se puede cerrar a un solo origen. Los scripts sí: los suyos y Swagger UI.
# form-action 'none': si el JavaScript falla, el formulario de inicio de sesión no puede
# mandar la contraseña en la URL.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' %s" % SWAGGER,
    "style-src 'self' 'unsafe-inline' %s" % SWAGGER,
    "img-src 'self' data: %s" % SWAGGER,
    "connect-src 'self' http: https:",
    "form-action 'none'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
])

app = Flask("consola", static_folder=str(ESTATICO), static_url_path="/estatico")


@app.after_request
def cabeceras(respuesta):
    respuesta.headers["Content-Security-Policy"] = CSP
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    return respuesta


@app.get("/")
def inicio():
    return send_from_directory(ESTATICO, "index.html")


@app.get("/config")
def configuracion():
    # El directorio de estado-servicios, como lo ve el navegador.
    return responder({"directorio": os.environ.get("URL_DIRECTORIO") or "http://localhost:5262"},
                     "configuracion")


@app.get("/health")
def health():
    return responder({"servicio": "consola", "version": os.environ.get("VERSION_SERVICIO") or "0.1.0",
                      "estado": "ok"}, "salud")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5260)
