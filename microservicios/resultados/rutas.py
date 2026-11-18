"""Servicio resultados: curvas e indicadores de una corrida completada.

El resumen, la huella y la trazabilidad los lee de simulation_runs (queries.get_run y
get_resultado_run); la serie diaria, de MongoDB (series_corridas, D28). Lo de una corrida
completada ya no cambia, así que se guarda en la caché de Redis; lo que no está completado no
entra a la caché. Con MongoDB caído, /indicators sigue respondiendo y lo que lleva la serie
responde 503.
"""
from backend_web import queries, simulaciones
from epidemia_comun import cache, mongo, series_corridas
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo
from procesamiento.motor import AVISO_SIMULACION
from procesamiento.motores import de_version

# Los mismos roles que la pantalla de detalle de una corrida del monolito.
ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
CACHE_TTL = 300
CAMPOS_CORRIDA = ("id", "scenario_version_id", "scenario_id", "version_number", "scenario_name",
                  "disease_name", "region_name", "seed", "population_size", "horizon_days",
                  "finished_at")
CAMPOS_RESULTADO = ("corrida", "engine_version", "scenario_checksum", "resumen", "serie",
                    "trazabilidad", "escala")


def _corrida(run_id):
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
                "resumen": guardado["resumen"], "trazabilidad": guardado["trazabilidad"],
                # D6: la corrida simula agentes; cuántos habitantes de la región representan.
                "escala": simulaciones.escala(corrida["region_population"],
                                              corrida["population_size"], guardado["resumen"])}

    return cache.obtener("resultados", "run=%d" % run_id, CACHE_TTL, calcular)


def _serie(run_id):
    def calcular():
        serie = mongo.requerido("resultados: leer la serie", lambda: series_corridas.leer(run_id))
        if not serie:
            raise ErrorAPI(404, "NO_ENCONTRADO", "La corrida no tiene su serie guardada.")
        return serie

    return cache.obtener("resultados", "serie=%d" % run_id, CACHE_TTL, calcular)


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
        _corrida(run_id)
        return responder({"aviso": AVISO_SIMULACION, "run_id": run_id,
                          "serie": _serie(run_id)}, "curvas")

    @app.get("/api/v1/runs/<run_id>/indicators")
    @requiere_token(roles=ROLES)
    def indicadores(run_id):
        run_id = entero_positivo(run_id, "id")
        return responder({"aviso": AVISO_SIMULACION, "run_id": run_id,
                          "resumen": _corrida(run_id)["resumen"]}, "indicadores")
