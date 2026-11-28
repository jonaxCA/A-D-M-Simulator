# Servicio validacion: revisa un escenario contra el motor sin guardar nada. Sus reglas viven en
# reglas.py (E8); las de cada intervención se las pide a intervenciones (D37), y el motor
# (procesamiento.motor) dice lo que solo él sabe. Un resultado «no válido» no es un error HTTP: la
# respuesta es el dictamen ({valido, errores, avisos, datos}). Un 4xx/5xx solo significa que la
# petición misma está mal, que no hay permiso o que la versión no existe.
#
# POST /validate/version revisa una versión nueva de un escenario que ya existe; escenarios la pide
# antes de guardarla. GET /versions/{id}/validation da además la huella de la entrada del motor
# (huella.py, D55), con la que aprobacion firma la versión que aprueba.
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.http import llamar
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo
from procesamiento.entrada_motor import escenario_para_motor, intervenciones_para_motor
from procesamiento.motor.parametros import EscenarioInvalido, resolver

from . import datos as bd
from . import huella
from .reglas import revisa_version, valida_escenario, valida_version

ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")

# Los nombres son los campos del formulario del monolito (valida_escenario).
CAMPOS_ESCALARES = ("name", "description", "disease_id", "region_id", "population_size",
                    "initial_infected", "horizon_days", "age_unknown_policy", "notes")
CAMPOS_VERSION = ("population_size", "initial_infected", "horizon_days", "age_unknown_policy", "notes")
CONOCIDOS = set(CAMPOS_ESCALARES) | {"estratificar", "population_by_age", "interventions"}


def avisos_de_ajustes(detalle):
    # Un aviso por parámetro que la versión cambia del catálogo (044, D59): lo que ve quien revisa.
    catalogo = (detalle.get("escenario") or {}).get("default_params") or {}
    ajustes = ((detalle.get("version") or {}).get("param_overrides")) or {}
    avisos = []
    for clave, ajuste in sorted(ajustes.items()):
        base = catalogo.get(clave)
        base = base.get("valor") if isinstance(base, dict) else None
        respaldo = "supuesto" if ajuste.get("supuesto") else "fuente: %s" % ajuste.get("fuente")
        avisos.append("El parámetro %s se ajustó en esta versión: catálogo %s, versión %s (%s)."
                      % (clave, "sin dato" if base is None else base, ajuste.get("valor"), respaldo))
    return avisos


def _es_verdadero(valor):
    if isinstance(valor, bool):
        return valor
    return isinstance(valor, str) and valor.strip().lower() in ("true", "1", "si", "sí")


def _escalar(valor, campo):
    if isinstance(valor, (dict, list)):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El campo %s debe ser un valor simple." % campo)
    # Los validadores del monolito leen texto de formulario: .strip() sobre un int falla.
    return str(valor).lower() if isinstance(valor, bool) else str(valor)


def _lista(valor, campo):
    """JSON trae una lista; XML trae '' (vacía), un dict (un solo hijo) o una lista."""
    if valor is None or valor == "":
        return []
    if isinstance(valor, dict):
        if len(valor) == 1 and isinstance(next(iter(valor.values())), (dict, list)):
            valor = next(iter(valor.values()))
        else:
            return [valor]
    if isinstance(valor, dict):
        return [valor]
    if not isinstance(valor, list):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El campo %s debe ser una lista." % campo)
    return valor


def _formulario(cuerpo):
    """Cuerpo JSON/XML -> el `form` que espera valida_escenario, más los avisos."""
    avisos = ["Se ignoró el campo «%s»: no es parte de la solicitud." % c
              for c in sorted(set(cuerpo) - CONOCIDOS)]
    form = {c: _escalar(cuerpo[c], c) for c in CAMPOS_ESCALARES if cuerpo.get(c) is not None}
    reparto = cuerpo.get("population_by_age")
    if reparto in (None, ""):
        reparto = None
    elif not isinstance(reparto, dict):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "population_by_age debe ser un objeto grupo -> personas.")
    # Mandar el reparto por edad equivale a estratificar.
    form["estratificar"] = _es_verdadero(cuerpo.get("estratificar")) or reparto is not None
    return form, reparto, avisos


