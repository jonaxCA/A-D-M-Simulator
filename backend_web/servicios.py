"""Cliente HTTP de la web hacia los microservicios (D36).

La web no va a PostgreSQL, MongoDB ni Redis: cada dato lo pide al servicio dueño, en JSON, con el
JWT de la sesión (D34) y un X-Correlation-ID. La URL de cada servicio sale de
SERVICIO_<NOMBRE>_URL (p. ej. SERVICIO_ESCENARIOS_URL); si no viene, de URL_SERVICIOS con
{servicio} (el contenedor de la web usa http://{servicio}:8000, la red interna); y si tampoco,
la del catálogo en local. No reintenta escrituras.

Las funciones de abajo regresan lo que esperan las plantillas: si el JSON del servicio trae otros
nombres o fechas en texto, la conversión va aquí (inventario C6).
"""
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

log = logging.getLogger(__name__)

# Los puertos del catálogo (docs/arquitectura/microservicios.md).
PUERTOS = {"auth": 5201, "sesiones": 5202, "usuarios": 5203, "roles": 5204,
           "enfermedades": 5211, "parametros": 5212, "regiones": 5213, "poblacion": 5214,
           "tipos-intervencion": 5215, "casos": 5221, "sincronizacion": 5222,
           "dispositivos": 5223, "evidencias": 5224, "vacunas": 5225,
           "escenarios": 5231, "intervenciones": 5232, "aprobacion": 5233, "validacion": 5234,
           "escenarios-xml": 5235, "corridas": 5241, "simulador": 5242, "resultados": 5243,
           "comparacion": 5244, "pareto": 5245, "indicadores": 5251, "series": 5252,
           "zonas": 5253, "notificaciones": 5261, "estado-servicios": 5262}
TIEMPO_ESPERA = 5
TIEMPO_ESPERA_ARCHIVO = 30


class ServicioNoDisponible(Exception):
    """El servicio no respondió, tardó demasiado o respondió 5xx."""

    def __init__(self, servicio):
        super().__init__(servicio)
        self.servicio = servicio


class ErrorServicio(Exception):
    """El servicio respondió un error 4xx (RFC 7807): estado, codigo y detalle."""

    def __init__(self, servicio, estado, codigo=None, detalle=None):
        super().__init__("%s %s %s" % (servicio, estado, codigo))
        self.servicio, self.estado, self.codigo, self.detalle = servicio, estado, codigo, detalle


def _sin_cabeceras():
    return {}


# Las cabeceras de la persona que usa la web (su navegador), para que la bitácora del servicio
# anote el suyo y no el del servidor web (D36). Las pone frontend_web al crear la app: esta capa
# no conoce Flask.
cabeceras_de_la_persona = _sin_cabeceras


def url_base(servicio):
    variable = "SERVICIO_%s_URL" % servicio.upper().replace("-", "_")
    plantilla = os.environ.get("URL_SERVICIOS")
    url = os.environ.get(variable) or (plantilla.format(servicio=servicio) if plantilla else "")
    return (url or "http://localhost:%d" % PUERTOS[servicio]).rstrip("/")


