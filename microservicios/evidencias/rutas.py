"""Servicio evidencias: las fotos (y PDF) de los casos, en el volumen del servicio.

Las sube quien reportó el caso o ADMINISTRADOR; las ven los roles que leen casos,
y solo ADMINISTRADOR las borra. El archivo va tal cual en el cuerpo de la
petición y su tipo lo decide el contenido. Las reglas están en
backend_web.evidencias.
"""
import logging
import os
from pathlib import Path

from flask import Response, g, request

from backend_web import evidencias
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo

log = logging.getLogger("evidencias")

ROLES_SUBEN = ("CAPTURISTA", "ADMINISTRADOR")
# Los mismos que leen casos.
ROLES_LEEN = ("CAPTURISTA", "EPIDEMIOLOGO", "ANALISTA", "ADMINISTRADOR")
ROLES_BORRAN = ("ADMINISTRADOR",)
# Donde el compose monta el volumen; EVIDENCIAS_DIR la cambia.
CARPETA = "/var/lib/epidemia/evidencias"


def carpeta():
    return Path(os.environ.get("EVIDENCIAS_DIR") or CARPETA)


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


def _archivo():
    """El cuerpo de la petición, sin leer más de lo permitido."""
    if request.content_length is not None and request.content_length > evidencias.MAXIMO:
        raise ErrorAPI(413, "DATOS_INVALIDOS", "El archivo pasa de 20 MB.")
    datos = request.stream.read(evidencias.MAXIMO + 1)
    errores = evidencias.valida_archivo(datos)
    if errores:
        raise ErrorAPI(413 if len(datos) > evidencias.MAXIMO else 422, "DATOS_INVALIDOS",
                       " ".join(errores))
    return datos


def registrar(app):
    @app.post("/api/v1/cases/<case_id>/attachments")
    @requiere_token(roles=ROLES_SUBEN)
    def subir(case_id):
        caso = _caso(case_id)
        if caso["reported_by"] != g.contexto.user_id and "ADMINISTRADOR" not in g.usuario.get("roles", []):
            raise ErrorAPI(403, "PERMISO_INSUFICIENTE",
                           "Solo quien reportó el caso o ADMINISTRADOR le adjunta evidencias.")
        fila, creada = evidencias.guardar_evidencia(caso["id"], _archivo(), g.contexto.user_id,
                                                    carpeta(), contexto=g.contexto)
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

    @app.get("/api/v1/attachments/<evidencia_id>/content")
    @requiere_token(roles=ROLES_LEEN)
    def contenido(evidencia_id):
        fila, ruta = evidencias.archivo_de_evidencia(entero_positivo(evidencia_id, "id"), carpeta())
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la evidencia.")
        try:
            datos = ruta.read_bytes()
        except FileNotFoundError:
            log.warning("La evidencia %s no tiene su archivo en %s", fila["id"], ruta)
            raise ErrorAPI(404, "NO_ENCONTRADO", "El archivo de la evidencia no está en el servidor.")
        nombre = "evidencia-%d%s" % (fila["id"], evidencias.EXTENSIONES[fila["mime_type"]])
        return Response(datos, content_type=fila["mime_type"], headers={
            "Content-Disposition": 'inline; filename="%s"' % nombre,
            "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

    @app.delete("/api/v1/attachments/<evidencia_id>")
    @requiere_token(roles=ROLES_BORRAN)
    def borrar(evidencia_id):
        fila = evidencias.borrar_evidencia(entero_positivo(evidencia_id, "id"), carpeta(),
                                           contexto=g.contexto)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la evidencia.")
        return responder(fila, "evidencia")
