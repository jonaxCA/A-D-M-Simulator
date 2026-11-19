import re

from . import api, config, esquemas, resumen, xmlio

NOMBRES_ROL = {"ANALISTA": "analista", "ADMINISTRADOR": "administrador",
               "EPIDEMIOLOGO": "epidemiólogo", "CAPTURISTA": "capturista"}


def salud(c):
    return c.pedir("estado-servicios", "GET", "/api/v1/services/health", publico=True)


def captcha(c):
    return c.pedir("auth", "GET", "/api/v1/auth/captcha", publico=True)


def sesion_actual(c):
    return c.pedir("sesiones", "GET", "/api/v1/sessions/current")


def perfil(c):
    return c.pedir("usuarios", "GET", "/api/v1/users/me")


def abrir_sesion(c, usuario, password, captcha_id, respuesta):
    c.iniciar_sesion(usuario, password, captcha_id, respuesta)
    roles = sesion_actual(c).get("roles") or []
    c.usuario.update(perfil(c))
    c.usuario["roles"] = roles
    if not set(roles) & set(config.ROLES_PERMITIDOS):
        c.cerrar_sesion()
        nombres = ", ".join(NOMBRES_ROL.get(r, r) for r in roles) or "sin rol"
        raise api.ErrorServicio("La app de escritorio es para analistas y administradores. "
                                "Tu cuenta es de %s: usa el sistema web o la app móvil." % nombres, 403)
    return c.usuario


def enfermedades(c):
    datos = c.pedir("enfermedades", "GET", "/api/v1/diseases",
                    params={"size": 100, "status": "activa"}, publico=True)
    return datos.get("enfermedades") or []


def regiones(c):
    return c.pedir("regiones", "GET", "/api/v1/regions", publico=True).get("municipios") or []


def tipos_intervencion(c):
    return c.pedir("tipos-intervencion", "GET", "/api/v1/intervention-types", publico=True).get("tipos") or []


def escenarios(c, texto=""):
    params = {"q": texto} if texto else None
    return c.pedir("escenarios", "GET", "/api/v1/scenarios", params=params).get("escenarios") or []


def escenario(c, escenario_id, version=None):
    params = {"version": version} if version else None
    return c.pedir("escenarios", "GET", "/api/v1/scenarios/%s" % escenario_id, params=params)


def versiones(c, escenario_id):
    return c.pedir("escenarios", "GET", "/api/v1/scenarios/%s/versions" % escenario_id).get("versiones") or []


def crear_escenario(c, datos):
    return c.pedir("escenarios", "POST", "/api/v1/scenarios", datos, "escenario")


def crear_version(c, escenario_id, datos):
    return c.pedir("escenarios", "POST", "/api/v1/scenarios/%s/versions" % escenario_id, datos, "version")


def duplicar(c, escenario_id, nombre, version):
    return c.pedir("escenarios", "POST", "/api/v1/scenarios/%s/duplicate" % escenario_id,
                   {"name": nombre, "version": version}, "duplicado")


def agregar_intervencion(c, version_id, datos):
    return c.pedir("intervenciones", "POST", "/api/v1/versions/%s/interventions" % version_id,
                   datos, "intervencion")


def quitar_intervencion(c, version_id, intervencion_id):
    return c.pedir("intervenciones", "DELETE",
                   "/api/v1/versions/%s/interventions/%s" % (version_id, intervencion_id))


def mover_intervencion(c, version_id, intervencion_id, direccion):
    return c.pedir("intervenciones", "POST",
                   "/api/v1/versions/%s/interventions/%s/move" % (version_id, intervencion_id),
                   {"direction": direccion}, "movimiento")


def validar_version(c, version_id):
    return c.pedir("validacion", "GET", "/api/v1/versions/%s/validation" % version_id)


def enviar_a_revision(c, escenario_id):
    return c.pedir("aprobacion", "POST", "/api/v1/scenarios/%s/submit" % escenario_id)