def llamar(servicio, metodo, ruta, token=None, params=None, cuerpo=None, correlacion=None,
           cabeceras=None, archivo=None, tipo=None):
    """El JSON de la respuesta. Levanta ErrorServicio (4xx) o ServicioNoDisponible. `archivo` son
    los bytes que van tal cual en el cuerpo, con su `tipo` (evidencias no recibe formularios)."""
    consulta = dict(params or {}, format="json")
    consulta = {k: v for k, v in consulta.items() if v is not None}
    url = "%s%s?%s" % (url_base(servicio), ruta, urllib.parse.urlencode(consulta))
    enviadas = dict(cabeceras_de_la_persona(), Accept="application/json", **(cabeceras or {}))
    if token:
        enviadas["Authorization"] = "Bearer " + token
    if correlacion:
        enviadas["X-Correlation-ID"] = correlacion
    datos = None
    if cuerpo is not None:
        datos = json.dumps(cuerpo, default=str).encode("utf-8")
        enviadas["Content-Type"] = "application/json"
    elif archivo is not None:
        datos = archivo
        enviadas["Content-Type"] = tipo or "application/octet-stream"
    peticion = urllib.request.Request(url, data=datos, headers=enviadas, method=metodo.upper())
    try:
        with urllib.request.urlopen(
                peticion, timeout=TIEMPO_ESPERA if archivo is None else TIEMPO_ESPERA_ARCHIVO) as respuesta:
            contenido = respuesta.read()
            return json.loads(contenido) if contenido else None
    except urllib.error.HTTPError as error:
        if error.code >= 500:
            log.warning("%s respondió %s en %s %s", servicio, error.code, metodo.upper(), ruta)
            raise ServicioNoDisponible(servicio) from error
        try:
            problema = json.loads(error.read() or b"{}")
        except ValueError:
            problema = {}
        raise ErrorServicio(servicio, error.code, problema.get("codigo"),
                            problema.get("detail")) from error
    except (OSError, ValueError) as error:
        log.warning("%s no responde en %s %s: %s", servicio, metodo.upper(), ruta, error)
        raise ServicioNoDisponible(servicio) from error


def fecha(valor):
    if isinstance(valor, str):
        try:
            return datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except ValueError:
            return valor
    return valor


def con_fechas(filas, *campos):
    """Los servicios mandan las fechas en ISO 8601; las plantillas que usan strftime, datetime."""
    for fila in filas:
        for campo in campos:
            fila[campo] = fecha(fila.get(campo))
    return filas


def _sin_nulos(datos):
    return {k: v for k, v in datos.items() if v not in (None, "")}


# --- Tablero y mapa (D36, paso 5) ----------------------------------------------------------

def indicadores_tablero():
    return llamar("indicadores", "GET", "/api/v1/dashboard/indicators")


def resumen_situacion(limite=5):
    return llamar("indicadores", "GET", "/api/v1/dashboard/situation", params={"limit": limite})["enfermedades"]


def exporta_situacion(token, limite=20):
    """El mismo resumen; indicadores anota el EXPORT con quien lo pidió."""
    return llamar("indicadores", "GET", "/api/v1/dashboard/situation/export", token=token,
                  params={"limit": limite})["enfermedades"]


def curva_tablero():
    return llamar("indicadores", "GET", "/api/v1/dashboard/curve")["puntos"]


def enfermedades_con_casos(token):
    return llamar("zonas", "GET", "/api/v1/zones/diseases", token=token)["enfermedades"]


def mapa(token, disease_id, dias):
    """municipios y la serie del mapa. zonas manda la serie como lista (XML no acepta una etiqueta
    que empiece con dígito); el mapa la lee por clave INEGI."""
    datos = llamar("zonas", "GET", "/api/v1/zones/map", token=token,
                   params={"disease_id": disease_id, "days": dias})
    serie = datos["serie"]
    serie["series"] = {m["region_code"]: m for m in serie.pop("municipios", [])}
    return {"municipios": datos["municipios"], "serie": serie}


def _ambito(disease_id, region_id, dias):
    return {"disease_id": disease_id, "region_id": region_id, "days": dias}


def monitoreo_serie(token, disease_id, region_id, dias):
    return llamar("series", "GET", "/api/v1/series/cases", token=token,
                  params=_ambito(disease_id, region_id, dias))["puntos"]


def monitoreo_edad(token, disease_id, region_id, dias):
    return llamar("series", "GET", "/api/v1/series/cases/by-age", token=token,
                  params=_ambito(disease_id, region_id, dias))["grupos"]


def monitoreo_sexo(token, disease_id, region_id, dias):
    return llamar("series", "GET", "/api/v1/series/cases/by-sex", token=token,
                  params=_ambito(disease_id, region_id, dias))["sexos"]


def monitoreo_totales(token, disease_id, region_id, dias):
    return llamar("series", "GET", "/api/v1/series/cases/totals", token=token,
                  params=_ambito(disease_id, region_id, dias))["totales"]


def monitoreo_zonas(token, disease_id, region_id, dias, busqueda=None, orden="incidencia",
                    pagina=1, por_pagina=10):
    return llamar("zonas", "GET", "/api/v1/zones", token=token,
                  params=dict(_ambito(disease_id, region_id, dias), q=busqueda, order=orden,
                              page=pagina, size=por_pagina))


