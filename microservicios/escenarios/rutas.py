"""Servicio escenarios: alta, versiones nuevas, historial, duplicado, proyectos y archivado.

Las reglas del alta, la versión siguiente y el duplicado son las de backend_web.queries (E8
pendiente); aquí solo se adaptan el cuerpo JSON/XML y los códigos de respuesta. Los proyectos de
investigación, el archivado y el historial con sus responsables (D54) viven en datos.py, con su
bitácora en la misma transacción. Las lecturas aplican el alcance por región de D43.
"""
from flask import g, request

from backend_web import queries
from backend_web.db import query
from epidemia_comun.http import llamar
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.alcance import exige_region, regiones_permitidas
from epidemia_comun.validaciones import diccionario, entero_positivo, fecha

from . import datos as bd

ROLES = ("ANALISTA", "EPIDEMIOLOGO", "ADMINISTRADOR")
# D42: los dos perfiles de solo lectura tienen scenarios.read (migración 052).
ROLES_LEEN = ROLES + ("INVESTIGADOR", "AUTORIDAD_SANITARIA")
ESTADOS_LISTA = ("activo", "archivado", "todos")
CAMPOS_PROYECTO = {"name", "objective", "disease_id", "region_id", "period_start", "period_end",
                   "motores"}
ESTADOS_VERSION = ("borrador", "en_revision", "aprobado", "rechazado")

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
            "autor": v["autor"], "created_by": v.get("created_by"), "revisor": v["revisor"],
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




def _lista(valor, singular):
    # En XML una lista llega como {"motor": "x"} o {"motor": ["x", "y"]}.
    if isinstance(valor, dict) and set(valor) == {singular}:
        valor = valor[singular]
    return [valor] if isinstance(valor, str) else valor


def _invalido(mensaje):
    return ErrorAPI(422, "DATOS_INVALIDOS", mensaje)


def _proyecto_de(cuerpo, actual=None):
    """Los campos de un proyecto, validados. Con `actual` es un cambio parcial (PATCH)."""
    cuerpo = diccionario(cuerpo)
    extra = set(cuerpo) - CAMPOS_PROYECTO
    if extra:
        raise _invalido("Campos desconocidos: " + ", ".join(sorted(extra)) + ".")
    if actual is None:
        faltan = CAMPOS_PROYECTO - {"objective"} - set(cuerpo)
        if faltan:
            raise _invalido("Faltan: " + ", ".join(sorted(faltan)) + ".")
    elif not cuerpo:
        raise _invalido("No hay nada que cambiar.")
    valores = {}
    if "name" in cuerpo:
        nombre = cuerpo["name"]
        if not isinstance(nombre, str) or not 3 <= len(nombre.strip()) <= 160:
            raise _invalido("name debe tener de 3 a 160 caracteres.")
        valores["name"] = nombre.strip()
    if "objective" in cuerpo:
        objetivo = cuerpo["objective"]
        if objetivo is not None and not isinstance(objetivo, str):
            raise _invalido("objective debe ser texto.")
        objetivo = (objetivo or "").strip() or None
        if objetivo and len(objetivo) > 2000:
            raise _invalido("objective no puede pasar de 2,000 caracteres.")
        valores["objective"] = objetivo
    if "disease_id" in cuerpo:
        valores["disease_id"] = entero_positivo(cuerpo["disease_id"], "disease_id")
        if valores["disease_id"] not in {e["id"] for e in queries.get_enfermedades_para_escenario()}:
            raise _invalido("No existe la enfermedad %s o no está activa." % valores["disease_id"])
    if "region_id" in cuerpo:
        valores["region_id"] = entero_positivo(cuerpo["region_id"], "region_id")
        if valores["region_id"] not in {r["id"] for r in queries.get_regiones_para_escenario()}:
            raise _invalido("No existe la región %s." % valores["region_id"])
    for campo in ("period_start", "period_end"):
        if campo in cuerpo:
            valores[campo] = fecha(cuerpo[campo], campo)
    inicio = valores.get("period_start", actual["period_start"] if actual else None)
    fin = valores.get("period_end", actual["period_end"] if actual else None)
    if inicio and fin and fin < inicio:
        raise _invalido("period_end no puede ser antes de period_start.")
    if "motores" in cuerpo:
        motores = _lista(cuerpo["motores"], "motor")
        if (not isinstance(motores, list) or not motores or len(set(motores)) != len(motores)
                or any(m not in bd.MOTORES for m in motores)):
            raise _invalido("motores debe ser una lista sin repetir de: %s." % ", ".join(bd.MOTORES))
        valores["engines"] = motores
    return valores


