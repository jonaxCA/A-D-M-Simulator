import json
import math

from flask import g, request

from epidemia_comun import alcance, cola, llaves
from epidemia_comun.contratos import proyectar
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.redis_compartido import RedisNoDisponible, opcional
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo
from procesamiento import calibracion
from procesamiento.categoria import ESTADO, estado_modelo
from procesamiento.motor import AVISO_SIMULACION, ENGINE_VERSION

from . import datos

# calibrations.run (062): calibrar es una decisión científica, así que también el EPIDEMIOLOGO.
ROLES_LANZAN = ("EPIDEMIOLOGO", "ANALISTA", "ADMINISTRADOR")
# simulations.read, como pareto (D42, D50).
ROLES_LEEN = ROLES_LANZAN + ("INVESTIGADOR", "AUTORIDAD_SANITARIA")
TERMINALES = ("completado", "fallido", "cancelado")
ESTADOS = ("encolado", "ejecutando") + TERMINALES
LIMITE, LIMITE_MAX = 20, 100
# Lo que llega en el cuerpo -> la clave de la configuración de procesamiento.calibracion.
CONFIGURACION = {"samples": "muestras", "seeds": "semillas", "quantile": "cuantil",
                 "sampling_seed": "semilla_muestreo"}
CAMPOS = ("id", "dataset_id", "dataset_code", "dataset_version", "disease_id", "region_id",
          "engine", "engine_version", "method", "method_version", "config", "status", "terminal",
          "attempts", "progress", "error", "requested_by", "requested_by_username", "created_at",
          "started_at", "finished_at")
CAMPOS_LISTADO = ("id", "dataset_id", "dataset_code", "dataset_version", "region_id", "engine",
                  "engine_version", "status", "progress", "requested_by_username", "created_at",
                  "finished_at")
NOTA_AJUSTE = ("La banda p5-p95 junta la incertidumbre de los parámetros (las combinaciones "
               "aceptadas) y el ruido entre semillas. La banda de una corrida (/band) solo tiene "
               "el ruido entre semillas.")
NOTA_ESTADO = ("Calibrar es de este servicio (D50). Declarar un modelo calibrado o validado sigue "
               "siendo un PR revisado, con su evidencia en la ficha del simulador (D39).")


def _invalido(mensaje):
    return ErrorAPI(422, "DATOS_INVALIDOS", mensaje)


def _entero(valor, campo, minimo=1):
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        raise _invalido("%s debe ser un entero." % campo)
    if isinstance(valor, bool) or isinstance(valor, float) or numero < minimo:
        raise _invalido("%s debe ser un entero >= %d." % (campo, minimo))
    return numero


def _numero(valor, campo):
    try:
        numero = float(str(valor).strip())
    except (TypeError, ValueError):
        raise _invalido("%s debe ser un número." % campo)
    if isinstance(valor, bool) or not math.isfinite(numero):
        raise _invalido("%s debe ser un número." % campo)
    return numero


def _configuracion(cuerpo):
    config = dict(calibracion.CONFIGURACION)
    for campo, clave in CONFIGURACION.items():
        if cuerpo.get(campo) not in (None, ""):
            config[clave] = (_numero(cuerpo[campo], campo) if campo == "quantile"
                             else _entero(cuerpo[campo], campo, minimo=0 if campo == "sampling_seed" else 1))
    errores = calibracion.revisa_configuracion(config)
    if errores:
        raise _invalido(" ".join(errores))
    return config


def _conjunto(dataset_id):
    fila = datos.conjunto(dataset_id)
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el conjunto de datos %s." % dataset_id)
    alcance.exige_region(fila["region_id"])
    return fila


def _base(fila):
    base, errores = datos.base(fila)
    puntos = datos.puntos(fila["id"])
    if len(puntos) < calibracion.SEMANAS_MINIMAS:
        errores.append("La serie necesita al menos %d semanas." % calibracion.SEMANAS_MINIMAS)
    if errores:
        raise _invalido(" ".join(errores))
    return base, puntos


def _calibracion(cal_id, con_resultado=False):
    fila = datos.get(entero_positivo(cal_id, "id"), con_resultado)
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la calibración.")
    alcance.exige_region(fila["region_id"])
    return fila


