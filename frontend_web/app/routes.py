"""Rutas de la web (D36): cada pantalla pide sus datos a los servicios.

La web no tiene SQL ni credenciales de PostgreSQL, MongoDB o Redis. backend_web/servicios.py es
el cliente HTTP; la bitácora la escribe el servicio que hace cada cambio. Crear y editar
escenarios, enviarlos a revisión y lanzar corridas es de la app de escritorio (D4): aquí se
consulta y se aprueba. Cada ruta lleva requiere_permiso con su permiso de la matriz (D1); solo el
tablero y el mapa, que ven todos los roles, usan login_required.
"""
import csv
import io
import secrets
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

from flask import (Blueprint, current_app, jsonify, render_template, request, redirect,
                   url_for, make_response, g, flash, session)

from backend_web import catalogo, formato, servicios
from backend_web.servicios import ErrorServicio, ServicioNoDisponible

from . import formularios, presentacion, sesion_servicios
from .sesion_servicios import COOKIE_REFRESH, MENSAJE_CREDENCIALES, MENSAJE_SIN_SESIONES
from .permisos import (login_required, requiere_permiso, tiene_permiso, get_current_user,
                       token_de_sesion, COOKIE_NAME)

bp = Blueprint("main", __name__)

COOKIE_DISPOSITIVO = "dispositivo_web"

# Las exportaciones bajan todo lo que pasa el filtro de la pantalla; enfermedades pagina de 100.
EXPORT_POR_PAGINA = 100
MENSAJE_NO_GUARDADO = "El cambio no se guardó."


def seccion(servicio, funcion, *args, defecto=None, **kwargs):
    """Lo que regresa `funcion`, o `defecto` si su servicio no responde. La pantalla sigue y el
    aviso de base_app.html dice qué servicio faltó (D36)."""
    try:
        return funcion(*args, **kwargs)
    except ServicioNoDisponible as exc:
        caidos = g.setdefault("servicios_caidos", [])
        if exc.servicio not in caidos:
            caidos.append(exc.servicio)
        return defecto


def _falla_de_escritura(exc):
    """El texto de un rechazo del servicio para un formulario. 401 y 403 suben a su manejador."""
    if exc.estado in (401, 403):
        raise exc
    return exc.detalle or "El servicio rechazó el cambio."


@bp.app_context_processor
def inject_globals():
    # Solo pintan u ocultan opciones; el control real es requiere_permiso en cada ruta.
    try:
        user = get_current_user()
    except ServicioNoDisponible:
        user = None

    def puede(codigo=None):
        return tiene_permiso(user, codigo)

    def avisos_sin_leer():
        # La campana no tumba la página: sin notificaciones, no muestra número.
        try:
            return servicios.avisos(token_de_sesion(), True, 1)[1]
        except (ServicioNoDisponible, ErrorServicio):
            return 0

    return {
        "current_user": user,
        "now": datetime.now(timezone.utc),
        "puede": puede,
        "avisos_sin_leer": avisos_sin_leer,
        "servicios_caidos": g.get("servicios_caidos", []),
        "es_admin": puede("users.read"),
        "puede_editar_catalogo": puede("catalogs.update"),
        # Aprobar o rechazar (scenarios.approve): EPIDEMIOLOGO y ADMINISTRADOR, nunca la suya.
        "puede_revisar": puede("scenarios.approve"),
        "ve_bandeja": puede("scenarios.approve"),
        "ve_simulaciones": puede("simulations.read"),
        "ve_escenarios": puede("scenarios.read"),
        # Aviso obligatorio en simulacion, resultados y comparacion.
        "aviso_simulacion": formato.AVISO_SIMULACION,
    }


@bp.route("/health")
def salud():
    """Para el healthcheck del contenedor: el proceso responde. No llama a los servicios, para
    que la web no se reinicie cuando uno de ellos cae."""
    return {"servicio": "web", "estado": "ok"}


# ---------------------------------------------------------------------------
# Tablero público y tablero -- indicadores (RF-G11: lo ven todos los roles)
# ---------------------------------------------------------------------------
INDICADORES_VACIOS = {"casos_activos": 0, "casos_pct": 0, "tasa_incidencia": 0, "tasa_pct": 0,
                      "zonas_en_riesgo": 0, "simulaciones_activas": 0, "indicadores": []}


def _panorama():
    return {
        "indicadores": seccion("indicadores", servicios.indicadores_tablero, defecto=INDICADORES_VACIOS),
        "situacion": seccion("indicadores", servicios.resumen_situacion, defecto=[]),
        "curva": seccion("indicadores", servicios.curva_tablero, defecto=[]),
    }


@bp.route("/")
def dashboard_publico():
    try:
        if get_current_user():
            return redirect(url_for("main.dashboard"))
    except ServicioNoDisponible:
        pass
    return render_template("dashboard_publico.html", report_link=url_for("main.login"),
                           **_panorama())


# ---------------------------------------------------------------------------
# Login y logout -- auth y sesiones (D36)
# ---------------------------------------------------------------------------
def destino_seguro(destino):
    """`destino` si es una ruta de ESTE sitio; None si no (evita el redirect abierto)."""
    if not destino or not destino.startswith("/"):
        return None
    if destino.startswith(("//", "/\\")) or "\\" in destino:
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in destino):
        return None
    partes = urlsplit(destino)
    if partes.scheme or partes.netloc:
        return None
    return destino


def _pantalla_login(error, usuario, estado=200):
    # Cada intento lleva su captcha nuevo: auth lo borra al usarse, acierte o no.
    return render_template("login.html", error=error, usuario=usuario,
                           captcha=sesion_servicios.captcha()), estado


@bp.route("/login", methods=["GET", "POST"])
def login():
    # auth revisa captcha y contraseña y audita LOGIN y LOGIN_FAILED; la web guarda los tokens.
    if request.method == "GET":
        try:
            if get_current_user():
                return redirect(url_for("main.dashboard"))
        except ServicioNoDisponible:
            pass
        return _pantalla_login(None, "")

    usuario = (request.form.get("usuario") or "").strip()
    # Identifica a este navegador ante sesiones (D41); solo se manda si auth lo exige.
    dispositivo = request.cookies.get(COOKIE_DISPOSITIVO) or secrets.token_urlsafe(24)
    try:
        datos = sesion_servicios.iniciar(usuario, request.form.get("password") or "",
                                         request.form.get("captcha_id") or "",
                                         request.form.get("captcha_respuesta") or "", dispositivo)
    except ServicioNoDisponible:
        return _pantalla_login(MENSAJE_SIN_SESIONES, usuario, 503)
    except ErrorServicio as exc:
        credenciales = exc.estado in (400, 401, 422)
        mensaje = MENSAJE_CREDENCIALES if credenciales else (exc.detalle or MENSAJE_CREDENCIALES)
        return _pantalla_login(mensaje, usuario, 401 if credenciales else exc.estado)
    next_url = destino_seguro(request.args.get("next")) or url_for("main.dashboard")
    if datos.get("mfa_requerido"):
        # El token de MFA vive 5 minutos; el secreto TOTP nunca pasa por la sesión.
        session["mfa"] = {"token": datos["mfa_token"], "enrolado": datos.get("mfa_enrolado", False),
                          "next": next_url}
        resp = make_response(redirect(url_for("main.login_mfa")))
    else:
        resp = _con_tokens(make_response(redirect(next_url)), datos)
    resp.set_cookie(COOKIE_DISPOSITIVO, dispositivo, httponly=True, secure=request.is_secure,
                    samesite="Lax", max_age=60 * 60 * 24 * 365)
    return resp


