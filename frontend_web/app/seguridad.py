"""CSRF en los formularios (RNF-D07) y encabezados de seguridad en cada respuesta (RNF-D21)."""
import hmac
import secrets

from flask import abort, request, session

METODOS_QUE_ESCRIBEN = ("POST", "PUT", "PATCH", "DELETE")

# Las graficas cargan Highcharts de su CDN y las plantillas traen scripts y estilos en linea.
CSP = ("default-src 'self'; "
       "script-src 'self' 'unsafe-inline' https://code.highcharts.com; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; "
       "img-src 'self' data: https:; "
       "connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")

ENCABEZADOS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def registrar(app):
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def revisa_csrf():
        if request.method not in METODOS_QUE_ESCRIBEN:
            return None
        esperado = session.get("csrf")
        recibido = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
        if not esperado or not hmac.compare_digest(esperado, recibido):
            abort(400, "La página venció o el formulario no es de este sitio. Recárgala e intenta de nuevo.")
        return None

    @app.after_request
    def encabezados(respuesta):
        for nombre, valor in ENCABEZADOS.items():
            respuesta.headers.setdefault(nombre, valor)
        if request.is_secure:
            respuesta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if session.get("cuenta"):
            respuesta.headers.setdefault("Cache-Control", "no-store")
        return respuesta