def _proyecto(p):
    return {"id": p["id"], "name": p["name"], "objective": p["objective"],
            "disease_id": p["disease_id"], "enfermedad": p["enfermedad"],
            "region_id": p["region_id"], "region": p["region"],
            "period_start": p["period_start"], "period_end": p["period_end"],
            "motores": list(p["engines"]), "owner_id": p["owner_id"], "autor": p["autor"],
            "status": p["status"], "created_at": p["created_at"], "updated_at": p["updated_at"],
            "n_escenarios": p["n_escenarios"]}


def _proyecto_visible(project_id):
    proyecto = bd.proyecto(project_id)
    if proyecto is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el proyecto.")
    exige_region(proyecto["region_id"])
    return proyecto


def _proyecto_destino(project_id, disease_id, region_id):
    """El proyecto al que va a entrar un escenario: existe, está activo y coincide."""
    proyecto = bd.proyecto(project_id)
    if proyecto is None:
        raise _invalido("No existe el proyecto %s." % project_id)
    exige_region(proyecto["region_id"])
    if proyecto["status"] != "activo":
        raise ErrorAPI(409, "CONFLICTO", "El proyecto está archivado: no recibe escenarios.")
    if (proyecto["disease_id"], proyecto["region_id"]) != (disease_id, region_id):
        raise _invalido("El escenario no es de la enfermedad y la región del proyecto.")
    return proyecto


def _exige_dueno(dato, mensaje):
    if not _es_dueno_o_admin(dato):
        raise ErrorAPI(403, "PERMISO_INSUFICIENTE", mensaje)


def _escenario_propio(scenario_id, mensaje):
    escenario = bd.escenarios([scenario_id]).get(scenario_id)
    if escenario is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el escenario.")
    exige_region(escenario["region_id"])
    _exige_dueno(escenario, mensaje)
    return escenario


def _project_id(valor):
    return None if valor in (None, "") else entero_positivo(valor, "project_id")


