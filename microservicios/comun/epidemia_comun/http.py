import os
from urllib.parse import urljoin

import requests

from .errores import ErrorAPI


def llamar(servicio, metodo, ruta, formato="json", cuerpo=None, token=None,
           correlation_id=None, timeout=5, urls=None):
    """Llama a otro servicio sin reintentar escrituras automáticamente."""
    if formato not in ("json", "xml"):
        raise ValueError("El formato debe ser json o xml.")
    if not ruta.startswith("/") or ruta.startswith("//"):
        raise ValueError("La ruta debe comenzar con /.")
    urls = urls or {}
    base = urls.get(servicio) or os.environ.get("SERVICIO_" + servicio.upper().replace("-", "_") + "_URL")
    if not base:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "No se configuró el servicio solicitado.")
    encabezados = {"Accept": "application/" + formato}
    # Conserva la identidad y la correlación de la petición actual.
    try:
        from flask import has_request_context, g, request
        if has_request_context():
            if token is None:
                original = request.headers.get("Authorization", "")
                if original.startswith("Bearer "):
                    token = original[7:].strip()
            if correlation_id is None:
                correlation_id = getattr(g, "correlation_id", None)
    except ImportError:
        pass
    if token:
        encabezados["Authorization"] = "Bearer " + token
    if correlation_id:
        encabezados["X-Correlation-ID"] = correlation_id
    argumentos = {"headers": encabezados, "timeout": timeout}
    if cuerpo is not None:
        if formato == "json":
            argumentos["json"] = cuerpo
        else:
            from .formatos import a_xml
            argumentos["data"] = a_xml(cuerpo, "solicitud")
            encabezados["Content-Type"] = "application/xml"
    try:
        respuesta = requests.request(metodo.upper(), urljoin(base.rstrip("/") + "/", ruta.lstrip("/")), **argumentos)
    except requests.RequestException as exc:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio no respondió.") from exc
    return respuesta
