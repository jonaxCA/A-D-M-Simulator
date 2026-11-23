# Servicio importacion (D53, RF-B08): importa una serie observada agregada en CSV, JSON o XML, la
# revisa y registra su fuente, su licencia, su corte y su versión. Es la que usa la calibración
# (D50). El archivo va tal cual en el cuerpo y su formato lo dice el Content-Type; los metadatos,
# en la consulta. Las reglas están en lectura.py y la base en datos.py.
import hashlib
from datetime import datetime, timezone

from flask import g, request

from epidemia_comun.alcance import exige_region, regiones_permitidas
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo
from . import datos, lectura

# datasets.upload (061).
ROLES_IMPORTAN = ("EPIDEMIOLOGO", "ANALISTA", "ADMINISTRADOR")
# simulations.read, como pareto y calibracion (D50).
ROLES_LEEN = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR", "INVESTIGADOR", "AUTORIDAD_SANITARIA")


def _archivo():
    if request.mimetype not in lectura.TIPOS:
        raise ErrorAPI(415, "DATOS_INVALIDOS", "Usa Content-Type: text/csv, application/json o application/xml.")
    if request.content_length is not None and request.content_length > lectura.MAX_BYTES:
        raise ErrorAPI(413, "DATOS_INVALIDOS", "El archivo pasa de 2 MB.")
    contenido = request.stream.read(lectura.MAX_BYTES + 1)
    if len(contenido) > lectura.MAX_BYTES:
        raise ErrorAPI(413, "DATOS_INVALIDOS", "El archivo pasa de 2 MB.")
    return contenido


def _revisa():
    # (metadatos, ids, puntos, huella, fallas, resumen) de la petición, sin escribir nada.
    contenido = _archivo()
    filas, fallas_archivo = lectura.lee(contenido, request.mimetype)
    # En UTC: va unas horas adelante de Monterrey, así que nunca rechaza el corte de hoy.
    meta, fallas = lectura.revisa_metadatos(request.args, datetime.now(timezone.utc).date())
    ids = (None, None)
    if meta["disease"] and meta["region"]:
        ids = datos.ids_de(meta["disease"], meta["region"])
        if ids[0] is None:
            fallas.append("No existe la enfermedad %s." % meta["disease"])
        if ids[1] is None:
            fallas.append("No existe la región %s." % meta["region"])
    puntos, resumen = [], None
    if not fallas_archivo:
        puntos, fallas_archivo, resumen = lectura.revisa(filas, meta["period"] or "semana")
    fallas += fallas_archivo
    if resumen and meta["cutoff"] and meta["cutoff"] < resumen["fin"]:
        fallas.append("cutoff es anterior al último periodo de la serie.")
    return meta, ids, puntos, hashlib.sha256(contenido).hexdigest(), fallas[:lectura.MAX_FALLAS], resumen


def _conjunto(dataset_id):
    fila = datos.get(entero_positivo(dataset_id, "id"))
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el conjunto de datos.")
    exige_region(fila["region_id"])
    return fila


def registrar(app):
    @app.post("/api/v1/datasets")
    @requiere_token(roles=ROLES_IMPORTAN)
    def importar():
        meta, ids, puntos, huella, fallas, _ = _revisa()
        if fallas:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(fallas[:10]))
        exige_region(ids[1])
        fila, creado = datos.guardar(meta, ids, puntos, huella, g.contexto.user_id, contexto=g.contexto)
        return responder(fila, "conjunto", estado=201 if creado else 200)

    @app.post("/api/v1/datasets/validate")
    @requiere_token(roles=ROLES_IMPORTAN)
    def validar():
        _, _, _, huella, fallas, resumen = _revisa()
        return responder({"valido": not fallas, "sha256": huella, "fallas": fallas,
                          "resumen": None if fallas else resumen}, "validacion")

    @app.get("/api/v1/datasets")
    @requiere_token(roles=ROLES_LEEN)
    def listar():
        filas = datos.listar(request.args.get("disease"), request.args.get("region"), regiones_permitidas())
        return responder({"total": len(filas), "conjuntos": filas}, "conjuntos")

    @app.get("/api/v1/datasets/<dataset_id>")
    @requiere_token(roles=ROLES_LEEN)
    def consultar(dataset_id):
        return responder(_conjunto(dataset_id), "conjunto")

    @app.get("/api/v1/datasets/<dataset_id>/points")
    @requiere_token(roles=ROLES_LEEN)
    def puntos(dataset_id):
        fila = _conjunto(dataset_id)
        return responder({"dataset_id": fila["id"], "period": fila["period"],
                          "puntos": datos.puntos(fila["id"])}, "serie_observada")
