"""Servicio corridas: lanza, consulta y cancela corridas.

Las reglas son las del monolito (queries.crear_corrida, get_run,
get_runs_recientes) más cancelar_run. La corrida la ejecuta el servicio
simulador, que la toma de la cola de Redis.
"""
import json
import logging
import secrets

from flask import g, request

from backend_web import queries, simulaciones
from epidemia_comun import candados, cola, llaves
from epidemia_comun.candados import CandadoOcupado
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.redis_compartido import RedisNoDisponible, opcional
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo

log = logging.getLogger("corridas")

# Los mismos roles que la pantalla Simulaciones del monolito.
ROLES_EJECUTAN = ("ANALISTA", "ADMINISTRADOR")
ROLES_LEEN = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
# Cancelar es simulations.delete en la matriz de permisos (migración 010).
ROLES_CANCELAN = ("ANALISTA", "ADMINISTRADOR")
# El mismo tope que la semilla del formulario del monolito.
SEMILLA_MAX = 2**31 - 1
LIMITE, LIMITE_MAX = 20, 100
CANDADO_TTL = 10
TERMINALES = ("completado", "fallido", "cancelado")


def _semilla(valor):
    if valor is None or valor == "":
        return secrets.randbelow(SEMILLA_MAX + 1)
    if isinstance(valor, str) and valor.strip().isdigit():
        valor = int(valor)
    if isinstance(valor, bool) or not isinstance(valor, int) or not 0 <= valor <= SEMILLA_MAX:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "seed debe ser un entero de 0 a %d." % SEMILLA_MAX)
    return valor


def _booleano(valor, campo):
    if isinstance(valor, str) and valor.lower() in ("true", "false"):
        valor = valor.lower() == "true"
    if not isinstance(valor, bool):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser true o false." % campo)
    return valor


def _error_al_crear(mensaje):
    if "no existe" in mensaje:
        return ErrorAPI(404, "NO_ENCONTRADO", mensaje)
    if "no está aprobada" in mensaje:
        return ErrorAPI(409, "CONFLICTO", mensaje)
    # El texto de psycopg2 no sale de aquí: puede traer SQL.
    log.warning("crear_corrida falló: %s", mensaje)
    return ErrorAPI(409, "CONFLICTO", "No se pudo crear la corrida; revisa que la versión siga aprobada.")


def _corrida(run_id):
    corrida = queries.get_run(entero_positivo(run_id, "id"))
    if not corrida:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la corrida.")
    return corrida


def registrar(app):
    @app.errorhandler(RedisNoDisponible)
    def redis_caido(exc):
        return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "Redis no está disponible."))

    @app.errorhandler(CandadoOcupado)
    def doble_envio(exc):
        return respuesta_error(ErrorAPI(409, "CONFLICTO",
                                        "Ya se está lanzando una corrida de esta versión; intenta de nuevo."))

    @app.post("/api/v1/runs")
    @requiere_token(roles=ROLES_EJECUTAN)
    def lanzar():
        cuerpo = diccionario(leer_cuerpo())
        version_id = entero_positivo(cuerpo.get("scenario_version_id"), "scenario_version_id")
        semilla = _semilla(cuerpo.get("seed"))
        # Como en el monolito: para otro rol se ignora, no se rechaza.
        forzar = (_booleano(cuerpo.get("forzar_error", False), "forzar_error")
                  and "ADMINISTRADOR" in g.usuario.get("roles", []))
        with candados.candado(llaves.candado_corrida(version_id), ttl=CANDADO_TTL):
            run_id, batch_id, error = queries.crear_corrida(
                version_id, semilla, g.contexto.user_id, simulaciones.ENGINE_VERSION,
                contexto=g.contexto, forzar_error=forzar)
            if error:
                raise _error_al_crear(error)
            try:
                cola.encolar(llaves.COLA_SIMULACIONES,
                             json.dumps({"id": run_id, "forzar_error": forzar}))
            except RedisNoDisponible:
                # Sin entrada en la cola nadie la correría: se cierra en vez de dejarla colgada.
                queries.cancelar_run(run_id, contexto=g.contexto)
                raise
        return responder({"id": run_id, "batch_id": batch_id, "scenario_version_id": version_id,
                          "seed": semilla, "forzar_error": forzar, "status": "encolado"},
                         "corrida", estado=202)

    @app.get("/api/v1/runs")
    @requiere_token(roles=ROLES_LEEN)
    def listar():
        limite = request.args.get("limit")
        limite = LIMITE if limite is None else entero_positivo(limite, "limit")
        if limite > LIMITE_MAX:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "limit no puede pasar de %d." % LIMITE_MAX)
        filas = queries.get_runs_recientes(limite)
        return responder({"total": len(filas), "corridas": filas}, "listado")

    @app.get("/api/v1/runs/<run_id>")
    @requiere_token(roles=ROLES_LEEN)
    def consultar(run_id):
        corrida = _corrida(run_id)
        corrida["terminal"] = corrida["status"] in TERMINALES
        if not corrida["terminal"]:
            # El avance en vivo lo escribe el simulador en Redis; si no está, vale el de la base.
            avance = opcional("progreso_leer", lambda r: r.get(llaves.progreso(corrida["id"])))
            if avance is not None:
                corrida["progress"] = int(avance)
        return responder(corrida, "corrida")

    @app.post("/api/v1/runs/<run_id>/cancel")
    @requiere_token(roles=ROLES_CANCELAN)
    def cancelar(run_id):
        corrida = _corrida(run_id)
        if not queries.cancelar_run(corrida["id"], contexto=g.contexto):
            actual = queries.get_run(corrida["id"]) or corrida
            raise ErrorAPI(409, "CONFLICTO", "La corrida está en «%s»: solo se cancela una encolada."
                           % actual["status"])
        return responder({"id": corrida["id"], "status": "cancelado"}, "corrida")
