from concurrent.futures import ThreadPoolExecutor

from flask import g, request

from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import responder
from epidemia_comun.http import llamar
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import entero_positivo
from procesamiento.motor import AVISO_SIMULACION

from .seleccion import corridas_a_comparar

# Los mismos roles que la pantalla Comparación del monolito (ROLES_LEEN_SIMULACION).
# D42: INVESTIGADOR y AUTORIDAD_SANITARIA leen. El alcance por región (D43) lo aplican resultados y
# pareto, a quienes se reenvía el token de la persona; su 403 sube tal cual.
ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR", "INVESTIGADOR", "AUTORIDAD_SANITARIA")
# El selector del monolito ofrece las 50 corridas completadas más recientes.
MAXIMO = 50
HILOS = 8


METRICAS = (("tasa_ataque", "tasa de ataque (fracción)"), ("pico_casos_activos", "personas simuladas"),
            ("dia_pico", "día"), ("fallecimientos", "personas simuladas"),
            ("costo", "personas-día"), ("costo_pesos", "pesos"))
NOTA_DIFERENCIAS = ("Absoluta: la corrida menos la de referencia, con su signo. Relativa: la absoluta "
                    "entre la de referencia; sin valor si la referencia es cero. Son diferencias "
                    "descriptivas entre corridas simuladas; no recomiendan un escenario.")
NOTA_CONTRAFACTUAL = ("Exploratorio: compara lo que simularon las corridas indicadas, no estima lo que "
                      "habría pasado en la realidad. Las dos corridas pueden diferir en más que la "
                      "intervención; revisa su escenario y versión. No recomienda un escenario.")
NOTA_BANDAS = ("Banda p5 a p95 de los casos activos por día entre las réplicas completadas de la "
               "versión (D8). El pico es el día de mayor mediana. Las bandas se enciman si los "
               "intervalos p5 a p95 de sus picos se cruzan.")


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
                "scenario_version_id": corrida.get("scenario_version_id"),
                "version_number": corrida["version_number"],
                "scenario_name": corrida["scenario_name"], "serie": datos["serie"],
                "engine_version": datos.get("engine_version"),
                "fallecimientos": resumen["fallecimientos"],
                "pico_casos_activos": resumen["pico_casos_activos"],
                "dia_pico": resumen["dia_pico"], "tasa_ataque": resumen["tasa_ataque"]}
    except (TypeError, KeyError, ValueError):
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio resultados respondió algo inesperado.")


def _banda(corrida, token, correlacion):
    respuesta = llamar("resultados", "GET", "/api/v1/runs/%d/band" % corrida["id"], formato="json",
                       token=token, correlation_id=correlacion)
    if respuesta.status_code in (401, 403):
        raise ErrorAPI(respuesta.status_code,
                       "TOKEN_INVALIDO" if respuesta.status_code == 401 else "PERMISO_INSUFICIENTE",
                       "El servicio resultados rechazó la identidad.")
    try:
        datos = respuesta.json() if respuesta.status_code == 200 else None
        if datos["replicas"] < 2 or not datos["banda"]:
            return None
        pico = max(datos["banda"], key=lambda d: d["p50"])
        return {"replicas": datos["replicas"], "pico": {k: pico[k] for k in ("dia", "p5", "p50", "p95")},
                "banda": datos["banda"]}
    except (TypeError, KeyError, ValueError):
        return None


def _costos(ids, token, correlacion):
    try:
        respuesta = llamar("pareto", "GET", "/api/v1/pareto?runs=%s" % ",".join(map(str, ids)),
                           formato="json", token=token, correlation_id=correlacion)
        if respuesta.status_code == 200:
            return {f["id"]: f for f in respuesta.json()["filas"]}, None
        detalle = respuesta.json().get("detail") if respuesta.status_code == 422 else None
        return None, detalle or "El servicio pareto no entregó los costos."
    except (ErrorAPI, TypeError, KeyError, ValueError):
        return None, "El servicio pareto no entregó los costos."


def _metricas(base, otra, costos, claves=("base", "valor")):
    filas = []
    for clave, unidad in METRICAS:
        valores = [(costos or {}).get(c["id"], {}).get(clave) if clave.startswith("costo") else c.get(clave)
                   for c in (base, otra)]
        if None in valores:
            continue
        absoluta = valores[1] - valores[0]
        filas.append({"metrica": clave, "unidad": unidad, claves[0]: valores[0], claves[1]: valores[1],
                      "absoluta": absoluta, "relativa": absoluta / valores[0] if valores[0] else None})
    return filas


def _incertidumbre(corridas, token, correlacion):
    # D8: la banda es de una versión con un motor; /band filtra por el motor de la corrida que se le pide.
    por_banda = {}
    for c in corridas:
        clave = (c.get("scenario_version_id") or ("run", c["id"]), c.get("engine_version"))
        por_banda.setdefault(clave, []).append(c)
    with ThreadPoolExecutor(HILOS) as pool:
        bandas = list(pool.map(lambda g: _banda(g[0], token, correlacion), por_banda.values()))
    con, sin = [], []
    for grupo, banda in zip(por_banda.values(), bandas):
        for c in grupo:
            if banda:
                con.append(dict(banda, id=c["id"], grupo=id(grupo)))
            else:
                sin.append(c["id"])
    # Las corridas de una misma banda no se comparan entre sí: es la misma banda.
    encimadas = [{"corrida_id": a["id"], "contra_id": b["id"]}
                 for i, a in enumerate(con) for b in con[i + 1:]
                 if a["grupo"] != b["grupo"]
                 and max(a["pico"]["p5"], b["pico"]["p5"]) <= min(a["pico"]["p95"], b["pico"]["p95"])]
    for banda in con:
        del banda["grupo"]
    return {"nota": NOTA_BANDAS, "corridas": con, "sin_replicas": sin, "bandas_encimadas": encimadas}


def _id_de(texto, por_id, campo):
    if texto is None:
        return None
    numero = entero_positivo(texto, campo)
    if numero not in por_id:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser una de las corridas de runs." % campo)
    return numero


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
        por_id = {c["id"]: c for c in corridas}
        base = _id_de(request.args.get("base"), por_id, "base") or ids[0]
        sin = _id_de(request.args.get("sin_intervencion"), por_id, "sin_intervencion")
        costos, motivo = _costos(ids, token, correlacion)
        respuesta = {"aviso": AVISO_SIMULACION,
                     "corridas": [{k: v for k, v in c.items() if k != "engine_version"} for c in corridas], "base_id": base,
                     "diferencias": {"nota": NOTA_DIFERENCIAS,
                                     "costos_disponibles": costos is not None,
                                     "costos_motivo": motivo,
                                     "corridas": [{"corrida_id": c["id"], "contra_id": base,
                                                   "metricas": _metricas(por_id[base], c, costos)}
                                                  for c in corridas if c["id"] != base]},
                     "incertidumbre": _incertidumbre(corridas, token, correlacion)}
        if sin:
            respuesta["contrafactual"] = {
                "exploratorio": True, "nota": NOTA_CONTRAFACTUAL, "sin_intervencion_id": sin,
                "corridas": [{"corrida_id": c["id"], "scenario_name": c["scenario_name"],
                              "mismo_escenario": c["scenario_id"] == por_id[sin]["scenario_id"],
                              "metricas": _metricas(por_id[sin], c, costos, ("sin", "con"))}
                             for c in corridas if c["id"] != sin]}
        return responder(respuesta, "comparacion")
