import hashlib
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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


def dispositivo():
    """Identificador estable de este equipo (D41): se genera una vez y se guarda en la carpeta local."""
    archivo = config.CARPETA_LOCAL / "dispositivo"
    try:
        guardado = archivo.read_text(encoding="ascii").strip()
        if 8 <= len(guardado) <= 128:
            return guardado
    except (OSError, UnicodeError):
        pass
    nuevo = uuid.uuid4().hex
    try:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(nuevo, encoding="ascii")
    except OSError:
        pass
    return nuevo


def abrir_sesion(c, usuario, password, captcha_id, respuesta):
    """Regresa la cuenta, o el reto de MFA (mfa_requerido) si el perfil es crítico (D40)."""
    datos = c.iniciar_sesion(usuario, password, captcha_id, respuesta,
                             dispositivo() if config.ENVIAR_DISPOSITIVO else None)
    if datos.get("mfa_requerido"):
        return datos
    return completar_sesion(c)


def segundo_paso(c, accion, mfa_token, **campos):
    """enroll regresa el secreto; verify y confirm abren la sesión. confirm trae los códigos de respaldo,
    que el servidor muestra una sola vez."""
    datos = c.segundo_paso(accion, mfa_token, **campos)
    if accion == "enroll":
        return datos
    return {"usuario": completar_sesion(c), "codigos_respaldo": datos.get("codigos_respaldo") or []}


def completar_sesion(c):
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


def parametros_enfermedad(c, enfermedad_id):
    datos = c.pedir("parametros", "GET", "/api/v1/diseases/%s/parameters" % enfermedad_id, publico=True)
    return datos.get("parametros") or {}


def estado_parametros(c, enfermedad_id):
    return c.pedir("parametros", "GET", "/api/v1/diseases/%s/parameters/status" % enfermedad_id, publico=True)


def versiones_parametros(c, enfermedad_id):
    # El historial de versiones de los parámetros de la enfermedad (D58): cada cambio guarda la versión completa con su motivo.
    datos = c.pedir("parametros", "GET", "/api/v1/diseases/%s/parameters/versions" % enfermedad_id, publico=True)
    return datos.get("versiones") or []


def firma_version(c, version_id):
    return c.pedir("aprobacion", "GET", "/api/v1/versions/%s/signature" % version_id)


def zonas_mapa(c, enfermedad_id, dias):
    return c.pedir("zonas", "GET", "/api/v1/zones/map", params={"disease_id": enfermedad_id, "days": dias})


def geometria_municipal(c, etag=None):
    r = c.enviar("zonas", "GET", "/api/v1/zones/geometry", accept="application/geo+json", etag=etag)
    if r.status_code == 304 and etag:
        return None, etag
    if r.status_code == 200 and r.headers.get("Content-Type", "").split(";")[0] == "application/geo+json":
        try:
            datos = r.json()
            if datos.get("type") == "FeatureCollection" and isinstance(datos.get("features"), list):
                return datos, r.headers.get("ETag")
        except (ValueError, AttributeError):
            pass
    raise api.ErrorServicio("El servicio zonas no devolvió una geometría municipal GeoJSON válida.")


def historial_auditoria(c, entidad, identificador, limite, desplazamiento):
    return c.pedir("roles", "GET", "/api/v1/audit/history/%s/%d" % (entidad, identificador),
                   params={"limit": limite, "offset": desplazamiento})


def estado_calibracion(c, enfermedad_id, region_id):
    return c.pedir("pareto", "GET", "/api/v1/pareto/calibration",
                   params={"disease": enfermedad_id, "region": region_id})


def sensibilidad(c, version_id, parametro, cambios):
    return c.pedir("pareto", "GET", "/api/v1/pareto/sensitivity",
                   params={"version": version_id, "parameter": parametro, "percent": cambios})


def tipos_intervencion(c):
    return c.pedir("tipos-intervencion", "GET", "/api/v1/intervention-types", publico=True).get("tipos") or []


def escenarios(c, texto="", proyecto_id=None, archivados=False):
    params = {k: v for k, v in (("q", texto), ("project_id", proyecto_id),
                                ("archived", "true" if archivados else None)) if v}
    return c.pedir("escenarios", "GET", "/api/v1/scenarios", params=params or None).get("escenarios") or []


# Proyectos de investigación y archivado (D54, RF-D12, RF-D19). escenarios aplica dueño, alcance y reglas.
MOTORES_PROYECTO = ("seir-ref", "abm-ref", "abm-gpu")


def proyectos(c, estado=None, texto=""):
    params = {k: v for k, v in (("status", estado), ("q", texto)) if v}
    return c.pedir("escenarios", "GET", "/api/v1/projects", params=params or None).get("proyectos") or []