def _con_tokens(resp, datos):
    for nombre, valor in ((COOKIE_NAME, datos["access_token"]), (COOKIE_REFRESH, datos["refresh_token"])):
        resp.set_cookie(nombre, valor, httponly=True, secure=request.is_secure, samesite="Lax",
                        max_age=60 * 60 * 8)
    return resp


MENSAJES_MFA = {
    "MFA_CODIGO_INVALIDO": "El código no es correcto. Revisa la hora de tu teléfono e intenta de nuevo.",
    "MFA_TOKEN_INVALIDO": "El paso de verificación venció. Inicia sesión otra vez.",
}


@bp.route("/login/mfa", methods=["GET", "POST"])
def login_mfa():
    """El segundo paso de los perfiles críticos (D40): verificar el código, o enrolarse con el código
    de alta y confirmar. auth valida, cuenta los intentos, bloquea y audita."""
    pendiente = session.get("mfa")
    if not pendiente:
        return redirect(url_for("main.login"))

    def pantalla(paso, error=None, estado=200, **extra):
        return render_template("login_mfa.html", paso=paso, error=error, **extra), estado

    paso_inicial = "verificar" if pendiente["enrolado"] else "enrolar"
    if request.method == "GET":
        return pantalla(paso_inicial)

    accion = request.form.get("accion")
    try:
        if accion == "enrolar":
            alta = (request.form.get("codigo_alta") or "").strip()
            datos = sesion_servicios.mfa("enroll", pendiente["token"],
                                         **({"codigo_alta": alta} if alta else {}))
            return pantalla("confirmar", secreto=datos["secreto"], uri=datos["uri"],
                            algoritmo=datos.get("algoritmo"), digitos=datos.get("digitos"),
                            periodo=datos.get("periodo"))
        if accion not in ("verificar", "confirmar"):
            return pantalla(paso_inicial, "Elige una opción del formulario.", 400)
        datos = sesion_servicios.mfa("verify" if accion == "verificar" else "confirm", pendiente["token"],
                                     codigo=(request.form.get("codigo") or "").strip())
    except ServicioNoDisponible:
        return pantalla(paso_inicial, MENSAJE_SIN_SESIONES, 503)
    except ErrorServicio as exc:
        if exc.codigo == "MFA_TOKEN_INVALIDO":
            session.pop("mfa", None)
            flash(MENSAJES_MFA[exc.codigo], "error")
            return redirect(url_for("main.login"))
        paso = "verificar" if accion == "verificar" else paso_inicial
        return pantalla(paso, MENSAJES_MFA.get(exc.codigo) or exc.detalle or "No se pudo verificar.",
                        exc.estado if exc.estado in (401, 403, 409, 422, 429) else 400)

    if datos.get("codigos_respaldo"):
        resp = make_response(render_template("login_mfa.html", paso="respaldos", error=None,
                                             codigos=datos["codigos_respaldo"],
                                             siguiente=pendiente["next"]))
    else:
        resp = make_response(redirect(pendiente["next"]))
    return _con_tokens(resp, datos)


@bp.route("/logout")
def logout():
    # sesiones revoca el access, cierra la sesión y audita LOGOUT.
    sesion_servicios.cerrar(request.cookies.get(COOKIE_NAME))
    resp = make_response(redirect(url_for("main.dashboard_publico")))
    resp.delete_cookie(COOKIE_NAME)
    resp.delete_cookie(COOKIE_REFRESH)
    return resp


@bp.route("/dashboard")
@login_required
def dashboard():
    enlace = (url_for("main.export_resumen_csv") if tiene_permiso(g.user, "reports.export")
              else url_for("main.mapa"))
    return render_template("dashboard.html", active_nav="dashboard", report_link=enlace,
                           **_panorama())


# ---------------------------------------------------------------------------
# Mapa epidemiológico -- zonas (RF-G11: lo ven todos los roles)
# ---------------------------------------------------------------------------
PERIODOS_MAPA = (7, 30, 60)


def _filtros_mapa():
    dias = request.args.get("dias", default=30, type=int)
    return (request.args.get("enfermedad", default=None, type=int),
            dias if dias in PERIODOS_MAPA else 30)


@bp.route("/mapa")
@login_required
def mapa():
    disease_id, dias = _filtros_mapa()
    enfermedades = seccion("zonas", servicios.enfermedades_con_casos, token_de_sesion(), defecto=[])
    return render_template("mapa.html", enfermedades=enfermedades, dias=dias,
                           disease_id=disease_id, active_nav="mapa")


@bp.route("/api/mapa")
@login_required
def api_mapa():
    disease_id, dias = _filtros_mapa()
    try:
        return servicios.mapa(token_de_sesion(), disease_id, dias)
    except ServicioNoDisponible as exc:
        return jsonify({"error": "Este dato no está disponible por ahora (servicio «%s»)."
                                 % exc.servicio}), 503


# ---------------------------------------------------------------------------
# Catálogo de enfermedades -- enfermedades y parametros
# ---------------------------------------------------------------------------
def _filtros_enfermedades(args):
    """Los filtros de la pantalla; los comparten la vista y el export."""
    estado = args.get("estado") or ""
    return {
        "busqueda": (args.get("q") or "").strip(),
        "estado": estado if estado in ("activa", "inactiva") else "",
    }


def _filtros_url(filtros):
    nombres = {"busqueda": "q", "estado": "estado"}
    return {nombres[k]: v for k, v in filtros.items() if v}


LISTADO_VACIO = {"enfermedades": [], "total": 0, "pagina": 1, "por_pagina": 10, "paginas": 1,
                 "desde": 0, "hasta": 0}
STATS_VACIAS = {"registradas": 0, "altas_30d": 0, "activas": 0, "activas_pct": 0,
                "inactivas": 0, "detectadas_30d": 0}


@bp.route("/enfermedades")
@requiere_permiso("catalogs.read", "diseases")
def enfermedades():
    filtros = _filtros_enfermedades(request.args)
    pagina = max(1, request.args.get("pagina", default=1, type=int))
    return render_template(
        "enfermedades.html",
        stats=seccion("enfermedades", servicios.enfermedades_stats, defecto=STATS_VACIAS),
        listado=seccion("enfermedades", servicios.enfermedades, filtros["busqueda"],
                        filtros["estado"], pagina, defecto=LISTADO_VACIO),
        filtros=filtros, filtros_url=_filtros_url(filtros), active_nav="enfermedades")


def _form_enfermedad(enfermedad, params, errores, estado=200):
    return render_template("enfermedad_form.html", enfermedad=enfermedad,
                           parametros=catalogo.estado_parametros(params), errores=errores,
                           active_nav="enfermedades"), estado


