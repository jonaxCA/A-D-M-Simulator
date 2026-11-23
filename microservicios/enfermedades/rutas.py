"""Servicio enfermedades: el catálogo, su clasificación y las definiciones de caso versionadas (D56).

La lista y el alta siguen con las reglas de backend_web.queries (E8 pendiente); la ficha, la
clasificación y las definiciones de caso viven en datos.py.
"""
import psycopg2
from flask import g, request

from backend_web import queries
from backend_web.audit import log_audit
from backend_web.db import get_conn, query
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo

from . import datos as bd

ESTADO_NL = "19"
ROLES_EDITAN = ("EPIDEMIOLOGO", "ADMINISTRADOR")
TRANSMISIONES = ("respiratoria", "vectorial")
CRITERIOS_MAX = 20
TEXTO_MAX = 4000


def _invalido(mensaje):
    return ErrorAPI(422, "DATOS_INVALIDOS", mensaje)


def _texto(valor, campo, maximo, obligatorio=False):
    if valor is None and not obligatorio:
        return None
    if not isinstance(valor, str) or not valor.strip() or len(valor.strip()) > maximo:
        raise _invalido("%s debe ser texto de 1 a %d caracteres." % (campo, maximo))
    return valor.strip()


def _definicion_de(cuerpo):
    # (criterios, fuente, url) validados. En XML: <criterios><criterio>...</criterio></criterios>.
    cuerpo = diccionario(cuerpo)
    if set(cuerpo) - {"criterios", "fuente", "url"}:
        raise _invalido("Solo se aceptan criterios, fuente y url.")
    criterios = cuerpo.get("criterios")
    if isinstance(criterios, dict) and set(criterios) == {"criterio"}:
        criterios = criterios["criterio"]
    if isinstance(criterios, dict):
        criterios = [criterios]
    if not isinstance(criterios, list) or not 1 <= len(criterios) <= CRITERIOS_MAX:
        raise _invalido("criterios debe ser una lista de 1 a %d criterios." % CRITERIOS_MAX)
    limpios = []
    for criterio in criterios:
        if not isinstance(criterio, dict) or set(criterio) != {"clasificacion", "texto"}:
            raise _invalido("Cada criterio lleva clasificacion y texto.")
        limpios.append({"clasificacion": _texto(criterio["clasificacion"], "clasificacion", 200, True),
                        "texto": _texto(criterio["texto"], "texto", TEXTO_MAX, True)})
    url = _texto(cuerpo.get("url"), "url", 500)
    if url and not url.startswith(("http://", "https://")):
        raise _invalido("url debe empezar con http:// o https://.")
    return limpios, _texto(cuerpo.get("fuente"), "fuente", 1000, True), url


def _enfermedad(disease_id):
    fila = bd.enfermedad(disease_id)
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
    return fila


