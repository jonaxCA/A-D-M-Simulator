"""Servicio validacion: revisa un escenario contra el motor sin guardar nada.

Reutiliza las reglas del monolito (backend_web.queries): valida_escenario para los
campos, valida_intervencion para cada intervención y el motor
(procesamiento.motor) para lo que solo él sabe. Un resultado "no válido" NO es un
error HTTP: la petición se atendió bien y la respuesta es el dictamen
({valido, errores, avisos}). Un 4xx/5xx solo significa que la petición misma está mal
(cuerpo ilegible, tipos erróneos), que no hay permiso o que la versión no existe.
"""
from backend_web import queries
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo

ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")

# Los nombres son los campos del formulario del monolito (valida_escenario).
CAMPOS_ESCALARES = ("name", "description", "disease_id", "region_id", "population_size",
                    "initial_infected", "horizon_days", "age_unknown_policy", "notes")
CAMPOS_INTERVENCION = ("code", "start_day", "end_day", "coverage", "compliance")
CONOCIDOS = set(CAMPOS_ESCALARES) | {"estratificar", "population_by_age", "interventions"}


def _es_verdadero(valor):
    if isinstance(valor, bool):
        return valor
    return isinstance(valor, str) and valor.strip().lower() in ("true", "1", "si", "sí")


def _escalar(valor, campo):
    if isinstance(valor, (dict, list)):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El campo %s debe ser un valor simple." % campo)
    # Los validadores del monolito leen texto de formulario: .strip() sobre un int falla.
    return str(valor).lower() if isinstance(valor, bool) else str(valor)


def _texto_param(valor):
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (list, tuple)):
        return ",".join(_texto_param(v) for v in valor)
    return str(valor)


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


def _intervenciones(crudas, datos, tipos):
    """Valida cada intervención con valida_intervencion. Devuelve (para_motor, errores)."""
    existentes, errores = [], []
    horizonte = {"horizon_days": datos["horizon_days"]}
    for n, cruda in enumerate(crudas, 1):
        if not isinstance(cruda, dict):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Cada intervención debe ser un objeto.")
        code = str(cruda.get("code") or "").strip()
        form = {c: _escalar(cruda[c], c) for c in CAMPOS_INTERVENCION if cruda.get(c) is not None}
        params = cruda.get("params") or {}
        if params == "":
            params = {}
        if not isinstance(params, dict):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "params de la intervención %d debe ser un objeto." % n)
        for clave, valor in params.items():
            if isinstance(valor, dict):
                raise ErrorAPI(422, "DATOS_INVALIDOS",
                               "El parámetro %s debe ser un valor simple o una lista." % clave)
            # Los validadores del monolito leen texto de formulario (.strip()).
            form["p_%s_%s" % (code, clave)] = _texto_param(valor)
        pedido, errs = queries.valida_intervencion(form, tipos, horizonte, existentes)
        errores += ["Intervención %d: %s" % (n, e) for e in errs]
        if not errs:
            existentes.append(pedido)
    return existentes, errores


def valida_cuerpo(cuerpo):
    cuerpo = diccionario(cuerpo)
    form, reparto, avisos_entrada = _formulario(cuerpo)
    crudas = _lista(cuerpo.get("interventions"), "interventions")
    regiones = queries.get_regiones_para_escenario()
    enfermedades = queries.get_enfermedades_para_escenario()
    datos, errores = queries.valida_escenario(form, regiones, enfermedades)
    avisos = list(avisos_entrada)
    if reparto is not None and datos.get("population_by_age"):
        try:
            enviado = {str(k): int(v) for k, v in reparto.items()}
        except (TypeError, ValueError):
            enviado = None
        if enviado != {str(k): int(v) for k, v in datos["population_by_age"].items()}:
            errores.append("El reparto por edad enviado no coincide con el censo de la región.")
    if not errores:
        params = queries.query("SELECT default_params FROM diseases WHERE id = %s",
                               (datos["disease_id"],), one=True)["default_params"]
        intervenciones, errs = _intervenciones(crudas, datos, queries.get_tipos_intervencion())
        errores += errs
        if not errores:
            try:
                resultado = queries.resolver(
                    queries.escenario_para_motor(
                        datos, params, queries.intervenciones_para_motor(intervenciones)))
                avisos += list(resultado["avisos"])
            except queries.EscenarioInvalido as exc:
                errores += ["El motor rechaza el escenario: %s" % e for e in exc.errores]
    return {"valido": not errores, "errores": errores, "avisos": avisos}


def registrar(app):
    @app.post("/api/v1/validate")
    @requiere_token(roles=ROLES)
    def validar():
        return responder(valida_cuerpo(leer_cuerpo()), "validacion")

    @app.get("/api/v1/versions/<version_id>/validation")
    @requiere_token(roles=ROLES)
    def validar_version(version_id):
        numero = entero_positivo(version_id, "version_id")
        fila = queries.get_version_simulacion(numero)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la versión.")
        detalle = queries.get_escenario_detalle(fila["scenario_id"], fila["version_number"])
        if detalle is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la versión.")
        errores, avisos = queries.revisa_version(detalle)
        return responder({
            "version_id": fila["id"], "scenario_id": fila["scenario_id"],
            "version_number": fila["version_number"], "status": fila["status"],
            "valido": not errores, "errores": list(errores), "avisos": list(avisos),
        }, "validacion")