@bp.route("/enfermedades/nueva", methods=["GET", "POST"])
@requiere_permiso("catalogs.create", "diseases")
def enfermedad_nueva():
    """Alta en el catálogo (EPIDEMIOLOGO y ADMINISTRADOR, D1). enfermedades da de alta la ficha
    y parametros guarda R0, letalidad y demás, cada uno con su bitácora."""
    if request.method == "GET":
        return _form_enfermedad(None, {}, [])

    datos = {"code": catalogo.normaliza_codigo(request.form.get("code")),
             "name": (request.form.get("name") or "").strip(),
             "description": (request.form.get("description") or "").strip()}
    params, errores = catalogo.parametros_desde_form(request.form)
    errores = catalogo.valida_enfermedad(datos["code"], datos["name"]) + errores
    if errores:
        return _form_enfermedad(datos, params, errores, 400)

    token = token_de_sesion()
    try:
        nuevo_id = servicios.crea_enfermedad(token, datos["code"], datos["name"], datos["description"])
    except ErrorServicio as exc:
        return _form_enfermedad(datos, params, [_falla_de_escritura(exc)], 400)
    if params:
        try:
            servicios.fija_parametros(token, nuevo_id, params)
        except (ErrorServicio, ServicioNoDisponible) as exc:
            detalle = exc.detalle if isinstance(exc, ErrorServicio) else "el servicio parametros no respondió"
            flash(f"«{datos['name']}» quedó registrada, pero sus parámetros no se guardaron: "
                  f"{detalle}. Captúralos al editarla.", "warn")
            return redirect(url_for("main.enfermedad_editar", disease_id=nuevo_id))
    flash(f"Enfermedad «{datos['name']}» registrada con el código {datos['code']}.", "ok")
    return redirect(url_for("main.enfermedades"))


@bp.route("/enfermedades/<int:disease_id>/editar", methods=["GET", "POST"])
@requiere_permiso("catalogs.update", "diseases")
def enfermedad_editar(disease_id):
    """El código no se edita: es la llave con la que están ligados casos y escenarios."""
    actual = servicios.enfermedad(disease_id)
    if not actual:
        flash("Esa enfermedad ya no existe en el catálogo.", "error")
        return redirect(url_for("main.enfermedades"))
    if request.method == "GET":
        return _form_enfermedad(actual, actual["default_params"], [])

    datos = {"name": (request.form.get("name") or "").strip(),
             "description": (request.form.get("description") or "").strip()}
    params, errores = catalogo.parametros_desde_form(request.form, actual["default_params"])
    errores = catalogo.valida_enfermedad(actual["code"], datos["name"]) + errores
    vista = {**actual, **datos}
    if errores:
        return _form_enfermedad(vista, params, errores, 400)

    token = token_de_sesion()
    try:
        servicios.edita_enfermedad(token, disease_id, datos["name"], datos["description"])
        if params != (actual["default_params"] or {}):
            servicios.fija_parametros(token, disease_id, params)
    except ErrorServicio as exc:
        return _form_enfermedad(vista, params, [_falla_de_escritura(exc)], 400)
    flash(f"«{datos['name']}» actualizada.", "ok")
    return redirect(url_for("main.enfermedades"))


@bp.route("/enfermedades/<int:disease_id>/estado", methods=["POST"])
@requiere_permiso("catalogs.update", "diseases")
def enfermedad_estado(disease_id):
    """Baja y alta lógica: nunca borra, los casos apuntan a la enfermedad."""
    actual = servicios.enfermedad(disease_id)
    if not actual:
        flash("Esa enfermedad ya no existe en el catálogo.", "error")
        return redirect(url_for("main.enfermedades"))
    activa = request.form.get("activa") == "1"
    try:
        servicios.activa_enfermedad(token_de_sesion(), disease_id, activa)
    except ErrorServicio as exc:
        flash(_falla_de_escritura(exc), "error")
        return redirect(url_for("main.enfermedades"))
    flash(f"«{actual['name']}» quedó {'activa' if activa else 'inactiva'} en el catálogo.", "ok")
    return redirect(destino_seguro(urlsplit(request.referrer or "").path) or url_for("main.enfermedades"))


# Una hoja de cálculo lee como fórmula la celda que empieza con alguno de estos caracteres.
_INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _celda_csv(valor):
    """El texto que una hoja de cálculo leería como fórmula lleva un apóstrofo (OWASP)."""
    if isinstance(valor, str) and valor.startswith(_INICIO_DE_FORMULA):
        return "'" + valor
    return valor


def _csv(nombre_archivo, encabezados, filas):
    """Descarga CSV en UTF-8 con BOM, para que Excel en Windows lea bien los acentos."""
    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf)
    writer.writerow(encabezados)
    writer.writerows([_celda_csv(v) for v in fila] for fila in filas)
    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = f"attachment; filename={nombre_archivo}"
    return resp


@bp.route("/export/enfermedades.csv")
@requiere_permiso("reports.export", "reports")
def export_enfermedades_csv():
    filtros = _filtros_enfermedades(request.args)
    filas, pagina = [], 1
    while True:
        listado = servicios.enfermedades(filtros["busqueda"], filtros["estado"], pagina, EXPORT_POR_PAGINA)
        filas += listado["enfermedades"]
        if pagina >= listado["paginas"]:
            break
        pagina += 1
    return _csv(
        "catalogo_enfermedades.csv",
        ["Código", "Enfermedad", "Estado", "Actividad", "Alta en catálogo",
         "Casos NL (total)", "Casos NL (30 días)",
         "Simulable", "Parámetros faltantes", "Parámetros supuestos"],
        ([e["code"], e["nombre"], presentacion.estado_catalogo(e["activa"]),
          presentacion.actividad_etiqueta(e["actividad"]), presentacion.fecha_corta(e["alta"]),
          e["casos_total"], e["casos_30d"],
          "Sí" if e["parametros"]["simulable"] else "No",
          len(e["parametros"]["faltan"]), len(e["parametros"]["supuestos"])]
         for e in filas),
    )


@bp.route("/export/resumen.csv")
@requiere_permiso("reports.export", "reports")
def export_resumen_csv():
    situacion = servicios.exporta_situacion(token_de_sesion(), 20)
    return _csv(
        "resumen_situacion.csv",
        ["Enfermedad", "Estado", "Casos (7 dias)"],
        ([row["enfermedad"], presentacion.tendencia_etiqueta(row["estado"]), row["incidencia"]]
         for row in situacion),
    )


# ---------------------------------------------------------------------------
# Regiones -- regiones y poblacion. Corregir población es solo del ADMINISTRADOR.
# ---------------------------------------------------------------------------
CATALOGO_VACIO = {"municipios": [], "total": 0, "busqueda": "", "orden": "nombre", "direccion": "asc"}


@bp.route("/regiones")
@requiere_permiso("catalogs.read", "regions")
def regiones():
    busqueda = (request.args.get("q") or "").strip() or None
    orden = request.args.get("orden") or "nombre"
    direccion = request.args.get("dir") or "asc"
    if orden not in ("nombre", "poblacion", "poblacion_60"):
        orden = "nombre"
    if direccion not in ("asc", "desc"):
        direccion = "asc"
    return render_template(
        "regiones.html",
        estado=seccion("regiones", servicios.estado_nl),
        catalogo=seccion("regiones", servicios.regiones_catalogo, busqueda, orden, direccion,
                         defecto=dict(CATALOGO_VACIO, busqueda=busqueda or "")),
        active_nav="regiones")