def registrar(app):
    @app.get("/api/v1/diseases")
    def lista():
        try:
            pagina = entero_positivo(request.args.get("page", "1"), "page")
            tamano = entero_positivo(request.args.get("size", "10"), "size")
        except ErrorAPI:
            raise
        if tamano > 100:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "size no puede ser mayor que 100.")
        estado = request.args.get("status")
        if estado not in (None, "activa", "inactiva"):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "status debe ser activa o inactiva.")
        datos = queries.get_enfermedades(
            busqueda=(request.args.get("q") or "").strip() or None,
            estado=estado, pagina=pagina, por_pagina=tamano)
        return responder(datos, "catalogo_enfermedades")

    # La misma lista, para descargarla: pide sesión para que la bitácora sepa quién exportó (F-3).
    @app.get("/api/v1/diseases/export")
    @requiere_token()
    def exportar():
        pagina = entero_positivo(request.args.get("page", "1"), "page")
        tamano = entero_positivo(request.args.get("size", "100"), "size")
        if tamano > 100:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "size no puede ser mayor que 100.")
        estado = request.args.get("status")
        if estado not in (None, "activa", "inactiva"):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "status debe ser activa o inactiva.")
        datos = queries.get_enfermedades(
            busqueda=(request.args.get("q") or "").strip() or None,
            estado=estado, pagina=pagina, por_pagina=tamano)
        if pagina == 1:
            log_audit(g.contexto, "EXPORT", "reports", entity_id="catalogo_enfermedades")
        return responder(datos, "catalogo_enfermedades")

    # Las tarjetas del catálogo. «Detectadas» son las enfermedades con un caso pendiente o validado
    # en un municipio de Nuevo León en los últimos 30 días; lo demás es solo del catálogo.
    @app.get("/api/v1/diseases/stats")
    def estadisticas():
        catalogo = query("""SELECT count(*) AS registradas,
                                   count(*) FILTER (WHERE is_active) AS activas,
                                   count(*) FILTER (WHERE NOT is_active) AS inactivas,
                                   count(*) FILTER (WHERE created_at >= now() - interval '30 days') AS altas_30d
                            FROM diseases""", one=True)
        detectadas = query("""SELECT count(DISTINCT c.disease_id) AS n
                              FROM cases c JOIN regions r ON r.id = c.region_id
                              WHERE r.parent_region_id = (SELECT id FROM regions WHERE code = %s)
                                AND c.status IN ('pendiente', 'validado')
                                AND c.report_date >= current_date - 29""", (ESTADO_NL,), one=True)
        return responder({**catalogo, "detectadas_30d": detectadas["n"]}, "estadisticas_enfermedades")

    @app.get("/api/v1/diseases/<int:disease_id>")
    def detalle(disease_id):
        return responder(_enfermedad(disease_id), "enfermedad")

    @app.get("/api/v1/diseases/<int:disease_id>/case-definitions")
    def definiciones(disease_id):
        _enfermedad(disease_id)
        filas = bd.definiciones(disease_id)
        return responder({"disease_id": disease_id, "total": len(filas), "definiciones": filas},
                         "definiciones_caso")

    @app.get("/api/v1/diseases/<int:disease_id>/case-definitions/current")
    def definicion_vigente(disease_id):
        _enfermedad(disease_id)
        fila = bd.definicion(disease_id)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "La enfermedad no tiene una definición de caso vigente.")
        return responder(dict(fila, disease_id=disease_id), "definicion_caso")

    @app.get("/api/v1/diseases/<int:disease_id>/case-definitions/<version>")
    def definicion(disease_id, version):
        fila = bd.definicion(disease_id, entero_positivo(version, "version"))
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe esa versión de la definición de caso.")
        return responder(dict(fila, disease_id=disease_id), "definicion_caso")

    @app.post("/api/v1/diseases/<int:disease_id>/case-definitions")
    @requiere_token(roles=ROLES_EDITAN)
    def crear_definicion(disease_id):
        criterios, fuente, url = _definicion_de(leer_cuerpo())
        version = bd.crea_borrador(disease_id, criterios, fuente, url, contexto=g.contexto)
        return responder(dict(bd.definicion(disease_id, version), disease_id=disease_id), "definicion_caso",
                         estado=201)

    @app.put("/api/v1/diseases/<int:disease_id>/case-definitions/<version>")
    @requiere_token(roles=ROLES_EDITAN)
    def editar_definicion(disease_id, version):
        numero = entero_positivo(version, "version")
        criterios, fuente, url = _definicion_de(leer_cuerpo())
        bd.edita_borrador(disease_id, numero, criterios, fuente, url, contexto=g.contexto)
        return responder(dict(bd.definicion(disease_id, numero), disease_id=disease_id), "definicion_caso")

    @app.post("/api/v1/diseases/<int:disease_id>/case-definitions/<version>/publish")
    @requiere_token(roles=ROLES_EDITAN)
    def publicar_definicion(disease_id, version):
        numero = entero_positivo(version, "version")
        retirada = bd.publica(disease_id, numero, contexto=g.contexto)
        return responder(dict(bd.definicion(disease_id, numero), disease_id=disease_id, retirada=retirada),
                         "definicion_caso")

    @app.post("/api/v1/diseases")
    @requiere_token(roles=("EPIDEMIOLOGO", "ADMINISTRADOR"))
    def crear():
        datos = diccionario(leer_cuerpo())
        if set(datos) - {"code", "name", "description"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Los parámetros se actualizan desde el servicio parametros.")
        if not isinstance(datos.get("code"), str) or not isinstance(datos.get("name"), str):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "code y name deben ser texto.")
        codigo = datos["code"].strip()
        nombre = datos["name"].strip()
        errores = queries.valida_enfermedad(codigo, nombre)
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        descripcion = datos.get("description")
        if descripcion is not None and not isinstance(descripcion, str):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "description debe ser texto.")
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO diseases (code, name, description, default_params)
                                   VALUES (%s, %s, %s, '{}'::jsonb) RETURNING id""",
                                (codigo, nombre, (descripcion or "").strip() or None))
                    nuevo_id = cur.fetchone()[0]
                    log_audit(g.contexto, "CREATE", "diseases", nuevo_id,
                              data_after={"code": codigo, "name": nombre}, cur=cur)
                conn.commit()
        except psycopg2.errors.UniqueViolation as exc:
            raise ErrorAPI(409, "CONFLICTO", "Ya existe una enfermedad con ese código.") from exc
        return responder({"id": nuevo_id}, "enfermedad", estado=201)

    @app.put("/api/v1/diseases/<int:disease_id>")
    @requiere_token(roles=ROLES_EDITAN)
    def editar(disease_id):
        datos = diccionario(leer_cuerpo())
        nombre = datos.get("name")
        descripcion = datos.get("description")
        if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 120:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "name es obligatorio y de máximo 120 caracteres.")
        if descripcion is not None and not isinstance(descripcion, str):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "description debe ser texto.")
        clasificacion = {"transmission", "icd10", "classification_source"}
        if set(datos) - {"name", "description"} - clasificacion:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "No se pueden modificar código, parámetros ni otros campos aquí.")
        cambios = {"name": nombre.strip(), "description": (descripcion or "").strip() or None}
        if set(datos) & clasificacion:
            # La clasificación se cambia completa y con su fuente (regla 8).
            transmision = datos.get("transmission")
            if transmision is not None and transmision not in TRANSMISIONES:
                raise _invalido("transmission debe ser una de: %s." % ", ".join(TRANSMISIONES))
            cie = _texto(datos.get("icd10"), "icd10", 60)
            fuente = _texto(datos.get("classification_source"), "classification_source", 1000)
            if (transmision or cie) and not fuente:
                raise _invalido("La clasificación necesita su fuente (classification_source).")
            cambios.update(transmission=transmision, icd10=cie, classification_source=fuente)
        bd.clasifica(disease_id, cambios, contexto=g.contexto)
        return responder({"id": disease_id, "actualizada": True}, "enfermedad")

    @app.post("/api/v1/diseases/<int:disease_id>/<accion>")
    @requiere_token(roles=("EPIDEMIOLOGO", "ADMINISTRADOR"))
    def activar(disease_id, accion):
        if accion not in ("activate", "deactivate"):
            raise ErrorAPI(404, "NO_ENCONTRADO", "Operación no disponible.")
        activo = accion == "activate"
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT is_active FROM diseases WHERE id=%s FOR UPDATE", (disease_id,))
                fila = cur.fetchone()
                if fila is None:
                    raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
                cur.execute("UPDATE diseases SET is_active=%s WHERE id=%s", (activo, disease_id))
                log_audit(g.contexto, "UPDATE", "diseases", disease_id,
                          data_before={"is_active": fila[0]},
                          data_after={"is_active": activo}, cur=cur)
            conn.commit()
        return responder({"id": disease_id, "is_active": activo}, "enfermedad")
