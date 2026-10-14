"""Servicio escenarios: alta, versiones nuevas, historial y duplicado.

Las reglas (validación, alta, versión siguiente, duplicado) son las de
backend_web.queries; aquí solo se adaptan el cuerpo JSON/XML y los códigos de
respuesta. Las funciones de escritura de queries.py abren su propia transacción
y registran la bitácora dentro de ella (log_audit con cur), con el Contexto
sacado del token.
"""
from flask import g, request

from backend_web import queries
from epidemia_comun.http import llamar
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo

ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")

CAMPOS_ALTA = {"name", "description", "disease_id", "region_id", "population_size",
               "horizon_days", "initial_infected", "stratify", "age_unknown_policy", "notes"}
CAMPOS_VERSION = {"population_size", "horizon_days", "initial_infected", "stratify",
                  "age_unknown_policy", "notes"}


def _booleano(valor, campo):
    if valor is None or valor == "":
        return False
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)) and valor in (0, 1):
        return bool(valor)
    if isinstance(valor, str) and valor.strip().lower() in ("true", "false", "1", "0"):
        return valor.strip().lower() in ("true", "1")
    raise ErrorAPI(422, "DATOS_INVALIDOS", "El campo %s debe ser booleano." % campo)


def _texto(valor):
    return "" if valor is None else str(valor)


def _formulario(datos, permitidos):
    """Del cuerpo JSON/XML a los campos planos que esperan las valida_* del monolito."""
    datos = diccionario(datos)
    extra = set(datos) - permitidos
    if extra:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Campos desconocidos: " + ", ".join(sorted(extra)) + ".")
    for clave, valor in datos.items():
        if isinstance(valor, (dict, list)):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "El campo %s debe ser un valor simple." % clave)
    form = {clave: _texto(valor) for clave, valor in datos.items() if clave != "stratify"}
    estratificar = _booleano(datos.get("stratify"), "stratify")
    form["estratificar"] = "1" if estratificar else ""
    return form, estratificar


def _estado_por_mensaje(mensaje):
    """Clasifica el texto de error que regresan las funciones de escritura."""
    if "Ya tienes" in mensaje or "Ya hay" in mensaje or "al mismo tiempo" in mensaje:
        return 409, "CONFLICTO"
    if "ya no existe" in mensaje or "no existe" in mensaje:
        return 404, "NO_ENCONTRADO"
    if "requiere la migración" in mensaje:
        return 500, "ERROR_INTERNO"
    return 422, "DATOS_INVALIDOS"


def _falla(mensaje):
    estado, codigo = _estado_por_mensaje(mensaje or "")
    if estado == 500:
        raise ErrorAPI(500, "ERROR_INTERNO", "Ocurrió un error interno.")
    raise ErrorAPI(estado, codigo, mensaje)


def _grupos(poblacion_por_edad):
    return [{"grupo": grupo, "poblacion": n} for grupo, n in (poblacion_por_edad or {}).items()]


def _fila_listado(f):
    return {"id": f["id"], "name": f["name"], "description": f["description"],
            "status": f["status"], "created_at": f["created_at"],
            "enfermedad": f["enfermedad"], "region": f["region"], "autor": f["autor"],
            "version_number": f["version_number"], "version_status": f["version_status"],
            "population_size": f["population_size"], "horizon_days": f["horizon_days"],
            "initial_infected": f["initial_infected"], "por_edad": f["por_edad"]}


def _version(v):
    return {"id": v["id"], "version_number": v["version_number"], "status": v["status"],
            "is_current": v["is_current"], "population_size": v["population_size"],
            "horizon_days": v["horizon_days"], "initial_infected": v["initial_infected"],
            "notes": v["notes"], "created_at": v["created_at"],
            "por_edad": bool(v["population_by_age"]),
            "grupos_edad": _grupos(v["population_by_age"]),
            "population_age_unknown": v["population_age_unknown"],
            "age_unknown_policy": v["age_unknown_policy"],
            "autor": v["autor"], "revisor": v["revisor"],
            "submitted_at": v["submitted_at"], "reviewed_at": v["reviewed_at"],
            "review_comment": v["review_comment"]}


def _intervencion(i):
    return {"id": i["id"], "code": i["code"], "name": i["name"],
            "target_layer": i["target_layer"], "start_day": i["start_day"],
            "end_day": i["end_day"], "coverage": i["coverage"],
            "compliance": i["compliance"], "params": i["params"] or {},
            "order_index": i["order_index"]}


def _detalle(scenario_id, numero=None):
    detalle = queries.get_escenario_detalle(scenario_id, numero)
    if detalle is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el escenario o esa versión.")
    return detalle


def _es_dueno_o_admin(escenario):
    usuario = g.usuario
    return (str(escenario["owner_id"]) == str(usuario.get("sub"))
            or "ADMINISTRADOR" in (usuario.get("roles") or []))


def _validar_con_servicio(entrada):
    """Pasa el escenario por el servicio validacion antes de guardarlo."""
    respuesta = llamar("validacion", "POST", "/api/v1/validate", formato="json", cuerpo=entrada)
    if respuesta.status_code >= 500:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio validacion no pudo responder.")
    try:
        resultado = respuesta.json()
    except ValueError:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio validacion respondió algo ilegible.")
    if respuesta.status_code in (401, 403):
        raise ErrorAPI(respuesta.status_code,
                       "TOKEN_INVALIDO" if respuesta.status_code == 401 else "PERMISO_INSUFICIENTE",
                       "El servicio validacion rechazó la identidad.")
    if respuesta.status_code >= 400:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       str(resultado.get("detail") or "validacion rechazó el escenario."))
    errores = resultado.get("errores") if isinstance(resultado, dict) else None
    if errores or (isinstance(resultado, dict) and resultado.get("valido") is False):
        if isinstance(errores, list):
            detalle = " ".join(str(e) for e in errores)
        else:
            detalle = str(errores or "validacion rechazó el escenario.")
        raise ErrorAPI(422, "DATOS_INVALIDOS", detalle)