@bp.route("/regiones/<int:region_id>/editar", methods=["GET", "POST"])
@requiere_permiso("settings.update", "regions")
def region_editar(region_id):
    """Corrección manual de la población total de un municipio (poblacion valida, guarda,
    recalcula el estado y audita). El 60+ se deriva de los grupos de edad (022)."""
    municipio = servicios.municipio(region_id)
    if not municipio:
        flash("Ese municipio ya no existe en el catálogo.", "error")
        return redirect(url_for("main.regiones"))

    if request.method == "GET":
        return render_template("region_form.html", municipio=municipio, errores=[],
                               valores={"population": municipio["population"], "motivo": ""},
                               active_nav="regiones")

    valores = {"population": request.form.get("population"), "motivo": request.form.get("motivo") or ""}
    esperado, ok_pob = formularios.esperado(request.form, "esperado_population")
    if not ok_pob:
        errores = ["No se pudo verificar el estado del formulario. Recarga la página e intenta de nuevo."]
    else:
        try:
            resultado = servicios.corrige_poblacion(token_de_sesion(), region_id,
                                                    valores["population"], esperado, valores["motivo"])
            errores = []
        except ErrorServicio as exc:
            errores = [_falla_de_escritura(exc)]
    if errores:
        return render_template("region_form.html", municipio=municipio, errores=errores,
                               valores=valores, active_nav="regiones"), 400

    mensaje = f"Población de «{resultado['municipio']}» actualizada."
    if resultado["estado_actualizado"]:
        mensaje += " El total de Nuevo León se recalculó con la suma de sus 51 municipios."
    flash(mensaje, "ok")
    if resultado["municipios_sin_poblacion"]:
        flash(f"El total de población de Nuevo León no se recalculó: "
              f"{resultado['municipios_sin_poblacion']} municipio(s) no tienen ese dato capturado.",
              "warn")
    return redirect(url_for("main.regiones"))


GRUPOS_FORM = (("0-19", "grupo_0_19", "esperado_0_19"), ("20-39", "grupo_20_39", "esperado_20_39"),
               ("40-59", "grupo_40_59", "esperado_40_59"), ("60-79", "grupo_60_79", "esperado_60_79"),
               ("80+", "grupo_80_mas", "esperado_80_mas"))


@bp.route("/regiones/<int:region_id>/edades", methods=["GET", "POST"])
@requiere_permiso("settings.update", "regions")
def region_edades_editar(region_id):
    """Corrige las bandas de edad de un municipio; el 60+ se deriva de 60-79 y 80+."""
    municipio = servicios.municipio(region_id)
    if not municipio:
        flash("Ese municipio ya no existe en el catálogo.", "error")
        return redirect(url_for("main.regiones"))

    desglose = servicios.grupos_edad_municipio(region_id)
    campos = [{"grupo": grupo, "campo": campo, "esperado": esperado,
               "etiqueta": "80 años o más" if grupo == "80+" else f"{grupo} años"}
              for grupo, campo, esperado in GRUPOS_FORM]
    if not desglose or any(c["grupo"] not in desglose["grupos"] for c in campos):
        flash("Este municipio no tiene todas sus bandas de edad cargadas. "
              "Vuelve a ejecutar datos/postgres/semillas/nl_municipios_completos.sql.", "error")
        return redirect(url_for("main.regiones"))

    def pantalla(valores, errores, estado=200):
        return render_template("region_edades_form.html", municipio=municipio, campos=campos,
                               desglose=desglose, valores=valores, errores=errores,
                               active_nav="regiones"), estado

    if request.method == "GET":
        valores = {c["campo"]: desglose["grupos"][c["grupo"]] for c in campos}
        return pantalla(dict(valores, motivo=""), [])

    valores = {c["campo"]: request.form.get(c["campo"]) for c in campos}
    valores["motivo"] = (request.form.get("motivo") or "").strip()
    errores, esperados = [], {}
    for c in campos:
        esperados[c["grupo"]], valido = formularios.esperado(request.form, c["esperado"])
        if not valido:
            errores = ["No se pudo verificar el estado del formulario. Recarga la página."]
    esperados["edad_no_especificada"], valido = formularios.esperado(
        request.form, "esperado_edad_no_especificada")
    if not valido:
        errores.append("No se pudo verificar la edad no especificada. Recarga la página.")
    if not valores["motivo"]:
        errores.append("Indica la fuente o el motivo de la corrección.")
    if errores:
        return pantalla(valores, errores, 400)

    grupos = {c["grupo"]: valores[c["campo"]] for c in campos}
    try:
        resultado = servicios.corrige_grupos_edad(token_de_sesion(), region_id, grupos, esperados,
                                                  valores["motivo"])
    except ErrorServicio as exc:
        return pantalla(valores, [_falla_de_escritura(exc)], 400)

    mensaje = f"Bandas de edad de «{resultado['municipio']}» actualizadas. "
    mensaje += f"El 60+ derivado ahora es {resultado['population_60plus']:,}."
    if resultado.get("estado_actualizado"):
        mensaje += " También se recalcularon las bandas agregadas de Nuevo León."
    flash(mensaje, "ok")
    return redirect(url_for("main.regiones"))


# ---------------------------------------------------------------------------
# Escenarios y aprobación -- escenarios, validacion y aprobacion (D36, paso 2)
# ---------------------------------------------------------------------------
@bp.route("/escenarios")
@requiere_permiso("scenarios.read", "scenarios")
def escenarios():
    busqueda = (request.args.get("q") or "").strip() or None
    return render_template(
        "escenarios.html",
        escenarios=seccion("escenarios", servicios.escenarios, token_de_sesion(), busqueda, defecto=[]),
        busqueda=busqueda or "", active_nav="escenarios")


@bp.route("/escenarios/<int:scenario_id>")
@requiere_permiso("scenarios.read", "scenarios")
def escenario_detalle(scenario_id):
    """Detalle de una versión, de solo lectura. Sin `?version=` muestra la vigente."""
    token = token_de_sesion()
    detalle = servicios.escenario_detalle(token, scenario_id, request.args.get("version", type=int))
    if detalle is None:
        flash("Ese escenario o esa versión no existe.", "error")
        return redirect(url_for("main.escenarios"))
    version = detalle["version"]
    errores_motor, avisos_motor = (seccion("validacion", servicios.revisa_version, token, version["id"],
                                           defecto=([], [])) if version else ([], []))
    # D6: population_size son agentes; cuántos habitantes representa cada uno.
    escala = (formato.escala(detalle["escenario"].get("region_poblacion"), version["population_size"])
              if version else None)
    return render_template(
        "escenario_detalle.html", **detalle,
        versiones=seccion("escenarios", servicios.versiones, token, scenario_id, defecto=[]),
        errores_motor=errores_motor, avisos_motor=avisos_motor, escala=escala,
        validacion_caida="validacion" in g.get("servicios_caidos", []),
        active_nav="escenarios")


@bp.route("/escenarios/<int:scenario_id>/revisar", methods=["POST"])
@requiere_permiso("scenarios.approve", "scenario_versions")
def version_revisar(scenario_id):
    # aprobacion valida, impide revisar la propia, audita y avisa al autor en los dos casos (I1).
    try:
        estado = servicios.revisar(token_de_sesion(), scenario_id, request.form.get("decision"),
                                   request.form.get("comentario"))
    except ErrorServicio as exc:
        flash(_falla_de_escritura(exc), "error")
        return redirect(url_for("main.escenario_detalle", scenario_id=scenario_id))
    if estado == "aprobado":
        flash("Versión aprobada. Ya se puede simular. Se avisó a quien la armó.", "ok")
    else:
        flash("Versión rechazada. Se avisó a quien la armó, que puede crear una versión nueva "
              "con las correcciones en la app de escritorio.", "ok")
    return redirect(url_for("main.escenario_detalle", scenario_id=scenario_id))


