from http import HTTPStatus


class ErrorAPI(Exception):
    def __init__(self, estado, codigo, detalle):
        self.estado = estado
        self.codigo = codigo
        self.detalle = detalle
        super().__init__(detalle)


def respuesta_error(error):
    from flask import Response, request
    from .formatos import a_xml, a_json, formato_solicitado
    estado = error.estado
    titulo = HTTPStatus(estado).phrase if estado in HTTPStatus._value2member_map_ else "Error"
    datos = {"type": "about:blank", "title": titulo, "status": estado,
             "detail": error.detalle, "codigo": error.codigo,
             "instance": request.path}
    try:
        formato = formato_solicitado(request.args.get("format"), request.headers.get("Accept", ""))
    except ValueError:
        formato = "json"
    cuerpo, tipo = (a_json(datos), "application/problem+json") if formato == "json" else (a_xml(datos, "problem"), "application/problem+xml")
    return Response(cuerpo, status=estado, content_type=tipo + "; charset=utf-8")
