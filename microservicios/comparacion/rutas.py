from concurrent.futures import ThreadPoolExecutor

from flask import g, request

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.http import llamar
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import corridas_a_comparar
from procesamiento.motor import AVISO_SIMULACION

# Los mismos roles que la pantalla Comparación del monolito (ROLES_LEEN_SIMULACION).
ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
# El selector del monolito ofrece las 50 corridas completadas más recientes.
MAXIMO = 50
HILOS = 8


def _pedir(run_id, token, correlacion):
    # Los resultados de una corrida; None si no existe o no ha terminado.
    respuesta = llamar("resultados", "GET", "/api/v1/runs/%d/results" % run_id, formato="json",
                       token=token, correlation_id=correlacion)
    if respuesta.status_code in (404, 409):
        return None
    if respuesta.status_code == 429:
        raise ErrorAPI(429, "LIMITE_EXCEDIDO", "El servicio resultados limitó las consultas; intenta de nuevo.",
                       {"Retry-After": respuesta.headers.get("Retry-After", "60")})
    if respuesta.status_code in (401, 403):
        raise ErrorAPI(respuesta.status_code,
                       "TOKEN_INVALIDO" if respuesta.status_code == 401 else "PERMISO_INSUFICIENTE",
                       "El servicio resultados rechazó la identidad.")
    try:
        datos = respuesta.json() if respuesta.status_code == 200 else None
        resumen, corrida = datos["resumen"], datos["corrida"]
        return {"id": run_id, "scenario_id": corrida["scenario_id"],
                "version_number": corrida["version_number"],
                "scenario_name": corrida["scenario_name"], "serie": datos["serie"],
                "fallecimientos": resumen["fallecimientos"],
                "pico_casos_activos": resumen["pico_casos_activos"],
                "dia_pico": resumen["dia_pico"], "tasa_ataque": resumen["tasa_ataque"]}
    except (TypeError, KeyError, ValueError):
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio resultados respondió algo inesperado.")


def registrar(app):
    @app.get("/api/v1/comparisons")
    @requiere_token(roles=ROLES)
    def comparar():
        ids = corridas_a_comparar(request.args.get("runs"), MAXIMO)
        token = request.headers.get("Authorization", "")[7:].strip()
        correlacion = g.correlation_id
        with ThreadPoolExecutor(HILOS) as pool:
            pedidas = list(pool.map(lambda i: _pedir(i, token, correlacion), ids))
        corridas = [c for c in pedidas if c]
        faltan = [i for i, c in zip(ids, pedidas) if not c]
        if faltan:
            raise ErrorAPI(404, "NO_ENCONTRADO",
                           "No existen, no han terminado o no tienen resultados: %s."
                           % ", ".join(map(str, faltan)))
        return responder({"aviso": AVISO_SIMULACION, "corridas": corridas}, "comparacion")
