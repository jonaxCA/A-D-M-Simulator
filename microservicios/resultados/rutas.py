"""Servicio resultados: curvas e indicadores de una corrida completada.

Lee lo que guardó el simulador (queries.get_run y get_resultado_run). El
resultado de una corrida completada ya no cambia, así que se guarda en la
caché de Redis; lo que no está completado no entra a la caché.
"""
from backend_web import queries
from epidemia_comun import cache
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo
from procesamiento.motor import AVISO_SIMULACION
from procesamiento.motor.modelo import SIMPLIFICACIONES

# Los mismos roles que la pantalla de detalle de una corrida del monolito.
ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
CACHE_TTL = 300
CAMPOS_CORRIDA = ("id", "scenario_version_id", "scenario_id", "version_number", "scenario_name",
                  "disease_name", "region_name", "seed", "population_size", "horizon_days",
                  "finished_at")


def _resultado(run_id):
    run_id = entero_positivo(run_id, "id")

    def calcular():
        corrida = queries.get_run(run_id)
        if not corrida:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la corrida.")
        if corrida["status"] != "completado":
            raise ErrorAPI(409, "CONFLICTO", "La corrida está en «%s»: solo una completada tiene "
                           "resultados." % corrida["status"])
        guardado = queries.get_resultado_run(run_id)
        if not guardado:
            raise ErrorAPI(404, "NO_ENCONTRADO", "La corrida no tiene resultados guardados.")
        return {"corrida": {c: corrida[c] for c in CAMPOS_CORRIDA},
                "engine_version": guardado["engine_version"],
                "scenario_checksum": guardado["scenario_checksum"],
                "resumen": guardado["resumen"], "serie": guardado["serie"],
                "trazabilidad": guardado["trazabilidad"]}

    return cache.obtener("resultados", "run=%d" % run_id, CACHE_TTL, calcular)


def registrar(app):
    @app.get("/api/v1/runs/<run_id>/results")
    @requiere_token(roles=ROLES)
    def resultado(run_id):
        datos = _resultado(run_id)
        return responder(dict({"aviso": AVISO_SIMULACION, "simplificaciones": SIMPLIFICACIONES},
                              **datos), "resultado")

    @app.get("/api/v1/runs/<run_id>/curves")
    @requiere_token(roles=ROLES)
    def curvas(run_id):
        datos = _resultado(run_id)
        return responder({"aviso": AVISO_SIMULACION, "run_id": datos["corrida"]["id"],
                          "serie": datos["serie"]}, "curvas")

    @app.get("/api/v1/runs/<run_id>/indicators")
    @requiere_token(roles=ROLES)
    def indicadores(run_id):
        datos = _resultado(run_id)
        return responder({"aviso": AVISO_SIMULACION, "run_id": datos["corrida"]["id"],
                          "resumen": datos["resumen"]}, "indicadores")