@bp.route("/revisiones")
@requiere_permiso("scenarios.approve", "scenario_versions")
def revisiones():
    """Bandeja de versiones esperando dictamen, la más antigua primero."""
    return render_template(
        "revisiones.html",
        pendientes=seccion("aprobacion", servicios.pendientes_revision, token_de_sesion(), defecto=[]),
        active_nav="revisiones")


# ---------------------------------------------------------------------------
# Monitoreo -- series y zonas
# ---------------------------------------------------------------------------
INDICADORES = {"incidencia": "Incidencia / 100k", "casos": "Casos confirmados"}
PERIODOS = (7, 30, 90)
ZONAS_VACIAS = {"zonas": [], "total": 0, "pagina": 1, "paginas": 1, "desde": 0, "hasta": 0}
TOTALES_VACIOS = {"casos": 0, "casos_previo": 0, "casos_pct": 0, "incidencia": 0, "incidencia_previa": 0}


def _filtros_monitoreo(args):
    """Lo que no pertenece al dominio se descarta antes de llegar al servicio."""
    indicador = args.get("indicador") or ""
    dias = args.get("dias", type=int)
    return {
        "disease_id": args.get("enfermedad", type=int),
        "region_id": args.get("municipio", type=int),
        "dias": dias if dias in PERIODOS else 30,
        "indicador": indicador if indicador in INDICADORES else "incidencia",
        "busqueda": (args.get("q") or "").strip(),
    }


def _monitoreo_url(filtros):
    nombres = {"disease_id": "enfermedad", "region_id": "municipio",
               "dias": "dias", "indicador": "indicador", "busqueda": "q"}
    return {nombres[k]: v for k, v in filtros.items() if v}


@bp.route("/monitoreo")
@requiere_permiso("reports.read", "reports")
def monitoreo():
    f = _filtros_monitoreo(request.args)
    pagina = max(1, request.args.get("pagina", default=1, type=int))
    token = token_de_sesion()
    ambito = (token, f["disease_id"], f["region_id"], f["dias"])

    serie = seccion("series", servicios.monitoreo_serie, *ambito, defecto=[])
    edades = seccion("series", servicios.monitoreo_edad, *ambito, defecto=[])
    sexos = seccion("series", servicios.monitoreo_sexo, *ambito, defecto=[])
    totales = seccion("series", servicios.monitoreo_totales, *ambito, defecto=TOTALES_VACIOS)
    zonas = seccion("zonas", servicios.monitoreo_zonas, *ambito, f["busqueda"] or None,
                    f["indicador"], pagina, defecto=ZONAS_VACIAS)
    # La tarjeta geográfica compara todas las zonas del ámbito, en el orden fijo del servicio.
    todas = seccion("zonas", servicios.monitoreo_zonas, *ambito, por_pagina=100, defecto=ZONAS_VACIAS)

    return render_template(
        "monitoreo.html", serie=serie, edades=edades, sexos=sexos, totales=totales, zonas=zonas,
        insights=presentacion.monitoreo_insights(todas["zonas"], edades, totales, f["dias"]),
        enfermedades=seccion("zonas", servicios.enfermedades_con_casos, token, defecto=[]),
        municipios=seccion("regiones", servicios.municipios_catalogo, defecto=[]),
        indicadores=INDICADORES, periodos=PERIODOS, filtros=f, filtros_url=_monitoreo_url(f),
        active_nav="monitoreo")


@bp.route("/export/monitoreo.csv")
@requiere_permiso("reports.export", "reports")
def export_monitoreo_csv():
    f = _filtros_monitoreo(request.args)
    zonas = servicios.exporta_zonas(token_de_sesion(), f["disease_id"], f["region_id"], f["dias"],
                                    f["busqueda"] or None, f["indicador"])
    return _csv(
        "monitoreo_zonas.csv",
        ["Zona", f"Casos ({f['dias']} días)", "Incidencia / 100k",
         "Variación 7d (%)", "Graves", "Estado"],
        ([z["zona"], z["casos"], z["incidencia"], z["variacion"], z["graves"],
          presentacion.tendencia_etiqueta(z["estado"])]
         for z in zonas["zonas"]),
    )


# ---------------------------------------------------------------------------
# Simulaciones -- corridas y resultados (D36, paso 3). Solo lectura (D4).
# ---------------------------------------------------------------------------
@bp.route("/simulaciones")
@requiere_permiso("simulations.read", "simulations")
def simulaciones_lista():
    token = token_de_sesion()
    return render_template(
        "simulaciones.html",
        versiones=seccion("escenarios", servicios.todas_las_versiones, token, defecto=[]),
        runs=seccion("corridas", servicios.corridas, token, 20, defecto=[]),
        active_nav="simulaciones")


@bp.route("/simulaciones/corridas/<int:run_id>")
@requiere_permiso("simulations.read", "simulations")
def simulacion_detalle(run_id):
    token = token_de_sesion()
    run = servicios.corrida(token, run_id)
    if not run:
        flash("Esa corrida ya no existe.", "error")
        return redirect(url_for("main.simulaciones_lista"))

    resultado = equivalente = None
    if run["status"] == "completado":
        # Sin MongoDB, el resumen sin curvas (RF-F21); sin resultados, solo los datos de la corrida.
        resultado = seccion("resultados", servicios.resultado, token, run_id)
        otra = seccion("corridas", servicios.corrida_equivalente, token, run_id)
        if resultado and otra:
            # La huella prueba que la ENTRADA fue idéntica; esto compara además la SALIDA.
            equivalente = dict(otra, coincide=otra.get("resumen") == resultado.get("resumen"))

    motor = (resultado or {}).get("engine_version") or run.get("engine_version")
    version_actual, simplificaciones = (formato.motor_de_resultado(motor) if motor
                                        else (formato.ENGINE_VERSION, formato.SIMPLIFICACIONES))
    if resultado and resultado.get("simplificaciones"):
        simplificaciones = resultado["simplificaciones"]
    # resultados trae la escala de D6; sin ella, la pantalla no muestra equivalentes.
    escala = (resultado or {}).get("escala") or {"factor": None, "avisos": [], "representados": {}}
    if resultado and not resultado.get("engine_version"):
        resultado["engine_version"] = run.get("engine_version")
    return render_template(
        "simulacion_detalle.html", run=run, resultado=resultado, equivalente=equivalente,
        categoria=(resultado or {}).get("categoria"), simplificaciones=simplificaciones,
        engine_version_actual=version_actual, escala=escala, active_nav="simulaciones")


@bp.route("/simulaciones/corridas/<int:run_id>/estado")
@requiere_permiso("simulations.read", "simulations")
def simulacion_estado(run_id):
    """Polling de la pantalla de detalle mientras la corrida está encolada o ejecutándose."""
    try:
        run = servicios.corrida(token_de_sesion(), run_id)
    except ServicioNoDisponible:
        return jsonify({"error": "El servicio «corridas» no respondió."}), 503
    if not run:
        return jsonify({"error": "no encontrada"}), 404
    return jsonify({
        "status": run["status"],
        "estado_visible": formato.estado_visible(run["status"]),
        "progress": run["progress"],
        "error_message": run["error_message"],
        "terminal": run["status"] in ("completado", "fallido", "cancelado"),
    })