def exportar_xml(c, escenario_id, version=None):
    params = {"version": version} if version else None
    r = c.enviar("escenarios-xml", "GET", "/api/v1/scenarios/%s/export" % escenario_id, params=params)
    esquemas.validar_escenario(r.content)
    return r.content


def importar_xml(c, contenido):
    esquemas.validar_escenario(contenido)
    r = c.enviar("escenarios-xml", "POST", "/api/v1/scenarios/import", cuerpo=contenido)
    return xmlio.leer(r.content)


def lanzar_corrida(c, version_id, semilla, motor, forzar_error=False):
    datos = {"scenario_version_id": version_id, "seed": semilla, "engine": motor}
    if forzar_error:
        datos["forzar_error"] = True
    return c.pedir("corridas", "POST", "/api/v1/runs", datos, "solicitud")


def corridas(c, **filtros):
    params = {"limit": 100}
    params.update({k: v for k, v in filtros.items() if v not in (None, "")})
    return c.pedir("corridas", "GET", "/api/v1/runs", params=params).get("corridas") or []


def corrida(c, corrida_id):
    return c.pedir("corridas", "GET", "/api/v1/runs/%s" % corrida_id)


def cancelar_corrida(c, corrida_id):
    return c.pedir("corridas", "POST", "/api/v1/runs/%s/cancel" % corrida_id)


def _grupos(ids):
    for i in range(0, len(ids), config.LIMITE_COMPARACION):
        grupo = ids[i:i + config.LIMITE_COMPARACION]
        yield ids[-2:] if len(grupo) == 1 else grupo


def comparar(c, ids):
    aviso, salida = "", []
    for grupo in _grupos(ids):
        datos = c.pedir("comparacion", "GET", "/api/v1/comparisons",
                        params={"runs": ",".join(str(x) for x in grupo)})
        aviso = datos.get("aviso") or aviso
        salida.extend(datos.get("corridas") or [])
    return aviso, list({x["id"]: x for x in salida}.values())


def pareto(c, ids, metrica):
    junto = {"filas": []}
    for grupo in _grupos(ids):
        datos = c.pedir("pareto", "GET", "/api/v1/pareto",
                        params={"runs": ",".join(str(x) for x in grupo), "metric": metrica})
        filas = datos.pop("filas", None) or []
        junto.update(datos)
        junto["filas"].extend(filas)
    junto["filas"] = list({f["id"]: f for f in junto["filas"]}.values())
    return junto


def avisos(c):
    return c.pedir("notificaciones", "GET", "/api/v1/notifications", params={"limit": 50})


def marcar_leido(c, aviso_id):
    return c.pedir("notificaciones", "POST", "/api/v1/notifications/%s/read" % aviso_id)


def cargar_comparacion(c, version_ids, metrica):
    grupos = {}
    for vid in version_ids:
        grupos[vid] = resumen.una_por_semilla(corridas(c, scenario_version_id=vid, status="completado"))
    semillas = resumen.semillas_comunes(grupos)
    if not semillas:
        raise ValueError("Las versiones elegidas no tienen corridas completadas con la misma semilla.")
    elegidas = {vid: [g[s] for s in semillas] for vid, g in grupos.items()}
    ids = [x["id"] for lista in elegidas.values() for x in lista]
    aviso, comparadas = comparar(c, ids)
    try:
        datos_pareto = pareto(c, ids, metrica)
    except api.ErrorServicio as exc:
        # Sin costo unitario con fuente o supuesto, pareto se niega (regla 8): se compara sin frontera.
        if exc.status != 422:
            raise
        datos_pareto = {"filas": [], "avisos": motivos_sin_costo(str(exc))}
    return resumen.armar(elegidas, comparadas, datos_pareto, metrica, aviso)


def motivos_sin_costo(texto):
    motivos = []
    for parte in re.split(r"SIM-\d+ - [^:]*: ", texto):
        parte = parte.strip()
        if parte and parte not in motivos:
            motivos.append(parte)
    return motivos