def registrar(app):
    @app.get("/api/v1/scenarios")
    @requiere_token(roles=ROLES_LEEN)
    def listar():
        busqueda = (request.args.get("q") or "").strip() or None
        proyecto = _project_id(request.args.get("project_id"))
        archivados = _booleano(request.args.get("archived"), "archived")
        filas = queries.get_escenarios(busqueda=busqueda)
        propios = bd.escenarios([f["id"] for f in filas])
        permitidas = regiones_permitidas()
        salida = []
        for f in filas:
            extra = propios.get(f["id"], {})
            if permitidas is not None and extra.get("region_id") not in permitidas:
                continue
            if (f["status"] == "archivado" and not archivados) or (
                    proyecto is not None and extra.get("project_id") != proyecto):
                continue
            salida.append(dict(_fila_listado(f), project_id=extra.get("project_id")))
        return responder({"total": len(salida), "escenarios": salida}, "lista_escenarios")

    # Las versiones de todos los escenarios en una sola llamada (pantalla de simulaciones de la
    # web). Las aprobadas van primero: son las únicas que se pueden correr.
    @app.get("/api/v1/scenarios/versions")
    @requiere_token(roles=ROLES_LEEN)
    def versiones():
        estado = request.args.get("status")
        if estado is not None and estado not in ESTADOS_VERSION:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "status debe ser uno de: %s." % ", ".join(ESTADOS_VERSION))
        permitidas = regiones_permitidas()
        filas = query("""SELECT sv.id, sv.scenario_id, sv.version_number, sv.status,
                                sv.population_size, sv.horizon_days, sv.initial_infected,
                                sv.created_at, sv.reviewed_at, sv.review_comment,
                                s.name AS scenario_name, s.status AS scenario_status,
                                s.region_id, d.name AS disease_name, reg.name AS region_name,
                                autor.full_name AS creado_por, revisor.full_name AS revisado_por
                         FROM scenario_versions sv
                         JOIN scenarios s ON s.id = sv.scenario_id
                         JOIN diseases d ON d.id = s.disease_id
                         JOIN regions reg ON reg.id = s.region_id
                         JOIN users autor ON autor.id = sv.created_by
                         LEFT JOIN users revisor ON revisor.id = sv.reviewed_by
                         WHERE %s IS NULL OR sv.status = %s
                         ORDER BY (sv.status = 'aprobado') DESC, sv.created_at DESC""", (estado, estado))
        salida = [{k: v for k, v in f.items() if k != "region_id"} for f in filas
                  if permitidas is None or f["region_id"] in permitidas]
        return responder({"total": len(salida), "versiones": salida}, "versiones")

    @app.get("/api/v1/scenarios/<int:scenario_id>")
    @requiere_token(roles=ROLES_LEEN)
    def consultar(scenario_id):
        numero = request.args.get("version")
        if numero is not None:
            numero = entero_positivo(numero, "version")
        detalle = _detalle(scenario_id, numero)
        e, v = detalle["escenario"], detalle["version"]
        exige_region(e["region_id"])
        propio = bd.escenarios([scenario_id]).get(scenario_id, {})
        datos = {"id": e["id"], "name": e["name"], "description": e["description"],
                 "status": e["status"], "owner_id": e["owner_id"], "created_at": e["created_at"],
                 "disease_id": e["disease_id"], "enfermedad": e["enfermedad"],
                 "region_id": e["region_id"], "region": e["region"], "autor": e["autor"],
                 "region_poblacion": e.get("region_poblacion"),
                 "project_id": propio.get("project_id"),
                 "editable": bool(detalle["editable"]) and e["status"] != "archivado",
                 "parametros_congelados": bool(detalle.get("parametros_congelados")),
                 "parametros_sin_congelar": bool(detalle.get("parametros_sin_congelar")),
                 "version": _version(v) if v else None,
                 "intervenciones": [_intervencion(i) for i in detalle["intervenciones"]]}
        return responder(datos, "escenario")

    @app.get("/api/v1/scenarios/<int:scenario_id>/versions")
    @requiere_token(roles=ROLES_LEEN)
    def historial(scenario_id):
        exige_region(_detalle(scenario_id)["escenario"]["region_id"])
        filas = bd.versiones(scenario_id)
        return responder({"scenario_id": scenario_id, "total": len(filas), "versiones": filas},
                         "historial_versiones")

    @app.post("/api/v1/scenarios")
    @requiere_token(roles=ROLES)
    def crear():
        cuerpo = diccionario(leer_cuerpo())
        project_id = _project_id(cuerpo.pop("project_id", None))
        form, estratificar = _formulario(cuerpo, CAMPOS_ALTA)
        regiones = queries.get_regiones_para_escenario()
        enfermedades = queries.get_enfermedades_para_escenario()
        datos, errores = queries.valida_escenario(form, regiones, enfermedades)
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        exige_region(datos["region_id"])
        if project_id is not None:
            _proyecto_destino(project_id, datos["disease_id"], datos["region_id"])
        _validar_con_servicio(dict(form, estratificar=estratificar))
        ok, error, scenario_id = queries.crea_escenario(datos, contexto=g.contexto)
        if not ok:
            _falla(error)
        if project_id is not None:
            bd.asigna_proyecto(scenario_id, project_id, contexto=g.contexto)
        return responder({"id": scenario_id, "version_number": 1, "status": "borrador",
                          "project_id": project_id}, "escenario", estado=201)

    @app.post("/api/v1/scenarios/<int:scenario_id>/versions")
    @requiere_token(roles=ROLES)
    def nueva_version(scenario_id):
        detalle = _detalle(scenario_id)
        exige_region(detalle["escenario"]["region_id"])
        if not detalle["version"]:
            raise ErrorAPI(409, "CONFLICTO", "Ese escenario no tiene una versión de la que partir.")
        if not _es_dueno_o_admin(detalle["escenario"]):
            raise ErrorAPI(403, "PERMISO_INSUFICIENTE",
                           "Solo quien creó el escenario puede versionarlo.")
        if detalle["escenario"]["status"] == "archivado":
            raise ErrorAPI(409, "CONFLICTO", "El escenario está archivado: restáuralo antes de "
                           "crear otra versión.")
        if detalle["version"]["status"] == "en_revision":
            raise ErrorAPI(409, "CONFLICTO", "La versión vigente está en revisión: espera el "
                           "dictamen (o que te la devuelvan) antes de crear otra.")
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
        exige_region(detalle["escenario"]["region_id"])
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
        # El duplicado se queda en el proyecto del original, si sigue activo.
        project_id = bd.escenarios([scenario_id]).get(scenario_id, {}).get("project_id")
        if project_id is not None and (bd.proyecto(project_id) or {}).get("status") == "activo":
            bd.asigna_proyecto(nuevo_id, project_id, contexto=g.contexto)
        else:
            project_id = None
        return responder({"id": nuevo_id, "duplicado_de": scenario_id,
                          "version_origen": numero, "version_number": 1,
                          "status": "borrador", "project_id": project_id}, "escenario", estado=201)

    @app.put("/api/v1/scenarios/<int:scenario_id>/project")
    @requiere_token(roles=ROLES)
    def mover_a_proyecto(scenario_id):
        cuerpo = diccionario(leer_cuerpo())
        if set(cuerpo) != {"project_id"}:
            raise _invalido("Solo se acepta project_id (null lo saca de su proyecto).")
        project_id = _project_id(cuerpo["project_id"])
        escenario = _escenario_propio(scenario_id, "Solo quien creó el escenario puede moverlo "
                                                   "de proyecto.")
        if project_id is not None:
            _proyecto_destino(project_id, escenario["disease_id"], escenario["region_id"])
        bd.asigna_proyecto(scenario_id, project_id, contexto=g.contexto)
        return responder({"scenario_id": scenario_id, "project_id": project_id}, "escenario")

    def _archivar(scenario_id, archivar):
        _escenario_propio(scenario_id, "Solo quien creó el escenario puede archivarlo o "
                                       "restaurarlo.")
        bd.archiva(scenario_id, archivar, contexto=g.contexto)
        return responder({"id": scenario_id, "status": "archivado" if archivar else "borrador"},
                         "escenario")

    @app.post("/api/v1/scenarios/<int:scenario_id>/archive")
    @requiere_token(roles=ROLES)
    def archivar(scenario_id):
        return _archivar(scenario_id, True)

    @app.post("/api/v1/scenarios/<int:scenario_id>/restore")
    @requiere_token(roles=ROLES)
    def restaurar(scenario_id):
        return _archivar(scenario_id, False)

    @app.get("/api/v1/projects")
    @requiere_token(roles=ROLES_LEEN)
    def listar_proyectos():
        estado = request.args.get("status", "activo")
        if estado not in ESTADOS_LISTA:
            raise _invalido("status debe ser uno de: %s." % ", ".join(ESTADOS_LISTA))
        busqueda = (request.args.get("q") or "").strip() or None
        permitidas = regiones_permitidas()
        filas = bd.proyectos(None if estado == "todos" else estado, busqueda,
                             None if permitidas is None else sorted(permitidas))
        return responder({"total": len(filas), "proyectos": [_proyecto(p) for p in filas]},
                         "lista_proyectos")

    @app.get("/api/v1/projects/<int:project_id>")
    @requiere_token(roles=ROLES_LEEN)
    def consultar_proyecto(project_id):
        proyecto = _proyecto_visible(project_id)
        return responder(dict(_proyecto(proyecto), escenarios=bd.escenarios_de(project_id)),
                         "proyecto")

    @app.post("/api/v1/projects")
    @requiere_token(roles=ROLES)
    def crear_proyecto():
        valores = _proyecto_de(leer_cuerpo())
        exige_region(valores["region_id"])
        project_id = bd.crea_proyecto(valores, contexto=g.contexto)
        return responder(_proyecto(bd.proyecto(project_id)), "proyecto", estado=201)

    @app.patch("/api/v1/projects/<int:project_id>")
    @requiere_token(roles=ROLES)
    def cambiar_proyecto(project_id):
        actual = _proyecto_visible(project_id)
        _exige_dueno(actual, "Solo quien creó el proyecto puede cambiarlo.")
        cambios = _proyecto_de(leer_cuerpo(), actual)
        if "region_id" in cambios:
            exige_region(cambios["region_id"])
        bd.cambia_proyecto(project_id, cambios, contexto=g.contexto)
        return responder(_proyecto(bd.proyecto(project_id)), "proyecto")

    def _estado_proyecto(project_id, estado):
        _exige_dueno(_proyecto_visible(project_id), "Solo quien creó el proyecto puede archivarlo "
                                                    "o restaurarlo.")
        bd.cambia_estado_proyecto(project_id, estado, contexto=g.contexto)
        return responder(_proyecto(bd.proyecto(project_id)), "proyecto")

    @app.post("/api/v1/projects/<int:project_id>/archive")
    @requiere_token(roles=ROLES)
    def archivar_proyecto(project_id):
        return _estado_proyecto(project_id, "archivado")

    @app.post("/api/v1/projects/<int:project_id>/restore")
    @requiere_token(roles=ROLES)
    def restaurar_proyecto(project_id):
        return _estado_proyecto(project_id, "activo")