@bp.route("/comparacion")
@requiere_permiso("simulations.read", "simulations")
def comparacion():
    """Curvas (comparacion, que las pide a resultados) y costo contra impacto (pareto)."""
    token = token_de_sesion()
    seleccionados = request.args.getlist("run_id")
    run_ids = formularios.ids_de(seleccionados)
    corridas, comparacion_pareto, errores_pareto = [], None, []
    if len(run_ids) == 1:
        flash("Selecciona al menos dos corridas completadas para compararlas.", "warn")
    elif len(run_ids) >= 2:
        try:
            corridas = servicios.comparacion(token, run_ids)
        except ErrorServicio as exc:
            flash(_falla_de_escritura(exc), "error")
        except ServicioNoDisponible as exc:
            g.setdefault("servicios_caidos", []).append(exc.servicio)
        try:
            comparacion_pareto = servicios.pareto(token, run_ids)
        except ErrorServicio as exc:
            # Sin personas-día por dosis (D3) u otro dato, pareto se niega y dice por qué.
            errores_pareto = [_falla_de_escritura(exc)]
        except ServicioNoDisponible as exc:
            g.setdefault("servicios_caidos", []).append(exc.servicio)
    runs = seccion("corridas", servicios.corridas, token, 100, "completado", defecto=[])
    return render_template(
        "comparacion.html", runs=runs, corridas=corridas,
        sin_curvas=[c["id"] for c in corridas if not c.get("serie")],
        seleccionados=seleccionados, comparacion_pareto=comparacion_pareto,
        errores_pareto=errores_pareto, active_nav="comparacion")


@bp.route("/comparacion/costos", methods=["GET", "POST"])
@requiere_permiso("catalogs.update", "intervention_types")
def comparacion_costos():
    # tipos-intervencion da el catálogo; intervenciones valida, guarda y audita (D36).
    tipos = servicios.tipos_intervencion()
    if request.method == "GET":
        return render_template("comparacion_costos.html", tipos=tipos, errores=[],
                               active_nav="comparacion")

    tipo_id = request.form.get("intervention_type_id", type=int)
    if not any(t["id"] == tipo_id for t in tipos):
        flash("El tipo de intervención no existe.", "error")
        return redirect(url_for("main.comparacion_costos"))
    try:
        if request.form.get("campo") == "personas_dia":
            servicios.fija_personas_dia_tipo(
                token_de_sesion(), tipo_id, request.form.get("person_days_per_unit"),
                request.form.get("person_days_source"),
                request.form.get("person_days_is_assumption") == "1")
            flash("Personas-día por dosis actualizadas.", "ok")
        else:
            servicios.fija_costo_tipo(
                token_de_sesion(), tipo_id, request.form.get("unit_cost"),
                request.form.get("cost_source"), request.form.get("cost_is_assumption") == "1")
            flash("Costo de la intervención actualizado.", "ok")
    except ErrorServicio as exc:
        return render_template("comparacion_costos.html", tipos=tipos,
                               errores=[_falla_de_escritura(exc)], active_nav="comparacion"), 400
    return redirect(url_for("main.comparacion_costos"))


# ---------------------------------------------------------------------------
# Vigilancia -- casos por región y periodo, con su seguimiento (C7, D47)
# ---------------------------------------------------------------------------
ESTADOS_CASO = {"pendiente": "Pendiente", "validado": "Validado", "duplicado": "Duplicado",
                "descartado": "Descartado"}
CASOS_VACIOS = {"casos": [], "total": 0, "pagina": 1, "por_pagina": 20, "paginas": 0}


def _fecha_iso(texto):
    try:
        return date.fromisoformat(texto).isoformat() if texto else None
    except ValueError:
        return None


@bp.route("/vigilancia")
@requiere_permiso("cases.read", "cases")
def vigilancia():
    hoy = date.today()
    filtros = {
        "disease_id": request.args.get("enfermedad", type=int),
        "region_id": request.args.get("municipio", type=int),
        "estado": request.args.get("estado") if request.args.get("estado") in ESTADOS_CASO else None,
        "desde": _fecha_iso(request.args.get("desde")) or (hoy - timedelta(days=30)).isoformat(),
        "hasta": _fecha_iso(request.args.get("hasta")) or hoy.isoformat(),
    }
    pagina = max(1, request.args.get("pagina", default=1, type=int))
    token = token_de_sesion()
    try:
        listado = servicios.casos(token, filtros["disease_id"], filtros["region_id"], filtros["estado"],
                                  filtros["desde"], filtros["hasta"], pagina)
    except ErrorServicio as exc:
        flash(_falla_de_escritura(exc), "error")
        listado = CASOS_VACIOS
    except ServicioNoDisponible as exc:
        g.setdefault("servicios_caidos", []).append(exc.servicio)
        listado = CASOS_VACIOS
    return render_template(
        "vigilancia.html", listado=listado, filtros=filtros, estados=ESTADOS_CASO,
        enfermedades=seccion("zonas", servicios.enfermedades_con_casos, token, defecto=[]),
        municipios=seccion("regiones", servicios.municipios_catalogo, defecto=[]),
        filtros_url={k: v for k, v in {"enfermedad": filtros["disease_id"],
                                       "municipio": filtros["region_id"], "estado": filtros["estado"],
                                       "desde": filtros["desde"], "hasta": filtros["hasta"]}.items() if v},
        active_nav="vigilancia")


@bp.route("/vigilancia/casos/<int:case_id>", methods=["GET", "POST"])
@requiere_permiso("cases.read", "cases")
def caso_detalle(case_id):
    """El caso y su historial (casos). Validar, descartar o marcar duplicado es del
    EPIDEMIOLOGO (cases.approve, D47), con la versión que se leyó para no pisar otro cambio."""
    token = token_de_sesion()
    if request.method == "POST":
        if not tiene_permiso(g.user, "cases.approve"):
            from flask import abort
            abort(403)
        try:
            servicios.cambia_estado_caso(
                token, case_id, request.form.get("version", type=int), request.form.get("estado"),
                (request.form.get("motivo") or "").strip() or None,
                request.form.get("duplicado_de", type=int))
            flash("Estado del caso actualizado. Si lo descartaste o lo marcaste duplicado, se "
                  "avisó a quien lo capturó.", "ok")
        except ErrorServicio as exc:
            if exc.estado == 412:
                flash("Otra persona cambió este caso mientras lo veías. Revisa la versión actual y "
                      "vuelve a intentarlo.", "warn")
            else:
                flash(_falla_de_escritura(exc), "error")
        return redirect(url_for("main.caso_detalle", case_id=case_id))

    caso = servicios.caso(token, case_id)
    if not caso:
        flash("Ese caso no existe.", "error")
        return redirect(url_for("main.vigilancia"))
    historial = seccion("casos", servicios.historial_caso, token, case_id, defecto=[])
    return render_template("caso_detalle.html", caso=caso, historial=historial, estados=ESTADOS_CASO,
                           active_nav="vigilancia")


# ---------------------------------------------------------------------------
# Campañas de salud -- vacunas (D49)
# ---------------------------------------------------------------------------
ESTADOS_CAMPANA = {"programada": "Programada", "activa": "Activa", "terminada": "Terminada",
                   "cancelada": "Cancelada"}