def _intervenciones(crudas, horizonte):
    # Las reglas de una intervención son de intervenciones (D37): se le piden por HTTP, con el
    # token de la persona. Solo si el escenario trae intervenciones.
    respuesta = llamar("intervenciones", "POST", "/api/v1/interventions/validate", formato="json",
                       cuerpo={"horizon_days": horizonte, "interventions": crudas})
    if respuesta.status_code >= 500:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio intervenciones no pudo responder.")
    try:
        dictamen = respuesta.json()
    except ValueError:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio intervenciones respondió algo ilegible.")
    if respuesta.status_code in (401, 403):
        raise ErrorAPI(respuesta.status_code,
                       "TOKEN_INVALIDO" if respuesta.status_code == 401 else "PERMISO_INSUFICIENTE",
                       "El servicio intervenciones rechazó la identidad.")
    if respuesta.status_code >= 400:
        raise ErrorAPI(422, "DATOS_INVALIDOS", str(dictamen.get("detail") or "Las intervenciones no se pueden leer."))
    return dictamen["intervenciones"], dictamen["errores"]


def valida_cuerpo(cuerpo):
    cuerpo = diccionario(cuerpo)
    form, reparto, avisos_entrada = _formulario(cuerpo)
    crudas = _lista(cuerpo.get("interventions"), "interventions")
    datos, errores = valida_escenario(form, bd.regiones_para_escenario(),
                                      bd.enfermedades_para_escenario(), bd.parametros_de)
    avisos = list(avisos_entrada)
    if reparto is not None and datos.get("population_by_age"):
        try:
            enviado = {str(k): int(v) for k, v in reparto.items()}
        except (TypeError, ValueError):
            enviado = None
        if enviado != {str(k): int(v) for k, v in datos["population_by_age"].items()}:
            errores.append("El reparto por edad enviado no coincide con el censo de la región.")
    if not errores:
        intervenciones = []
        if crudas:
            intervenciones, errs = _intervenciones(crudas, datos["horizon_days"])
            errores += errs
        if not errores:
            try:
                resultado = resolver(escenario_para_motor(
                    datos, bd.parametros_de(datos["disease_id"]), intervenciones_para_motor(intervenciones)))
                avisos += list(resultado["avisos"])
            except EscenarioInvalido as exc:
                errores += ["El motor rechaza el escenario: %s" % e for e in exc.errores]
    return {"valido": not errores, "errores": errores, "avisos": avisos, "datos": datos}


def valida_cuerpo_version(cuerpo):
    cuerpo = diccionario(cuerpo)
    scenario_id = entero_positivo(cuerpo.get("scenario_id"), "scenario_id")
    form = {c: _escalar(cuerpo[c], c) for c in CAMPOS_VERSION if cuerpo.get(c) is not None}
    form["estratificar"] = _es_verdadero(cuerpo.get("estratificar"))
    detalle = bd.escenario_detalle(scenario_id)
    if detalle is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el escenario.")
    region = next((r for r in bd.regiones_para_escenario() if r["id"] == detalle["escenario"]["region_id"]),
                  None)
    datos, errores = valida_version(form, region, detalle["escenario"]["default_params"])
    return {"valido": not errores, "errores": errores, "avisos": [], "datos": datos}


def registrar(app):
    @app.post("/api/v1/validate")
    @requiere_token(roles=ROLES)
    def validar():
        return responder(valida_cuerpo(leer_cuerpo()), "validacion")

    @app.post("/api/v1/validate/version")
    @requiere_token(roles=ROLES)
    def validar_version_nueva():
        return responder(valida_cuerpo_version(leer_cuerpo()), "validacion")

    @app.get("/api/v1/versions/<version_id>/validation")
    @requiere_token(roles=ROLES)
    def validar_version(version_id):
        numero = entero_positivo(version_id, "version_id")
        fila = bd.version_simulacion(numero)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la versión.")
        detalle = bd.escenario_detalle(fila["scenario_id"], fila["version_number"])
        if detalle is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la versión.")
        errores, avisos = revisa_version(detalle)
        return responder({
            "version_id": fila["id"], "scenario_id": fila["scenario_id"],
            "version_number": fila["version_number"], "status": fila["status"],
            "valido": not errores, "errores": list(errores),
            "avisos": list(avisos) + avisos_de_ajustes(detalle),
            "huella": huella.de_version(fila["id"]),
        }, "validacion")
