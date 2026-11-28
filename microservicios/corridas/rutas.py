"""Servicio corridas: lanza, consulta y cancela corridas.

Las reglas son las del monolito (datos.crear_corrida, get_run,
get_runs_recientes) más cancelar_run y get_motor_run. La corrida la ejecuta el
simulador de su motor, que la toma de la cola de Redis de ese motor.
"""
import json
import logging
import os
import secrets

from flask import g, request

from epidemia_comun import alcance, candados, cola, llaves
from epidemia_comun.candados import CandadoOcupado
from epidemia_comun.contratos import proyectar
from epidemia_comun.bd import query
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.redis_compartido import RedisNoDisponible, opcional
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo, fecha
from procesamiento.motores import IMPLEMENTADOS

from . import datos

log = logging.getLogger("corridas")

# Lo que dice el contrato; la fila de la base trae más (region_population, requested_by...).
CAMPOS_CORRIDA = (
    'id', 'batch_id', 'scenario_version_id', 'seed', 'status', 'progress', 'engine_version',
    'queued_at', 'started_at', 'finished_at', 'error_message', 'requested_by',
    'version_number', 'scenario_id', 'version_status', 'population_size', 'horizon_days',
    'initial_infected', 'scenario_name', 'disease_id', 'disease_name', 'region_id',
    'region_name', 'requested_by_username', 'requested_by_nombre', 'engine', 'terminal',
    'priority', 'queue_position', 'estimated_seconds', 'estimate_samples',
    'estimate_reason',
)
CAMPOS_LISTADO = (
    'id', 'status', 'seed', 'engine', 'engine_version', 'queued_at', 'started_at',
    'finished_at', 'error_message', 'scenario_version_id', 'scenario_id', 'version_number',
    'horizon_days',
    'scenario_name', 'requested_by_username', 'disease_name', 'region_name',
)

# Los mismos roles que la pantalla Simulaciones del monolito.
ROLES_EJECUTAN = ("ANALISTA", "ADMINISTRADOR")
# D42: INVESTIGADOR y AUTORIDAD_SANITARIA leen (simulations.read).
ROLES_LEEN = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR", "INVESTIGADOR", "AUTORIDAD_SANITARIA")
# Cancelar es simulations.delete en la matriz de permisos (migración 010).
ROLES_CANCELAN = ("ANALISTA", "ADMINISTRADOR")
# Reintentar una fallida vuelve a encolarla: es simulations.run. La prioridad alta (D44) solo la
# pide el ADMINISTRADOR; baja y normal, cualquiera que lance.
PRIORIDAD_ALTA = "ADMINISTRADOR"
# El mismo tope que la semilla del formulario del monolito.
SEMILLA_MAX = 2**31 - 1
LIMITE, LIMITE_MAX = 20, 100
# D8: tope de réplicas de un lote (migración 036). Cada POST crea una corrida; replicas es el
# tamaño del lote que el cliente está lanzando y aquí solo se valida.
REPLICAS_MAX = 100
CANDADO_TTL = 10
TERMINALES = ("completado", "fallido", "cancelado")
ESTADOS = ("encolado", "ejecutando") + TERMINALES
# Los que acepta la base (ck_simulation_batches_engine, migración 035). seir-ref siempre;
# los demás solo si MOTORES_HABILITADOS los nombra: sin un simulador de ese motor desplegado,
# la corrida se quedaría encolada para siempre.
MOTORES = ("seir-ref", "abm-ref", "abm-gpu")
MOTOR_REFERENCIA = "seir-ref"
# Los nombres de antes de D2. La v1 los sigue aceptando en lo que manda el cliente (el cuerpo
# de POST /runs y el filtro engine) y en MOTORES_HABILITADOS, y los traduce; las respuestas ya
# usan los nuevos.
NOMBRES_ANTERIORES = {"python-ref": "seir-ref", "numba": "abm-ref", "cuda": "abm-gpu"}


def nombre_actual(motor):
    return NOMBRES_ANTERIORES.get(motor, motor) if isinstance(motor, str) else motor


def motores_habilitados():
    nombrados = {nombre_actual(m.strip())
                 for m in (os.environ.get("MOTORES_HABILITADOS") or "").split(",")}
    return [m for m in MOTORES if m == MOTOR_REFERENCIA or m in nombrados]


def _motor(valor):
    if valor is None or valor == "":
        return MOTOR_REFERENCIA
    valor = nombre_actual(valor)
    habilitados = motores_habilitados()
    if valor not in habilitados:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "engine debe ser uno de: %s." % ", ".join(habilitados))
    return valor


