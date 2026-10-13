import psycopg2
from flask import g, request

from backend_web import queries
from backend_web.audit import log_audit
from backend_web.db import get_conn
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo


CAMPOS = ("id", "code", "name", "description", "is_active", "created_at")


def _ficha(fila):
    return {clave: fila[clave] for clave in CAMPOS}


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

    @app.get("/api/v1/diseases/<int:disease_id>")
    def detalle(disease_id):
        fila = queries.get_enfermedad(disease_id)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
        return responder(_ficha(fila), "enfermedad")

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
    @requiere_token(roles=("EPIDEMIOLOGO", "ADMINISTRADOR"))
    def editar(disease_id):
        datos = diccionario(leer_cuerpo())
        nombre = datos.get("name")
        descripcion = datos.get("description")
        if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 120:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "name es obligatorio y de máximo 120 caracteres.")
        if descripcion is not None and not isinstance(descripcion, str):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "description debe ser texto.")
        if set(datos) - {"name", "description"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "No se pueden modificar código, parámetros ni otros campos aquí.")
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, description FROM diseases WHERE id=%s FOR UPDATE", (disease_id,))
                anterior = cur.fetchone()
                if anterior is None:
                    raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
                antes = {"name": anterior[1], "description": anterior[2]}
                despues = {"name": nombre.strip(), "description": (descripcion or "").strip() or None}
                cur.execute("UPDATE diseases SET name=%s, description=%s WHERE id=%s",
                            (despues["name"], despues["description"], disease_id))
                log_audit(g.contexto, "UPDATE", "diseases", disease_id,
                          data_before=antes, data_after=despues, cur=cur)
            conn.commit()
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