@bp.route("/campanas", methods=["GET", "POST"])
@requiere_permiso("cases.read", "campaigns")
def campanas():
    """Consulta las campañas; las crean y cancelan EPIDEMIOLOGO y ADMINISTRADOR (catalogs.update),
    y vacunas avisa a los CAPTURISTA."""
    token = token_de_sesion()
    errores, valores = [], {}
    if request.method == "POST":
        if not tiene_permiso(g.user, "catalogs.update"):
            from flask import abort
            abort(403)
        valores = {k: (request.form.get(k) or "").strip() for k in
                   ("name", "disease_id", "region_id", "starts_on", "ends_on", "target_population",
                    "description")}
        try:
            if request.form.get("cancelar"):
                servicios.cancela_campana(token, request.form.get("cancelar", type=int),
                                          (request.form.get("motivo") or "").strip())
                flash("Campaña cancelada.", "ok")
            else:
                servicios.crea_campana(token, valores)
                flash("Campaña registrada. Se avisó a los capturistas.", "ok")
            return redirect(url_for("main.campanas"))
        except ErrorServicio as exc:
            errores = [_falla_de_escritura(exc)]
    estado = request.args.get("estado") if request.args.get("estado") in ESTADOS_CAMPANA else None
    return render_template(
        "campanas.html",
        campanas=seccion("vacunas", servicios.campanas, token, estado, defecto=[]),
        estado=estado, estados=ESTADOS_CAMPANA, errores=errores, valores=valores,
        enfermedades=seccion("enfermedades", servicios.enfermedades, None, "activa", 1, 100,
                             defecto=LISTADO_VACIO)["enfermedades"],
        municipios=seccion("regiones", servicios.municipios_catalogo, defecto=[]),
        active_nav="campanas"), 400 if errores else 200


# ---------------------------------------------------------------------------
# Seguimiento de intervenciones (D51): lo programado, su costo, lo simulado y lo aplicado
# ---------------------------------------------------------------------------
@bp.route("/intervenciones")
@requiere_permiso("scenarios.read", "scenario_interventions")
def seguimiento_intervenciones():
    token = token_de_sesion()
    busqueda = (request.args.get("q") or "").strip().lower()
    versiones = [v for v in seccion("escenarios", servicios.todas_las_versiones, token, defecto=[])
                 if v["status"] == "aprobado"
                 and (not busqueda or busqueda in (v["scenario_name"] or "").lower())]
    tipos = {t["code"]: t for t in seccion("tipos-intervencion", servicios.tipos_intervencion, defecto=[])}
    corridas_por_version = {}
    for c in seccion("corridas", servicios.corridas, token, 100, defecto=[]):
        corridas_por_version.setdefault(c["scenario_version_id"], []).append(c)
    campanas = seccion("vacunas", servicios.campanas, token, defecto=[])

    filas = []
    for v in versiones:
        intervenciones = seccion("intervenciones", servicios.intervenciones_version, token, v["id"],
                                 defecto=None)
        corridas = corridas_por_version.get(v["id"], [])
        por_dosis = any((tipos.get(i["code"]) or {}).get("cost_unit") == "por_dosis"
                        for i in intervenciones or [])
        filas.append({
            "version": v, "intervenciones": intervenciones, "corridas": corridas,
            "completadas": [c["id"] for c in corridas if c["status"] == "completado"],
            "campanas": [c for c in campanas if c.get("enfermedad") == v["disease_name"]] if por_dosis else [],
        })
    return render_template("intervenciones.html", filas=filas, tipos=tipos,
                           busqueda=request.args.get("q") or "", active_nav="intervenciones")


# ---------------------------------------------------------------------------
# Reportes -- las descargas de la web en un solo lugar (C7)
# ---------------------------------------------------------------------------
@bp.route("/reportes")
@requiere_permiso("reports.read", "reports")
def reportes():
    return render_template("reportes.html", active_nav="reportes")


# ---------------------------------------------------------------------------
# Usuarios -- usuarios y roles (D36, paso 7). Solo ADMINISTRADOR.
# ---------------------------------------------------------------------------
RESUMEN_VACIO = {"total": 0, "activos": 0, "pendientes": 0, "inactivos": 0}


@bp.route("/usuarios")
@requiere_permiso("users.read", "users")
def usuarios():
    token = token_de_sesion()
    busqueda = request.args.get("q") or None
    rol_id = request.args.get("rol", type=int)
    estado = request.args.get("estado") or None
    if estado not in (None, "activo", "pendiente", "inactivo"):
        estado = None
    return render_template(
        "usuarios.html",
        resumen=seccion("usuarios", servicios.usuarios_resumen, token, defecto=RESUMEN_VACIO),
        roles=seccion("roles", servicios.roles, token, defecto=[]),
        usuarios=seccion("usuarios", servicios.usuarios, token, busqueda, rol_id, estado, defecto=[]),
        filtro_q=busqueda or "", filtro_rol=rol_id, filtro_estado=estado, active_nav="usuarios")


def _form_usuario(token, usuario, errores, estado=200):
    return render_template(
        "usuario_form.html", usuario=usuario, errores=errores,
        roles=seccion("roles", servicios.roles, token, defecto=[]),
        instituciones=seccion("usuarios", servicios.instituciones, token, defecto=[]),
        municipios=seccion("regiones", servicios.municipios_catalogo, defecto=[]),
        active_nav="usuarios"), estado


def _datos_usuario(form):
    return {"email": (form.get("email") or "").strip(),
            "full_name": (form.get("full_name") or "").strip(),
            "institution_id": form.get("institution_id", type=int),
            "region_id": form.get("region_id", type=int)}


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@requiere_permiso("users.create", "users")
def usuario_nuevo():
    """usuarios valida y da de alta la cuenta; roles le asigna el rol. Cada uno audita."""
    token = token_de_sesion()
    if request.method == "GET":
        return _form_usuario(token, None, [])
    datos = dict(_datos_usuario(request.form), username=(request.form.get("username") or "").strip(),
                 is_active=request.form.get("is_active") == "on")
    role_id = request.form.get("role_id", type=int)
    vista = dict(datos, role_id=role_id)
    if not role_id:
        return _form_usuario(token, vista, ["Selecciona un rol."], 400)
    try:
        servicios.crea_usuario(token, datos, request.form.get("password") or "", role_id)
    except ErrorServicio as exc:
        return _form_usuario(token, vista, [_falla_de_escritura(exc)], 400)
    flash(f"Usuario '{datos['username'].lower()}' creado.", "ok")
    return redirect(url_for("main.usuarios"))


@bp.route("/usuarios/<int:user_id>/editar", methods=["GET", "POST"])
@requiere_permiso("users.update", "users")
def usuario_editar(user_id):
    token = token_de_sesion()
    actual = servicios.usuario(token, user_id)
    if not actual:
        flash("Ese usuario ya no existe.", "error")
        return redirect(url_for("main.usuarios"))
    if request.method == "GET":
        return _form_usuario(token, actual, [])

    datos = _datos_usuario(request.form)
    activo = request.form.get("is_active") == "on"
    role_id = request.form.get("role_id", type=int)
    vista = {**actual, **datos, "is_active": activo, "role_id": role_id}
    if not role_id:
        return _form_usuario(token, vista, ["Selecciona un rol."], 400)
    if user_id == g.user["sub"] and not activo:
        return _form_usuario(token, vista, ["No puedes desactivar tu propia cuenta."], 400)
    try:
        servicios.edita_usuario(token, user_id, datos, request.form.get("password") or "", role_id,
                                activo, actual["is_active"], actual.get("role_id"))
    except ErrorServicio as exc:
        return _form_usuario(token, vista, [_falla_de_escritura(exc)], 400)
    flash(f"Usuario '{actual['username']}' actualizado.", "ok")
    return redirect(url_for("main.usuarios"))