def exporta_zonas(token, disease_id, region_id, dias, busqueda=None, orden="incidencia"):
    """Todas las zonas del ámbito; zonas anota el EXPORT."""
    return llamar("zonas", "GET", "/api/v1/zones/export", token=token,
                  params=dict(_ambito(disease_id, region_id, dias), q=busqueda, order=orden))


# --- Catálogos (D36, paso 6) ---------------------------------------------------------------

def enfermedades(busqueda=None, estado=None, pagina=1, por_pagina=10):
    datos = llamar("enfermedades", "GET", "/api/v1/diseases",
                   params={"q": busqueda or None, "status": estado or None, "page": pagina,
                           "size": por_pagina})
    for e in datos["enfermedades"]:
        e["alta"] = fecha(e.get("alta"))
    return datos


def exporta_enfermedades(token, busqueda=None, estado=None, pagina=1, por_pagina=100):
    """La lista para descargar; enfermedades anota el EXPORT con quien lo pidió."""
    datos = llamar("enfermedades", "GET", "/api/v1/diseases/export", token=token,
                   params={"q": busqueda or None, "status": estado or None, "page": pagina,
                           "size": por_pagina})
    for e in datos["enfermedades"]:
        e["alta"] = fecha(e.get("alta"))
    return datos


def enfermedades_stats():
    datos = llamar("enfermedades", "GET", "/api/v1/diseases/stats")
    datos["activas_pct"] = round(datos["activas"] / datos["registradas"] * 100) if datos["registradas"] else 0
    return datos


def enfermedad(disease_id):
    """La ficha con sus parámetros (enfermedades y parametros); None si no existe."""
    try:
        ficha = llamar("enfermedades", "GET", "/api/v1/diseases/%d" % disease_id)
    except ErrorServicio as exc:
        if exc.estado == 404:
            return None
        raise
    ficha["default_params"] = llamar("parametros", "GET",
                                     "/api/v1/diseases/%d/parameters" % disease_id)["parametros"]
    return ficha


def crea_enfermedad(token, code, name, description):
    return llamar("enfermedades", "POST", "/api/v1/diseases", token=token,
                  cuerpo={"code": code, "name": name, "description": description or None})["id"]


def edita_enfermedad(token, disease_id, name, description):
    return llamar("enfermedades", "PUT", "/api/v1/diseases/%d" % disease_id, token=token,
                  cuerpo={"name": name, "description": description or None})


def fija_parametros(token, disease_id, parametros):
    return llamar("parametros", "PUT", "/api/v1/diseases/%d/parameters" % disease_id, token=token,
                  cuerpo={"parametros": parametros})


def activa_enfermedad(token, disease_id, activa):
    return llamar("enfermedades", "POST", "/api/v1/diseases/%d/%s"
                  % (disease_id, "activate" if activa else "deactivate"), token=token)


def regiones_catalogo(busqueda=None, orden="nombre", direccion="asc"):
    return llamar("regiones", "GET", "/api/v1/regions",
                  params={"q": busqueda, "order": orden, "direction": direccion})


def estado_nl():
    return llamar("regiones", "GET", "/api/v1/regions/state")


def municipios_catalogo():
    """Los 51 municipios para los selectores, como {id, name}."""
    return [{"id": m["id"], "name": m["nombre"]} for m in regiones_catalogo()["municipios"]]


def municipio(region_id):
    try:
        return llamar("regiones", "GET", "/api/v1/regions/%d" % region_id)
    except ErrorServicio as exc:
        if exc.estado == 404:
            return None
        raise


def grupos_edad_municipio(region_id):
    try:
        return llamar("poblacion", "GET", "/api/v1/regions/%d/age-groups" % region_id)
    except ErrorServicio as exc:
        if exc.estado == 404:
            return None
        raise


def corrige_poblacion(token, region_id, poblacion, esperada, motivo):
    """El resultado de poblacion: municipio, estado_actualizado y municipios_sin_poblacion."""
    return llamar("poblacion", "PUT", "/api/v1/regions/%d/population" % region_id, token=token,
                  cuerpo={"population": poblacion, "expected_population": esperada, "reason": motivo})