def proyecto(c, proyecto_id):
    return c.pedir("escenarios", "GET", "/api/v1/projects/%s" % proyecto_id)


def crear_proyecto(c, datos):
    return c.pedir("escenarios", "POST", "/api/v1/projects", datos, "proyecto")


def cambiar_proyecto(c, proyecto_id, cambios):
    return c.pedir("escenarios", "PATCH", "/api/v1/projects/%s" % proyecto_id, cambios, "proyecto")


def archivar_proyecto(c, proyecto_id, archivar=True):
    return c.pedir("escenarios", "POST", "/api/v1/projects/%s/%s" % (proyecto_id, "archive" if archivar else "restore"))


def mover_a_proyecto(c, escenario_id, proyecto_id):
    """proyecto_id None saca el escenario de su proyecto."""
    return c.pedir("escenarios", "PUT", "/api/v1/scenarios/%s/project" % escenario_id,
                   {"project_id": proyecto_id}, "escenario")


def archivar_escenario(c, escenario_id, archivar=True):
    return c.pedir("escenarios", "POST",
                   "/api/v1/scenarios/%s/%s" % (escenario_id, "archive" if archivar else "restore"))


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


def motores_habilitados(c):
    # Los motores que el despliegue acepta (RF-E15). Con un corridas que no responde la ruta, solo los de siempre:
    # abm-gpu no se ofrece sin que el servicio lo anuncie.
    try:
        motores = c.pedir("corridas", "GET", "/api/v1/runs/engines").get("motores") or []
    except api.ErrorServicio:
        return list(config.MOTORES)
    return [m for m in motores if m in config.MOTORES_TODOS] or list(config.MOTORES)


def corridas(c, **filtros):
    params = {"limit": 100}
    params.update({k: v for k, v in filtros.items() if v not in (None, "")})
    return c.pedir("corridas", "GET", "/api/v1/runs", params=params).get("corridas") or []


def corrida(c, corrida_id):
    return c.pedir("corridas", "GET", "/api/v1/runs/%s" % corrida_id)


def resultado_corrida(c, corrida_id):
    return c.pedir("resultados", "GET", "/api/v1/runs/%s/results" % corrida_id)


def escala_corrida(c, corrida_id):
    datos = resultado_corrida(c, corrida_id)
    return {"run_id": corrida_id, "escala": datos.get("escala")}


def corrida_equivalente(c, corrida_id):
    return c.pedir("corridas", "GET", "/api/v1/runs/%s/equivalent" % corrida_id)


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


def subir_reporte(c, run_ids, titulo, pdf):
    """RF-F17, D35: el PDF va tal cual al bucket por evidencias, con su huella para que el servidor la revise."""
    if not pdf.startswith(b"%PDF"):
        raise api.ErrorServicio("El reporte no es un PDF.")
    if len(pdf) > config.MAX_REPORTE_BYTES:
        raise api.ErrorServicio("El reporte pesa más de 20 MB y el servidor no lo aceptaría.")
    run_ids = sorted(set(run_ids))
    if not run_ids:
        raise api.ErrorServicio("El reporte no tiene corridas.")
    if len(run_ids) > config.MAX_CORRIDAS_REPORTE:
        raise api.ErrorServicio("El reporte reúne %d corridas y evidencias admite %d por reporte: compara menos "
                                "versiones o menos semillas para subirlo." % (len(run_ids), config.MAX_CORRIDAS_REPORTE))
    params = {"runs": ",".join(str(x) for x in run_ids)}
    if titulo:
        params["title"] = titulo[:200]
    r = c.enviar("evidencias", "POST", "/api/v1/reports", pdf, params, tipo="application/pdf",
                 cabeceras={"X-Content-SHA256": hashlib.sha256(pdf).hexdigest()})
    return c.leer_respuesta("evidencias", r)


def reportes(c, run_ids=None):
    params = {"runs": ",".join(str(x) for x in run_ids)} if run_ids else None
    return c.pedir("evidencias", "GET", "/api/v1/reports", params=params).get("reportes") or []


def url_reporte(c, reporte_id):
    return c.pedir("evidencias", "GET", "/api/v1/reports/%s/url" % reporte_id)


TIPOS_CONJUNTO = {".csv": "text/csv", ".json": "application/json", ".xml": "application/xml"}
CAMPOS_CONJUNTO = ("code", "name", "disease", "region", "metric", "period", "source", "license", "url", "cutoff")