def _completada(cal_id):
    fila = _calibracion(cal_id, con_resultado=True)
    if fila["status"] != "completado":
        raise ErrorAPI(409, "CONFLICTO", "La calibración está en «%s»: su ajuste existe al "
                       "completarse." % fila["status"])
    return fila


def _detalle(fila):
    salida = proyectar(dict(fila, terminal=fila["status"] in TERMINALES), CAMPOS)
    if not salida["terminal"]:
        avance = opcional("calibracion: leer avance",
                          lambda r: r.get(llaves.avance_calibracion(fila["id"])))
        if avance is not None:
            salida["progress"] = int(avance)
    resultado = fila.get("result")
    if resultado:
        salida.update(estimados=resultado["parametros"], perdida=resultado["perdida"],
                      metricas=resultado["metricas"], ventanas=resultado["configuracion"]["ventanas"],
                      huella_configuracion=resultado["huella_configuracion"])
    return salida


def _escenario(fila):
    resultado = fila["result"]
    entrada = calibracion.configuracion_calibrada(resultado)
    r0 = entrada["r0"]
    fuente = ("Calibración n.º %d (D50): %s %s, %s, conjunto %s v%d; mediana y p5-p95 de las "
              "combinaciones aceptadas" % (fila["id"], resultado["metodo"], resultado["version_metodo"],
                                           resultado["engine_version"], fila["dataset_code"],
                                           fila["dataset_version"]))
    return {
        "calibration_id": fila["id"],
        "engine": fila["engine"], "engine_version": fila["engine_version"],
        "escenario": {
            "name": "Calibración n.º %d (%s v%d)" % (fila["id"], fila["dataset_code"],
                                                    fila["dataset_version"]),
            "disease_id": fila["disease_id"], "region_id": fila["region_id"],
            "stratify": True, "age_unknown_policy": datos.POLITICA_EDAD,
            "horizon_days": entrada["horizon_days"],
            "initial_infected": entrada["initial_infected"],
            "notes": "Configuración calibrada contra %s v%d; las intervenciones son las de la "
                     "Jornada Nacional de Sana Distancia (D50)." % (fila["dataset_code"],
                                                                    fila["dataset_version"]),
        },
        "intervenciones": entrada["interventions"],
        "param_overrides": {"r0": {"valor": r0["mediana"], "fuente": fuente, "supuesto": False,
                                   "intervalo": {"min": r0["p5"], "max": r0["p95"], "tipo": "rango"}}},
        "observacion": {"rho": entrada["rho"], "phi": entrada["phi"]},
        "huella_configuracion": resultado["huella_configuracion"],
    }