def corrige_grupos_edad(token, region_id, grupos, esperados, motivo):
    return llamar("poblacion", "PUT", "/api/v1/regions/%d/age-groups" % region_id, token=token,
                  cuerpo={"groups": grupos, "expected_groups": esperados, "reason": motivo})


# --- Escenarios y aprobación (D36, paso 2) -------------------------------------------------

def escenarios(token, busqueda=None):
    return llamar("escenarios", "GET", "/api/v1/scenarios", token=token,
                  params={"q": busqueda})["escenarios"]


def escenario_detalle(token, scenario_id, version_number=None):
    """La forma de queries.get_escenario_detalle; None si no existe el escenario o la versión."""
    try:
        datos = llamar("escenarios", "GET", "/api/v1/scenarios/%d" % scenario_id, token=token,
                       params={"version": version_number})
    except ErrorServicio as exc:
        if exc.estado == 404:
            return None
        raise
    version = datos.pop("version")
    if version:
        version["population_by_age"] = {g["grupo"]: g["poblacion"]
                                        for g in version.pop("grupos_edad", [])} or None
        for campo in ("created_at", "submitted_at", "reviewed_at"):
            version[campo] = fecha(version.get(campo))
    return {"escenario": datos, "version": version, "intervenciones": datos.pop("intervenciones"),
            "editable": datos.pop("editable", False),
            "parametros_congelados": datos.pop("parametros_congelados", False),
            "parametros_sin_congelar": datos.pop("parametros_sin_congelar", False)}


def versiones(token, scenario_id):
    datos = llamar("escenarios", "GET", "/api/v1/scenarios/%d/versions" % scenario_id, token=token)
    return con_fechas(datos["versiones"], "created_at")


def todas_las_versiones(token):
    return llamar("escenarios", "GET", "/api/v1/scenarios/versions", token=token)["versiones"]


def intervenciones_version(token, version_id):
    return llamar("intervenciones", "GET", "/api/v1/versions/%d/interventions" % version_id,
                  token=token)["intervenciones"]


def revisa_version(token, version_id):
    """(errores, avisos) del motor para la versión (servicio validacion)."""
    datos = llamar("validacion", "GET", "/api/v1/versions/%d/validation" % version_id, token=token)
    return list(datos.get("errores") or []), list(datos.get("avisos") or [])


def pendientes_revision(token):
    datos = llamar("aprobacion", "GET", "/api/v1/reviews/pending", token=token)
    return con_fechas(datos["pendientes"], "submitted_at")


def revisar(token, scenario_id, decision, comentario):
    """El estado nuevo de la versión ('aprobado' o 'rechazado'). aprobacion valida, impide
    revisar la versión propia, audita y avisa al autor; un rechazo suyo sube como ErrorServicio."""
    datos = llamar("aprobacion", "POST", "/api/v1/scenarios/%d/review" % scenario_id, token=token,
                   cuerpo={"decision": decision, "comentario": comentario or ""})
    return datos["status"]


# --- Corridas y resultados (D36, paso 3) ---------------------------------------------------

def corridas(token, limite=20, estado=None):
    datos = llamar("corridas", "GET", "/api/v1/runs", token=token,
                   params={"limit": limite, "status": estado})
    return con_fechas(datos["corridas"], "queued_at", "started_at", "finished_at")


def corrida(token, run_id):
    try:
        datos = llamar("corridas", "GET", "/api/v1/runs/%d" % run_id, token=token)
    except ErrorServicio as exc:
        if exc.estado == 404:
            return None
        raise
    return con_fechas([datos], "queued_at", "started_at", "finished_at")[0]


def resultado(token, run_id):
    """Resumen, serie, trazabilidad, escala y categoría de una corrida (resultados).

    Si MongoDB no responde, /results da 503: entonces se piden los indicadores, que siguen, y la
    serie queda en None (RF-F21)."""
    try:
        return llamar("resultados", "GET", "/api/v1/runs/%d/results" % run_id, token=token)
    except ServicioNoDisponible:
        datos = llamar("resultados", "GET", "/api/v1/runs/%d/indicators" % run_id, token=token)
        return dict(datos, serie=None, trazabilidad=[], escala=None, engine_version=None)


