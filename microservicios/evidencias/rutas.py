"""Servicio evidencias: los archivos en el bucket (D30). Las fotos y PDF de los casos y los
reportes de una comparación (D35).

Las fotos las sube quien reportó el caso; las ven los roles que leen casos, y solo
ADMINISTRADOR las borra. Los reportes los suben ANALISTA y ADMINISTRADOR (reports.upload) y
los ven los roles con reports.read. El archivo va tal cual en el cuerpo de la petición y su
tipo lo decide el contenido. Cada archivo se abre con una URL firmada que vence en minutos
(RNF-D17). Las reglas están en datos.py y reportes.py.
"""
import logging

from flask import Response, g, request

from epidemia_comun import archivos
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo
from . import datos as evidencias
from . import reportes

log = logging.getLogger("evidencias")

# Solo el CAPTURISTA captura, y sus fotos son parte de la captura (D1).
ROLES_SUBEN = ("CAPTURISTA",)
# Los mismos que leen casos.
ROLES_LEEN = ("CAPTURISTA", "EPIDEMIOLOGO", "ANALISTA", "ADMINISTRADOR")
ROLES_BORRAN = ("ADMINISTRADOR",)
# reports.upload (034) y reports.read (010 y 052).
ROLES_SUBEN_REPORTES = ("ANALISTA", "ADMINISTRADOR")
ROLES_LEEN_REPORTES = ("EPIDEMIOLOGO", "ANALISTA", "ADMINISTRADOR", "INVESTIGADOR",
                       "AUTORIDAD_SANITARIA")
# La huella SHA-256 que declara el cliente (RNF-C09); opcional.
CABECERA_HUELLA = "X-Content-SHA256"


def _caso(case_id):
    caso = evidencias.get_caso(entero_positivo(case_id, "case_id"))
    if caso is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el caso.")
    return caso


def _evidencia(evidencia_id):
    fila = evidencias.get_evidencia(entero_positivo(evidencia_id, "id"))
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la evidencia.")
    return fila


def _reporte(reporte_id):
    fila = reportes.get_reporte(entero_positivo(reporte_id, "id"))
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el reporte.")
    return fila


def _archivo(tipos=tuple(evidencias.EXTENSIONES)):
    """El cuerpo de la petición, sin leer más de lo permitido, validado por su contenido, su
    tamaño y su huella (RNF-D27)."""
    if request.content_length is not None and request.content_length > evidencias.MAXIMO:
        raise ErrorAPI(413, "DATOS_INVALIDOS", "El archivo pasa de 20 MB.")
    datos = request.stream.read(evidencias.MAXIMO + 1)
    errores = evidencias.valida_archivo(datos, request.headers.get(CABECERA_HUELLA), tipos)
    if errores:
        raise ErrorAPI(413 if len(datos) > evidencias.MAXIMO else 422, "DATOS_INVALIDOS",
                       " ".join(errores))
    return datos


def _url_firmada(fila_id, objeto, nombre):
    url, vence = archivos.url_firmada(objeto, nombre=nombre)
    respuesta = responder({"id": fila_id, "url": url, "expires_at": vence,
                           "minutes": archivos.MINUTOS}, "url_firmada")
    # La URL es un permiso temporal: que nadie la guarde.
    respuesta.headers["Cache-Control"] = "private, no-store"
    return respuesta