def registrar(app):
    @app.get("/api/v1/scenarios")
    @requiere_token(roles=ROLES)
    def listar():
        busqueda = (request.args.get("q") or "").strip() or None
        filas = [_fila_listado(f) for f in queries.get_escenarios(busqueda=busqueda)]
        return responder({"total": len(filas), "escenarios": filas}, "lista_escenarios")

    @app.get("/api/v1/scenarios/<int:scenario_id>")
    @requiere_token(roles=ROLES)
    def consultar(scenario_id):
        numero = request.args.get("version")
        if numero is not None:
            numero = entero_positivo(numero, "version")
        detalle = _detalle(scenario_id, numero)
        e, v = detalle["escenario"], detalle["version"]
        datos = {"id": e["id"], "name": e["name"], "description": e["description"],
                 "status": e["status"], "owner_id": e["owner_id"], "created_at": e["created_at"],
                 "disease_id": e["disease_id"], "enfermedad": e["enfermedad"],
                 "region_id": e["region_id"], "region": e["region"], "autor": e["autor"],
                 "editable": detalle["editable"],
                 "version": _version(v) if v else None,
                 "intervenciones": [_intervencion(i) for i in detalle["intervenciones"]]}
        return responder(datos, "escenario")

    @app.get("/api/v1/scenarios/<int:scenario_id>/versions")
    @requiere_token(roles=ROLES)
    def historial(scenario_id):
        _detalle(scenario_id)
        filas = [{"version_number": v["version_number"], "status": v["status"],
                  "is_current": v["is_current"], "population_size": v["population_size"],
                  "horizon_days": v["horizon_days"], "initial_infected": v["initial_infected"],
                  "notes": v["notes"], "created_at": v["created_at"], "por_edad": v["por_edad"],
                  "autor": v["autor"], "n_intervenciones": v["n_intervenciones"]}
                 for v in queries.get_versiones(scenario_id)]
        return responder({"scenario_id": scenario_id, "total": len(filas), "versiones": filas},
                         "historial_versiones")

    @app.post("/api/v1/scenarios")
    @requiere_token(roles=ROLES)
    def crear():
        form, estratificar = _formulario(leer_cuerpo(), CAMPOS_ALTA)
        regiones = queries.get_regiones_para_escenario()
        enfermedades = queries.get_enfermedades_para_escenario()
        datos, errores = queries.valida_escenario(form, regiones, enfermedades)
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        _validar_con_servicio(dict(form, estratificar=estratificar))
        ok, error, scenario_id = queries.crea_escenario(datos, contexto=g.contexto)
        if not ok:
            _falla(error)
        return responder({"id": scenario_id, "version_number": 1, "status": "borrador"},
                         "escenario", estado=201)

    @app.post("/api/v1/scenarios/<int:scenario_id>/versions")
    @requiere_token(roles=ROLES)
    def nueva_version(scenario_id):
        detalle = _detalle(scenario_id)
        if not detalle["version"]:
            raise ErrorAPI(409, "CONFLICTO", "Ese escenario no tiene una versión de la que partir.")
        if not _es_dueno_o_admin(detalle["escenario"]):
            raise ErrorAPI(403, "PERMISO_INSUFICIENTE",
                           "Solo quien creó el escenario puede versionarlo.")
        form, _ = _formulario(leer_cuerpo(), CAMPOS_VERSION)
        region = next((r for r in queries.get_regiones_para_escenario()
                       if r["id"] == detalle["escenario"]["region_id"]), None)
        datos, errores = queries.valida_version(
            form, region, detalle["escenario"]["default_params"])
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        ok, error, numero = queries.crea_version(scenario_id, datos, contexto=g.contexto)
        if not ok:
            _falla(error)
        return responder({"scenario_id": scenario_id, "version_number": numero,
                          "status": "borrador"}, "version", estado=201)

    @app.post("/api/v1/scenarios/<int:scenario_id>/duplicate")
    @requiere_token(roles=ROLES)
    def duplicar(scenario_id):
        datos = diccionario(leer_cuerpo())
        if set(datos) - {"name", "version"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Solo se aceptan name y version.")
        nombre = datos.get("name")
        if not isinstance(nombre, str) or not nombre.strip():
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Ponle un nombre al escenario nuevo.")
        detalle = _detalle(scenario_id)
        if datos.get("version") in (None, ""):
            if not detalle["version"]:
                raise ErrorAPI(409, "CONFLICTO", "Ese escenario no tiene versiones.")
            numero = detalle["version"]["version_number"]
        else:
            numero = entero_positivo(datos["version"], "version")
        ok, error, nuevo_id = queries.duplica_escenario(
            scenario_id, numero, nombre, contexto=g.contexto)
        if not ok:
            _falla(error)
        return responder({"id": nuevo_id, "duplicado_de": scenario_id,
                          "version_origen": numero, "version_number": 1,
                          "status": "borrador"}, "escenario", estado=201)