@bp.route("/usuarios/<int:user_id>/estado", methods=["POST"])
@requiere_permiso("users.update", "users")
def usuario_estado(user_id):
    """Baja y alta lógica. Desactivar cierra las sesiones de la cuenta (usuarios)."""
    activar = request.form.get("activar") == "1"
    try:
        servicios.activa_usuario(token_de_sesion(), user_id, activar)
        flash("Usuario reactivado." if activar else "Usuario desactivado (baja lógica).", "ok")
    except ErrorServicio as exc:
        flash(_falla_de_escritura(exc), "error")
    return redirect(url_for("main.usuarios"))


@bp.route("/usuarios/<int:user_id>/eliminar", methods=["POST"])
@requiere_permiso("users.delete", "users")
def usuario_eliminar(user_id):
    # usuarios se niega si la cuenta tiene registros: entonces va la baja lógica.
    try:
        servicios.elimina_usuario(token_de_sesion(), user_id)
        flash("Usuario eliminado.", "ok")
    except ErrorServicio as exc:
        flash(_falla_de_escritura(exc), "error")
    return redirect(url_for("main.usuarios"))


@bp.route("/auditoria")
@requiere_permiso("audit.read", "audit")
def auditoria():
    """La bitácora, solo del ADMINISTRADOR (RF-L05). La consulta roles (D37)."""
    token = token_de_sesion()
    busqueda = request.args.get("q") or None
    usuario_id = request.args.get("usuario", type=int)
    modulo = request.args.get("modulo") or None
    accion = request.args.get("accion") or None
    filtros = seccion("roles", servicios.bitacora_filtros, token,
                      defecto={"modulos": [], "acciones": [], "usuarios": []})
    eventos = seccion("roles", servicios.bitacora, token, busqueda, usuario_id, modulo, accion, 100,
                      defecto=[])
    return render_template(
        "auditoria.html",
        resumen=seccion("roles", servicios.bitacora_resumen, token,
                        defecto={"eventos_totales": 0, "criticas": 0, "fallidos": 0, "activos_24h": 0}),
        eventos=presentacion.filas_bitacora(eventos),
        usuarios_filtro=filtros["usuarios"], modulos=filtros["modulos"],
        acciones=presentacion.opciones_accion(filtros["acciones"]),
        filtro_q=busqueda or "", filtro_usuario=usuario_id, filtro_modulo=modulo,
        filtro_accion=accion, active_nav="auditoria")


# ---------------------------------------------------------------------------
# Avisos -- servicio notificaciones (RF-D15, RF-C19)
# ---------------------------------------------------------------------------
TIPOS_DE_AVISO = {
    "SCENARIO_SUBMITTED": "Versión por revisar", "SCENARIO_APPROVED": "Versión aprobada",
    "SCENARIO_REJECTED": "Versión rechazada", "SCENARIO_PUBLISHED": "Escenario publicado",
    "NEW_CASES": "Casos nuevos", "CASE_REJECTED": "Caso descartado",
    "DATA_INCOMPLETE": "Datos incompletos", "CAMPAIGN": "Campaña",
    "RUN_FINISHED": "Corrida terminada", "RUN_FAILED": "Corrida fallida",
    "THRESHOLD_EXCEEDED": "Umbral superado", "ASSIGNMENT": "Asignación", "SYSTEM": "Sistema",
}


@bp.route("/avisos")
@requiere_permiso(None, "notifications")
def avisos():
    solo_no_leidas = request.args.get("no_leidas") == "1"
    lista, no_leidas = seccion("notificaciones", servicios.avisos, token_de_sesion(), solo_no_leidas,
                               defecto=([], 0))
    return render_template("avisos.html", avisos=lista, no_leidas=no_leidas,
                           solo_no_leidas=solo_no_leidas,
                           sin_servicio="notificaciones" in g.get("servicios_caidos", []),
                           tipos_aviso=TIPOS_DE_AVISO, active_nav="avisos")


@bp.route("/avisos/<int:aviso_id>/leido", methods=["POST"])
@requiere_permiso(None, "notifications")
def aviso_leido(aviso_id):
    try:
        servicios.marca_aviso_leido(token_de_sesion(), aviso_id)
    except ErrorServicio as exc:
        flash(_falla_de_escritura(exc), "error")
    return redirect(url_for("main.avisos"))


# ---------------------------------------------------------------------------
# Errores: se explican sin mostrar la traza (RNF-E06, D36)
# ---------------------------------------------------------------------------
def _error(codigo, titulo, mensaje):
    return render_template("error.html", codigo=str(codigo), titulo=titulo, mensaje=mensaje), codigo


@bp.app_errorhandler(400)
def solicitud_invalida(exc):
    return _error(400, "No se pudo procesar la solicitud",
                  getattr(exc, "description", None) or "Revisa los datos e intenta de nuevo.")


@bp.app_errorhandler(403)
def sin_permiso(_):
    return _error(403, "No tienes acceso a esta sección",
                  "Tu rol no incluye permiso para ver esta página. "
                  "Pide acceso a un administrador si lo necesitas.")


@bp.app_errorhandler(404)
def no_encontrado(_):
    return _error(404, "Esta página no existe",
                  "Revisa la dirección o vuelve al panorama epidemiológico.")


@bp.app_errorhandler(405)
def metodo_no_permitido(_):
    return _error(405, "Esa acción no está disponible aquí",
                  "Vuelve a la pantalla anterior y usa sus botones.")


@bp.app_errorhandler(ServicioNoDisponible)
def servicio_caido(exc):
    # La pantalla dice qué servicio falta; si era una escritura, que no se guardó.
    current_app.logger.warning("Servicio no disponible: %s", exc.servicio)
    g._usuario_actual = None
    escritura = request.method not in ("GET", "HEAD")
    return _error(503, "Este dato no está disponible por ahora",
                  "El servicio «%s» no respondió. %sIntenta de nuevo en unos minutos."
                  % (exc.servicio, MENSAJE_NO_GUARDADO + " " if escritura else ""))


@bp.app_errorhandler(ErrorServicio)
def error_de_servicio(exc):
    if exc.estado == 401:
        return redirect(url_for("main.login", next=request.path))
    if exc.estado == 403:
        return sin_permiso(exc)
    if exc.estado == 404:
        return no_encontrado(exc)
    return _error(exc.estado, "No se pudo completar la operación",
                  exc.detalle or "El servicio rechazó la petición.")


@bp.app_errorhandler(Exception)
def error_inesperado(exc):
    # La traza va al registro, nunca a la pantalla (RNF-E06).
    from werkzeug.exceptions import HTTPException
    if isinstance(exc, HTTPException):
        return exc
    current_app.logger.exception("Error inesperado en %s", request.path)
    return _error(500, "Algo salió mal",
                  "Ocurrió un error inesperado y quedó registrado. Intenta de nuevo; si sigue "
                  "pasando, avisa al administrador con la hora en que ocurrió.")


@bp.after_app_request
def guarda_tokens_renovados(respuesta):
    nuevos = g.get("tokens_nuevos")
    if nuevos:
        for nombre, valor in zip((COOKIE_NAME, COOKIE_REFRESH), nuevos):
            respuesta.set_cookie(nombre, valor, httponly=True, secure=request.is_secure,
                                 samesite="Lax", max_age=60 * 60 * 8)
    return respuesta