def registrar(app):
    @app.errorhandler(RedisNoDisponible)
    def redis_caido(exc):
        return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "Redis no está disponible."))

    @app.post("/api/v1/calibrations")
    @requiere_token(roles=ROLES_LANZAN)
    def lanzar():
        cuerpo = diccionario(leer_cuerpo())
        sobran = set(cuerpo) - {"dataset_id", "engine"} - set(CONFIGURACION)
        if sobran:
            raise _invalido("Campos desconocidos: %s." % ", ".join(sorted(sobran)))
        dataset_id = entero_positivo(cuerpo.get("dataset_id"), "dataset_id")
        motor = cuerpo.get("engine") or calibracion.MOTOR
        if motor != calibracion.MOTOR:
            raise _invalido("Solo se calibra %s por ahora (D50)." % calibracion.MOTOR)
        config = _configuracion(cuerpo)
        _base(_conjunto(dataset_id))
        cal_id = datos.crear(dataset_id, motor, ENGINE_VERSION, calibracion.METODO,
                             calibracion.VERSION_METODO, config, g.contexto.user_id,
                             contexto=g.contexto)
        try:
            cola.encolar(llaves.cola_calibraciones(), json.dumps({"id": cal_id}))
        except RedisNoDisponible:
            # Sin entrada en la cola nadie la correría: se cierra en vez de dejarla colgada.
            datos.cancelar(cal_id, contexto=g.contexto)
            raise
        return responder({"id": cal_id, "dataset_id": dataset_id, "engine": motor,
                          "engine_version": ENGINE_VERSION, "method": calibracion.METODO,
                          "method_version": calibracion.VERSION_METODO, "config": config,
                          "status": "encolado"}, "calibracion", estado=202)

    @app.get("/api/v1/calibrations")
    @requiere_token(roles=ROLES_LEEN)
    def listar():
        limite = request.args.get("limit")
        limite = LIMITE if limite is None else entero_positivo(limite, "limit")
        if limite > LIMITE_MAX:
            raise _invalido("limit no puede pasar de %d." % LIMITE_MAX)
        estado = request.args.get("status")
        if estado is not None and estado not in ESTADOS:
            raise _invalido("status debe ser uno de: %s." % ", ".join(ESTADOS))
        dataset = request.args.get("dataset")
        dataset = entero_positivo(dataset, "dataset") if dataset is not None else None
        filas = datos.listar(limite, estado, dataset, alcance.regiones_permitidas())
        return responder({"total": len(filas),
                          "calibraciones": [proyectar(f, CAMPOS_LISTADO) for f in filas]},
                         "calibraciones")

    @app.get("/api/v1/calibrations/state")
    @requiere_token(roles=ROLES_LEEN)
    def estado_de_los_modelos():
        version = request.args.get("engine")
        if version is not None and version not in ESTADO:
            raise _invalido("engine debe ser uno de: %s." % ", ".join(ESTADO))
        enfermedad = request.args.get("disease")
        enfermedad = entero_positivo(enfermedad, "disease") if enfermedad is not None else None
        region = request.args.get("region")
        region = entero_positivo(region, "region") if region is not None else None
        modelos = [estado_modelo(v, enfermedad, region) for v in ([version] if version else ESTADO)]
        return responder({"aviso": AVISO_SIMULACION, "disponible": True,
                          "motores_calibrables": [calibracion.MOTOR], "modelos": modelos,
                          "nota": NOTA_ESTADO}, "estado_calibracion")

    @app.get("/api/v1/calibrations/evaluate")
    @requiere_token(roles=ROLES_LEEN)
    def evaluar():
        fila = _conjunto(entero_positivo(request.args.get("dataset"), "dataset"))
        theta = {p: _numero(request.args.get(p), p) for p in calibracion.PARAMETROS}
        errores = calibracion.revisa_parametros(theta)
        if errores:
            raise _invalido(" ".join(errores))
        base, puntos = _base(fila)
        resultado = calibracion.evaluar(puntos, base, theta)
        return responder({"aviso": AVISO_SIMULACION, "dataset_id": fila["id"],
                          "dataset_code": fila["code"], "dataset_version": fila["version"],
                          **resultado}, "evaluacion")

    @app.get("/api/v1/calibrations/<cal_id>")
    @requiere_token(roles=ROLES_LEEN)
    def consultar(cal_id):
        return responder(_detalle(_calibracion(cal_id, con_resultado=True)), "calibracion")

    @app.post("/api/v1/calibrations/<cal_id>/cancel")
    @requiere_token(roles=ROLES_LANZAN)
    def cancelar(cal_id):
        fila = _calibracion(cal_id)
        if not datos.cancelar(fila["id"], contexto=g.contexto):
            raise ErrorAPI(409, "CONFLICTO", "La calibración está en «%s»: solo se cancela una "
                           "encolada o en ejecución." % (datos.estado(fila["id"]) or fila["status"]))
        return responder({"id": fila["id"], "status": "cancelado"}, "calibracion")

    @app.get("/api/v1/calibrations/<cal_id>/fit")
    @requiere_token(roles=ROLES_LEEN)
    def ajuste(cal_id):
        fila = _completada(cal_id)
        resultado = fila["result"]
        return responder({"calibration_id": fila["id"], "dataset_id": fila["dataset_id"],
                          "dataset_code": fila["dataset_code"],
                          "dataset_version": fila["dataset_version"],
                          "engine_version": resultado["engine_version"],
                          "ventanas": resultado["configuracion"]["ventanas"],
                          "estimados": resultado["parametros"], "metricas": resultado["metricas"],
                          "semanas": resultado["semanas"], "nota": NOTA_AJUSTE}, "ajuste")

    @app.get("/api/v1/calibrations/<cal_id>/scenario")
    @requiere_token(roles=ROLES_LEEN)
    def escenario(cal_id):
        return responder(_escenario(_completada(cal_id)), "escenario_calibrado")