def leer_conjunto(ruta):
    """El archivo tal cual, con el tipo que le toca por su extensión (D6, D53)."""
    ruta = Path(ruta)
    tipo = TIPOS_CONJUNTO.get(ruta.suffix.lower())
    if tipo is None:
        raise api.ErrorServicio("El archivo debe ser CSV, JSON o XML.")
    contenido = ruta.read_bytes()
    if len(contenido) > config.MAX_CONJUNTO_BYTES:
        raise api.ErrorServicio("El archivo pesa más de 2 MB y el servidor no lo aceptaría.")
    return contenido, tipo


def _metadatos(datos):
    return {k: str(v).strip() for k, v in datos.items() if k in CAMPOS_CONJUNTO and str(v or "").strip()}


def validar_conjunto(c, contenido, tipo, metadatos):
    """Verifica la calidad sin guardar nada: valido, huella, fallas y resumen."""
    r = c.enviar("importacion", "POST", "/api/v1/datasets/validate", contenido, _metadatos(metadatos), tipo=tipo)
    return c.leer_respuesta("importacion", r)


def importar_conjunto(c, contenido, tipo, metadatos):
    """Guarda la versión siguiente de la clave; el mismo archivo con la misma clave regresa la que ya estaba."""
    r = c.enviar("importacion", "POST", "/api/v1/datasets", contenido, _metadatos(metadatos), tipo=tipo)
    datos = c.leer_respuesta("importacion", r)
    datos["ya_existia"] = r.status_code == 200
    return datos


def conjuntos(c, enfermedad=None, region=None):
    params = {k: v for k, v in (("disease", enfermedad), ("region", region)) if v}
    return c.pedir("importacion", "GET", "/api/v1/datasets", params=params or None).get("conjuntos") or []


def puntos_conjunto(c, conjunto_id):
    return c.pedir("importacion", "GET", "/api/v1/datasets/%s/points" % conjunto_id).get("puntos") or []


def avisos(c):
    return c.pedir("notificaciones", "GET", "/api/v1/notifications", params={"limit": 50})


def marcar_leido(c, aviso_id):
    return c.pedir("notificaciones", "POST", "/api/v1/notifications/%s/read" % aviso_id)


def _versiones_motor(c, elegidas):
    pendientes = [r for lista in elegidas.values() for r in lista if r.get("engine") and not r.get("engine_version")]
    if not pendientes:
        return
    with ThreadPoolExecutor(max_workers=6) as grupo:
        for i in range(0, len(pendientes), 6):
            lote = pendientes[i:i + 6]
            trabajos = [grupo.submit(corrida, c, r["id"]) for r in lote]
            for r, trabajo in zip(lote, trabajos):
                try:
                    detalle = trabajo.result()
                    r["engine_version"] = detalle.get("engine_version")
                    r["horizon_days"] = detalle.get("horizon_days")
                except api.SesionCerrada:
                    raise
                except api.ErrorServicio as exc:
                    if exc.status != 404:
                        return


def cargar_comparacion(c, version_ids, metrica, motor=None):
    grupos = {}
    for vid in version_ids:
        grupos[vid] = resumen.una_por_semilla(corridas(c, scenario_version_id=vid, status="completado", engine=motor))
    semillas = resumen.semillas_comunes(grupos)
    if not semillas:
        raise ValueError("Las versiones elegidas no tienen corridas completadas con la misma semilla.")
    elegidas = {vid: [g[s] for s in semillas] for vid, g in grupos.items()}
    ids = [x["id"] for lista in elegidas.values() for x in lista]
    aviso, comparadas = comparar(c, ids)
    recibidas = {x["id"] for x in comparadas}
    semillas = [s for s in semillas if all(g[s]["id"] in recibidas for g in grupos.values())]
    if not semillas:
        raise ValueError("El servicio no devolvió resultados completos para ninguna semilla compartida.")
    elegidas = {vid: [g[s] for s in semillas] for vid, g in grupos.items()}
    ids = [x["id"] for lista in elegidas.values() for x in lista]
    try:
        datos_pareto = pareto(c, ids, metrica)
    except api.ErrorServicio as exc:
        # Sin costo unitario con fuente o supuesto, pareto se niega (regla 8): se compara sin frontera.
        if exc.status != 422:
            raise
        datos_pareto = {"filas": [], "avisos": motivos_sin_costo(str(exc))}
    _versiones_motor(c, elegidas)
    return resumen.armar(elegidas, comparadas, datos_pareto, metrica, aviso)


def motivos_sin_costo(texto):
    motivos = []
    for parte in re.split(r"SIM-\d+ - [^:]*: ", texto):
        parte = parte.strip()
        if parte and parte not in motivos:
            motivos.append(parte)
    return motivos