def corrida_equivalente(token, run_id):
    datos = llamar("corridas", "GET", "/api/v1/runs/%d/equivalent" % run_id, token=token)
    return datos["equivalente"]


def comparacion(token, run_ids):
    datos = llamar("comparacion", "GET", "/api/v1/comparisons", token=token,
                   params={"runs": ",".join(str(i) for i in run_ids)})
    return datos["corridas"]


def pareto(token, run_ids, metrica="fallecimientos"):
    return llamar("pareto", "GET", "/api/v1/pareto", token=token,
                  params={"runs": ",".join(str(i) for i in run_ids), "metric": metrica})


# --- Archivos en el bucket: fotos de los casos y reportes de una comparación (D30, D35) ---------

def evidencias_caso(token, case_id):
    return con_fechas(llamar("evidencias", "GET", "/api/v1/cases/%d/attachments" % case_id,
                             token=token)["evidencias"], "uploaded_at")


def url_evidencia(token, evidencia_id):
    return llamar("evidencias", "GET", "/api/v1/attachments/%d/url" % evidencia_id, token=token)


def reportes_comparacion(token, run_ids=None):
    params = {"runs": ",".join(str(i) for i in run_ids)} if run_ids else None
    return con_fechas(llamar("evidencias", "GET", "/api/v1/reports", token=token,
                             params=params)["reportes"], "uploaded_at")


def url_reporte(token, reporte_id):
    return llamar("evidencias", "GET", "/api/v1/reports/%d/url" % reporte_id, token=token)


def sube_reporte(token, run_ids, titulo, pdf, huella):
    """El PDF tal cual, con su SHA-256 para que evidencias revise que llegó completo (RNF-C09)."""
    return llamar("evidencias", "POST", "/api/v1/reports", token=token, archivo=pdf,
                  tipo="application/pdf", cabeceras={"X-Content-SHA256": huella},
                  params=_sin_nulos({"runs": ",".join(str(i) for i in run_ids), "title": titulo}))


# --- Vigilancia: casos y campañas (C7) -----------------------------------------------------

def casos(token, disease_id=None, region_id=None, estado=None, desde=None, hasta=None,
          pagina=1, por_pagina=20):
    return llamar("casos", "GET", "/api/v1/cases", token=token,
                  params=_sin_nulos({"disease_id": disease_id, "region_id": region_id,
                                     "status": estado, "from": desde, "to": hasta,
                                     "page": pagina, "per_page": por_pagina}))


def caso(token, case_id):
    try:
        return llamar("casos", "GET", "/api/v1/cases/%d" % case_id, token=token)
    except ErrorServicio as exc:
        if exc.estado == 404:
            return None
        raise


def historial_caso(token, case_id):
    datos = llamar("casos", "GET", "/api/v1/cases/%d/history" % case_id, token=token)
    return datos.get("cambios", datos.get("historial", [])) if isinstance(datos, dict) else datos


def cambia_estado_caso(token, case_id, version, estado, motivo, duplicado_de=None):
    cuerpo = _sin_nulos({"status": estado, "reason": motivo, "duplicate_of": duplicado_de})
    return llamar("casos", "POST", "/api/v1/cases/%d/status" % case_id, token=token,
                  cuerpo=cuerpo, cabeceras={"If-Match": '"%s"' % version})


def campanas(token, estado=None, limite=100):
    return llamar("vacunas", "GET", "/api/v1/campaigns", token=token,
                  params={"status": estado, "limit": limite})["campanas"]


def crea_campana(token, datos):
    return llamar("vacunas", "POST", "/api/v1/campaigns", token=token, cuerpo=_sin_nulos(datos))


def cancela_campana(token, campana_id, motivo):
    return llamar("vacunas", "POST", "/api/v1/campaigns/%d/cancel" % campana_id, token=token,
                  cuerpo={"reason": motivo})


# --- Administración (D36, paso 7) ----------------------------------------------------------