def _filtros():
    """Los filtros de la lista. engine acepta los tres motores, habilitados o no: una corrida
    vieja de un motor que hoy está apagado se sigue pudiendo buscar."""
    filtros = {}
    for nombre in ("scenario_id", "scenario_version_id"):
        if nombre in request.args:
            filtros[nombre] = entero_positivo(request.args[nombre], nombre)
    for nombre, validos in (("status", ESTADOS), ("engine", MOTORES)):
        valor = request.args.get(nombre)
        if nombre == "engine":
            valor = nombre_actual(valor)
        if valor is not None:
            if valor not in validos:
                raise ErrorAPI(422, "DATOS_INVALIDOS",
                               "%s debe ser uno de: %s." % (nombre, ", ".join(validos)))
            filtros[nombre] = valor
    for nombre, clave in (("from", "desde"), ("to", "hasta")):
        if nombre in request.args:
            filtros[clave] = fecha(request.args[nombre], nombre)
    if filtros.get("desde") and filtros.get("hasta") and filtros["desde"] > filtros["hasta"]:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "from no puede ser posterior a to.")
    return filtros


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


def _prioridad(valor):
    if valor is None or valor == "":
        return "normal"
    if valor not in datos.PRIORIDADES:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "priority debe ser uno de: %s." % ", ".join(datos.PRIORIDADES))
    if valor == "alta" and PRIORIDAD_ALTA not in g.usuario.get("roles", []):
        raise ErrorAPI(403, "PERMISO_INSUFICIENTE", "Solo el ADMINISTRADOR pide prioridad alta.")
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
    corrida = datos.get_run(entero_positivo(run_id, "id"))
    if not corrida:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la corrida.")
    alcance.exige_region(corrida["region_id"])
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
        motor = _motor(cuerpo.get("engine"))
        prioridad = _prioridad(cuerpo.get("priority"))
        if "replicas" in cuerpo and entero_positivo(cuerpo["replicas"], "replicas") > REPLICAS_MAX:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "replicas no puede pasar de %d." % REPLICAS_MAX)
        # Como en el monolito: para otro rol se ignora, no se rechaza.
        forzar = (_booleano(cuerpo.get("forzar_error", False), "forzar_error")
                  and "ADMINISTRADOR" in g.usuario.get("roles", []))
        alcance.exige_region_de(lambda: datos.region_de_version(version_id))
        with candados.candado(llaves.candado_corrida(version_id), ttl=CANDADO_TTL):
            # La versión del motor sale del registro de procesamiento/motores.py. Está aunque el
            # motor no corra aquí: corridas no necesita GPU para encolar una de abm-gpu.
            run_id, batch_id, error = datos.crear_corrida(
                version_id, semilla, g.contexto.user_id,
                IMPLEMENTADOS[motor].version if motor in IMPLEMENTADOS else None,
                engine=motor, contexto=g.contexto, forzar_error=forzar,
                prioridad=prioridad)
            if error:
                raise _error_al_crear(error)
            try:
                cola.encolar(llaves.cola_con_prioridad(motor, prioridad),
                             json.dumps({"id": run_id, "forzar_error": forzar}))
            except RedisNoDisponible:
                # Sin entrada en la cola nadie la correría: se cierra en vez de dejarla colgada.
                datos.cancelar_run(run_id, contexto=g.contexto)
                raise
        return responder({"id": run_id, "batch_id": batch_id, "scenario_version_id": version_id,
                          "seed": semilla, "engine": motor, "forzar_error": forzar,
                          "priority": prioridad, "status": "encolado"},
                         "corrida", estado=202)

    @app.get("/api/v1/runs")
    @requiere_token(roles=ROLES_LEEN)
    def listar():
        limite = request.args.get("limit")
        limite = LIMITE if limite is None else entero_positivo(limite, "limit")
        if limite > LIMITE_MAX:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "limit no puede pasar de %d." % LIMITE_MAX)
        filtros = _filtros()
        regiones = alcance.regiones_permitidas()
        if regiones is not None:
            filtros["regiones"] = sorted(regiones)
        filas = datos.get_runs_recientes(limite, **filtros)
        return responder({"total": len(filas),
                          "corridas": [proyectar(f, CAMPOS_LISTADO) for f in filas]}, "listado")

    # Los motores que este despliegue acepta en POST /runs (RF-E15): los clientes ofrecen solo estos.
    @app.get("/api/v1/runs/engines")
    @requiere_token(roles=ROLES_LEEN)
    def motores():
        habilitados = motores_habilitados()
        return responder({"total": len(habilitados), "referencia": MOTOR_REFERENCIA, "motores": habilitados},
                         "motores")

    @app.get("/api/v1/runs/<run_id>")
    @requiere_token(roles=ROLES_LEEN)
    def consultar(run_id):
        corrida = _corrida(run_id)
        corrida["engine"] = datos.get_motor_run(corrida["id"])
        corrida["terminal"] = corrida["status"] in TERMINALES
        corrida.update(datos.estimar_corrida(corrida["id"]))
        if not corrida["terminal"]:
            # El avance en vivo lo escribe el simulador en Redis; si no está, vale el de la base.
            avance = opcional("progreso_leer", lambda r: r.get(llaves.progreso(corrida["id"])))
            if avance is not None:
                corrida["progress"] = int(avance)
        return responder(proyectar(corrida, CAMPOS_CORRIDA), "corrida")

    # La demostración de reproducibilidad: otra corrida completada con la misma versión, la misma
    # semilla y la misma huella del escenario. Si existe, su resumen debe ser idéntico.
    @app.get("/api/v1/runs/<run_id>/equivalent")
    @requiere_token(roles=ROLES_LEEN)
    def equivalente(run_id):
        corrida = query("""SELECT r.id, r.scenario_version_id, r.seed, r.scenario_checksum, s.region_id
                           FROM simulation_runs r
                           JOIN scenario_versions sv ON sv.id = r.scenario_version_id
                           JOIN scenarios s ON s.id = sv.scenario_id
                           WHERE r.id = %s""",
                        (entero_positivo(run_id, "id"),), one=True)
        if corrida is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la corrida.")
        alcance.exige_region(corrida["region_id"])
        otra = None
        if corrida["scenario_checksum"]:
            otra = query("""SELECT id, resumen FROM simulation_runs
                            WHERE scenario_version_id = %s AND seed = %s AND id <> %s
                              AND scenario_checksum = %s AND status = 'completado'
                            ORDER BY finished_at ASC LIMIT 1""",
                         (corrida["scenario_version_id"], corrida["seed"], corrida["id"],
                          corrida["scenario_checksum"]), one=True)
        return responder({"run_id": corrida["id"], "scenario_version_id": corrida["scenario_version_id"],
                          "seed": corrida["seed"], "scenario_checksum": corrida["scenario_checksum"],
                          "equivalente": dict(otra) if otra else None}, "equivalencia")

    @app.post("/api/v1/runs/<run_id>/cancel")
    @requiere_token(roles=ROLES_CANCELAN)
    def cancelar(run_id):
        corrida = _corrida(run_id)
        if not datos.cancelar_run(corrida["id"], contexto=g.contexto):
            actual = datos.get_run(corrida["id"]) or corrida
            raise ErrorAPI(409, "CONFLICTO", "La corrida está en «%s»: solo se cancela una encolada."
                           % actual["status"])
        return responder({"id": corrida["id"], "status": "cancelado"}, "corrida")

    @app.post("/api/v1/runs/<run_id>/retry")
    @requiere_token(roles=ROLES_EJECUTAN)
    def reintentar(run_id):
        corrida = _corrida(run_id)
        # D44: solo el ADMINISTRADOR conserva la prioridad alta; para otro rol baja a normal.
        prioridad = datos.reintentar_run(corrida["id"], contexto=g.contexto,
                                         puede_alta=PRIORIDAD_ALTA in g.usuario.get("roles", []))
        if prioridad is None:
            actual = datos.get_run(corrida["id"]) or corrida
            raise ErrorAPI(409, "CONFLICTO", "La corrida está en «%s»: solo se reintenta una fallida."
                           % actual["status"])
        # Si Redis no responde, la corrida ya está encolada en la base y el simulador la mete a su
        # cola al recuperar la conexión (D19): se responde 202, que es lo que quedó guardado.
        try:
            cola.encolar(llaves.cola_con_prioridad(datos.get_motor_run(corrida["id"]), prioridad),
                         json.dumps({"id": corrida["id"]}))
        except RedisNoDisponible:
            log.warning("reintento de la corrida %d sin Redis; la reencola el simulador (D19)", corrida["id"])
        return responder({"id": corrida["id"], "seed": corrida["seed"], "priority": prioridad,
                          "status": "encolado"}, "corrida", estado=202)