def registrar(app):
    @app.post("/api/v1/cases/<case_id>/attachments")
    @requiere_token(roles=ROLES_SUBEN)
    def subir(case_id):
        caso = _caso(case_id)
        if caso["reported_by"] != g.contexto.user_id:
            raise ErrorAPI(403, "PERMISO_INSUFICIENTE",
                           "Solo quien reportó el caso le adjunta evidencias.")
        fila, creada = evidencias.guardar_evidencia(caso["id"], _archivo(), g.contexto.user_id,
                                                    contexto=g.contexto)
        return responder(fila, "evidencia", estado=201 if creada else 200)

    @app.get("/api/v1/cases/<case_id>/attachments")
    @requiere_token(roles=ROLES_LEEN)
    def listar(case_id):
        caso = _caso(case_id)
        filas = evidencias.listar_evidencias(caso["id"])
        return responder({"case_id": caso["id"], "total": len(filas), "evidencias": filas},
                         "evidencias_caso")

    @app.get("/api/v1/attachments/<evidencia_id>")
    @requiere_token(roles=ROLES_LEEN)
    def consultar(evidencia_id):
        return responder(_evidencia(evidencia_id), "evidencia")

    @app.get("/api/v1/attachments/<evidencia_id>/url")
    @requiere_token(roles=ROLES_LEEN)
    def url_de_evidencia(evidencia_id):
        fila, objeto = evidencias.objeto_de_evidencia(entero_positivo(evidencia_id, "id"))
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la evidencia.")
        nombre = "evidencia-%d%s" % (fila["id"], evidencias.EXTENSIONES[fila["mime_type"]])
        return _url_firmada(fila["id"], objeto, nombre)

    @app.get("/api/v1/attachments/<evidencia_id>/content")
    @requiere_token(roles=ROLES_LEEN)
    def contenido(evidencia_id):
        fila, objeto = evidencias.objeto_de_evidencia(entero_positivo(evidencia_id, "id"))
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la evidencia.")
        try:
            datos = archivos.leer(objeto)
        except FileNotFoundError:
            log.warning("La evidencia %s no tiene su archivo en %s", fila["id"], objeto)
            raise ErrorAPI(404, "NO_ENCONTRADO", "El archivo de la evidencia no está en el bucket.")
        nombre = "evidencia-%d%s" % (fila["id"], evidencias.EXTENSIONES[fila["mime_type"]])
        return Response(datos, content_type=fila["mime_type"], headers={
            "Content-Disposition": 'inline; filename="%s"' % nombre,
            "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

    @app.delete("/api/v1/attachments/<evidencia_id>")
    @requiere_token(roles=ROLES_BORRAN)
    def borrar(evidencia_id):
        fila = evidencias.borrar_evidencia(entero_positivo(evidencia_id, "id"), contexto=g.contexto)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la evidencia.")
        return responder(fila, "evidencia")

    @app.post("/api/v1/reports")
    @requiere_token(roles=ROLES_SUBEN_REPORTES)
    def subir_reporte():
        run_ids, errores = reportes.valida_corridas(request.args.get("runs"))
        titulo, errores_titulo = reportes.valida_titulo(request.args.get("title"))
        if errores or errores_titulo:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores + errores_titulo))
        datos = _archivo(reportes.TIPOS)
        faltan = reportes.corridas_que_faltan(run_ids)
        if faltan:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "No existen las corridas %s." % ", ".join(map(str, faltan)))
        fila, creado = reportes.guardar_reporte(run_ids, datos, titulo, g.contexto.user_id,
                                                contexto=g.contexto)
        return responder(fila, "reporte", estado=201 if creado else 200)

    @app.get("/api/v1/reports")
    @requiere_token(roles=ROLES_LEEN_REPORTES)
    def listar_reportes():
        run_ids = None
        if request.args.get("runs"):
            run_ids, errores = reportes.valida_corridas(request.args.get("runs"))
            if errores:
                raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        filas = reportes.listar_reportes(run_ids)
        return responder({"total": len(filas), "reportes": filas}, "reportes")

    @app.get("/api/v1/reports/<reporte_id>")
    @requiere_token(roles=ROLES_LEEN_REPORTES)
    def consultar_reporte(reporte_id):
        return responder(_reporte(reporte_id), "reporte")

    @app.get("/api/v1/reports/<reporte_id>/url")
    @requiere_token(roles=ROLES_LEEN_REPORTES)
    def url_de_reporte(reporte_id):
        fila, objeto = reportes.objeto_de_reporte(entero_positivo(reporte_id, "id"))
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el reporte.")
        return _url_firmada(fila["id"], objeto, "reporte-%d.pdf" % fila["id"])

    @app.delete("/api/v1/reports/<reporte_id>")
    @requiere_token(roles=ROLES_BORRAN)
    def borrar_reporte(reporte_id):
        fila = reportes.borrar_reporte(entero_positivo(reporte_id, "id"), contexto=g.contexto)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el reporte.")
        return responder(fila, "reporte")