def usuarios(token, busqueda=None, rol_id=None, estado=None):
    return llamar("usuarios", "GET", "/api/v1/users", token=token,
                  params={"q": busqueda, "role_id": rol_id, "status": estado})["usuarios"]


def usuarios_resumen(token):
    return llamar("usuarios", "GET", "/api/v1/users/summary", token=token)


def usuario(token, user_id):
    try:
        return llamar("usuarios", "GET", "/api/v1/users/%d" % user_id, token=token)
    except ErrorServicio as exc:
        if exc.estado == 404:
            return None
        raise


def roles(token):
    return llamar("roles", "GET", "/api/v1/roles", token=token)["roles"]


def instituciones(token):
    return llamar("usuarios", "GET", "/api/v1/institutions", token=token)["instituciones"]


def crea_usuario(token, datos, password, role_id):
    """usuarios da de alta la cuenta y roles le asigna el rol (cada uno audita lo suyo)."""
    ficha = llamar("usuarios", "POST", "/api/v1/users", token=token,
                   cuerpo=dict(datos, password=password))
    asigna_rol(token, ficha["id"], role_id)
    return ficha["id"]


def edita_usuario(token, user_id, datos, password, role_id, activo, activo_antes, rol_antes):
    cuerpo = dict(datos)
    if password:
        cuerpo["password"] = password
    llamar("usuarios", "PUT", "/api/v1/users/%d" % user_id, token=token, cuerpo=cuerpo)
    if role_id != rol_antes:
        asigna_rol(token, user_id, role_id)
    if activo != activo_antes:
        activa_usuario(token, user_id, activo)


def asigna_rol(token, user_id, role_id):
    return llamar("roles", "PUT", "/api/v1/roles/assignments/%d" % user_id, token=token,
                  cuerpo={"role_id": role_id})


def activa_usuario(token, user_id, activo):
    return llamar("usuarios", "POST", "/api/v1/users/%d/%s"
                  % (user_id, "activate" if activo else "deactivate"), token=token)


def elimina_usuario(token, user_id):
    return llamar("usuarios", "DELETE", "/api/v1/users/%d" % user_id, token=token)


def bitacora(token, busqueda=None, usuario_id=None, modulo=None, accion=None, limite=100):
    return llamar("roles", "GET", "/api/v1/audit", token=token,
                  params={"q": busqueda, "user_id": usuario_id, "module": modulo, "action": accion,
                          "limit": limite})["eventos"]


def bitacora_resumen(token):
    return llamar("roles", "GET", "/api/v1/audit/summary", token=token)


def bitacora_filtros(token):
    return llamar("roles", "GET", "/api/v1/audit/filters", token=token)


# --- Avisos (RF-D15, RF-C19) ---------------------------------------------------------------

def avisos(token, solo_no_leidas=False, limite=50):
    datos = llamar("notificaciones", "GET", "/api/v1/notifications", token=token,
                   params={"unread": "true" if solo_no_leidas else None, "limit": limite}) or {}
    return (con_fechas(list(datos.get("notificaciones") or []), "created_at", "read_at"),
            datos.get("no_leidas") or 0)


def marca_aviso_leido(token, aviso_id):
    return llamar("notificaciones", "POST", "/api/v1/notifications/%d/read" % aviso_id, token=token)


# --- Costos de intervención (D3, D36) ------------------------------------------------------

def tipos_intervencion():
    return llamar("tipos-intervencion", "GET", "/api/v1/intervention-types")["tipos"]


def fija_costo_tipo(token, tipo_id, valor, fuente, supuesto):
    return llamar("intervenciones", "PUT", "/api/v1/intervention-types/%d/cost" % tipo_id, token=token,
                  cuerpo={"unit_cost": valor or "", "cost_source": (fuente or "").strip() or None,
                          "cost_is_assumption": supuesto})


def fija_personas_dia_tipo(token, tipo_id, valor, fuente, supuesto):
    return llamar("intervenciones", "PUT", "/api/v1/intervention-types/%d/person-days" % tipo_id,
                  token=token,
                  cuerpo={"person_days_per_unit": valor or "",
                          "person_days_source": (fuente or "").strip() or None,
                          "person_days_is_assumption": supuesto})
