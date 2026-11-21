"""Servicio resultados: curvas e indicadores de una corrida completada.

El resumen, la huella y la trazabilidad los lee de simulation_runs (sql.get_run y
get_resultado_run); la serie diaria, de MongoDB (serie.py, D28). Lo de una corrida
completada ya no cambia, así que se guarda en la caché de Redis; lo que no está completado no
entra a la caché. Con MongoDB caído, /indicators sigue respondiendo y lo que lleva la serie
responde 503.
"""
from flask import request

from epidemia_comun import alcance, cache, mongo
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo
from procesamiento.analitica import factor_de_escala, representados
from procesamiento.categoria import categoria
from procesamiento.contrato import CAMPOS_SERIE
from procesamiento.motor import AVISO_SIMULACION
from procesamiento.motores import de_version

from . import datos as sql, serie as series

# Los mismos roles que la pantalla de detalle de una corrida del monolito.
ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR", "INVESTIGADOR", "AUTORIDAD_SANITARIA")
CACHE_TTL = 300
CAMPOS_BANDA = CAMPOS_SERIE[1:]
CAMPOS_CORRIDA = ("id", "scenario_version_id", "scenario_id", "version_number", "scenario_name",
                  "disease_name", "region_name", "seed", "population_size", "horizon_days",
                  "finished_at")
CAMPOS_RESULTADO = ("categoria", "corrida", "engine_version", "scenario_checksum", "resumen",
                    "serie", "trazabilidad", "escala")


def escala(habitantes, agentes, resumen=None):
    datos_escala = factor_de_escala(habitantes, agentes)
    datos_escala["representados"] = representados(resumen, datos_escala) if resumen else {}
    return datos_escala


def _corrida(run_id):
    def calcular():
        corrida = sql.get_run(run_id)
        if not corrida:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la corrida.")
        if corrida["status"] != "completado":
            raise ErrorAPI(409, "CONFLICTO", "La corrida está en «%s»: solo una completada tiene "
                           "resultados." % corrida["status"])
        guardado = sql.get_resultado_run(run_id)
        if not guardado:
            raise ErrorAPI(404, "NO_ENCONTRADO", "La corrida no tiene resultados guardados.")
        return {"region_id": corrida["region_id"],
                "corrida": {c: corrida[c] for c in CAMPOS_CORRIDA},
                "engine_version": guardado["engine_version"],
                "scenario_checksum": guardado["scenario_checksum"],
                "resumen": guardado["resumen"], "trazabilidad": guardado["trazabilidad"],
                # D6: la corrida simula agentes; cuántos habitantes de la región representan.
                "escala": escala(corrida["region_population"], corrida["population_size"],
                                 guardado["resumen"]),
                # D39: exploratoria, predicción o validada, con su motivo.
                "categoria": categoria(guardado["engine_version"], guardado["trazabilidad"],
                                       corrida["disease_id"], corrida["region_id"])}

    # La llave lleva la forma del dato: con D39 se agregó la categoría y con D43, la región.
    datos = cache.obtener("resultados", "run3=%d" % run_id, CACHE_TTL, calcular)
    # El alcance es de quien pregunta: se revisa fuera de la caché, que es de todos.
    alcance.exige_region(datos["region_id"])
    return datos


def _serie(run_id):
    def calcular():
        serie = mongo.requerido("resultados: leer la serie", lambda: series.leer(run_id))
        if not serie:
            raise ErrorAPI(404, "NO_ENCONTRADO", "La corrida no tiene su serie guardada.")
        return serie

    return cache.obtener("resultados", "serie=%d" % run_id, CACHE_TTL, calcular)


def _banda(datos, campo):
    motor = de_version(datos["engine_version"])
    if not motor:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No se reconoce el motor de la corrida.")
    version = datos["corrida"]["scenario_version_id"]
    completadas = sql.get_run_ids_completados(version, datos["engine_version"])
    ids = mongo.requerido("resultados: leer la banda", lambda: series.con_serie(
        version, motor.nombre, completadas))

    def calcular():
        dias = mongo.requerido("resultados: leer la banda", lambda: series.banda(
            version, motor.nombre, campo, ids))
        if not dias:
            raise ErrorAPI(404, "NO_ENCONTRADO", "La versión no tiene series guardadas.")
        return dias

    # La llave lleva las réplicas con serie (completadas y en MongoDB): al terminar otra, la banda se recalcula.
    clave = "banda=%d&%s&%s&n=%d&m=%d" % (version, motor.nombre, campo, len(ids), ids[-1] if ids else 0)
    return motor.nombre, ids, cache.obtener("resultados", clave, CACHE_TTL, calcular)


def registrar(app):
    @app.get("/api/v1/runs/<run_id>/results")
    @requiere_token(roles=ROLES)
    def resultado(run_id):
        run_id = entero_positivo(run_id, "id")
        datos = dict(_corrida(run_id), serie=_serie(run_id))
        # Las simplificaciones son las del motor que produjo el resultado (D2).
        motor = de_version(datos["engine_version"])
        simplificaciones = list(motor.simplificaciones) if motor else []
        return responder(dict({"aviso": AVISO_SIMULACION, "simplificaciones": simplificaciones},
                              **{c: datos[c] for c in CAMPOS_RESULTADO}), "resultado")

    @app.get("/api/v1/runs/<run_id>/curves")
    @requiere_token(roles=ROLES)
    def curvas(run_id):
        run_id = entero_positivo(run_id, "id")
        datos = _corrida(run_id)
        return responder({"aviso": AVISO_SIMULACION, "categoria": datos["categoria"], "run_id": run_id,
                          "serie": _serie(run_id)}, "curvas")

    @app.get("/api/v1/runs/<run_id>/indicators")
    @requiere_token(roles=ROLES)
    def indicadores(run_id):
        run_id = entero_positivo(run_id, "id")
        datos = _corrida(run_id)
        return responder({"aviso": AVISO_SIMULACION, "categoria": datos["categoria"], "run_id": run_id,
                          "resumen": datos["resumen"]}, "indicadores")

    @app.get("/api/v1/runs/<run_id>/band")
    @requiere_token(roles=ROLES)
    def banda(run_id):
        run_id = entero_positivo(run_id, "id")
        campo = request.args.get("campo", "casos_activos")
        if campo not in CAMPOS_BANDA:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "campo debe ser uno de: %s." % ", ".join(CAMPOS_BANDA))
        datos = _corrida(run_id)
        motor, ids, dias = _banda(datos, campo)
        return responder({"aviso": AVISO_SIMULACION, "categoria": datos["categoria"], "run_id": run_id,
                          "scenario_version_id": datos["corrida"]["scenario_version_id"],
                          "motor": motor, "campo": campo, "replicas": len(ids),
                          "metodo": "Mediana y percentiles 5 y 95 por día entre las réplicas completadas "
                                    "de la versión con el mismo motor (D8).",
                          "banda": dias}, "banda")
