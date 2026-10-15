from flask import g

from backend_web import queries
from backend_web.audit import log_audit
from backend_web.db import a_jsonb, get_conn
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, parametros_epidemiologicos


def registrar(app):
    @app.get("/api/v1/diseases/<int:disease_id>/parameters")
    def consultar(disease_id):
        fila = queries.get_enfermedad(disease_id)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
        return responder({"disease_id": disease_id, "parametros": fila["default_params"] or {}},
                         "parametros")

    @app.get("/api/v1/diseases/<int:disease_id>/parameters/status")
    def estado(disease_id):
        fila = queries.get_enfermedad(disease_id)
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
        return responder(queries.estado_parametros(fila["default_params"]), "estado_parametros")

    @app.put("/api/v1/diseases/<int:disease_id>/parameters")
    @requiere_token(roles=("EPIDEMIOLOGO", "ADMINISTRADOR"))
    def actualizar(disease_id):
        datos = diccionario(leer_cuerpo())
        if set(datos) != {"parametros"}:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Envía únicamente el campo parametros.")
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT default_params FROM diseases WHERE id=%s FOR UPDATE", (disease_id,))
                fila = cur.fetchone()
                if fila is None:
                    raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
                anteriores = fila[0] or {}
                nuevos = parametros_epidemiologicos(datos["parametros"], anteriores)
                cur.execute("UPDATE diseases SET default_params=%s::jsonb WHERE id=%s",
                            (a_jsonb(nuevos), disease_id))
                log_audit(g.contexto, "UPDATE", "diseases", disease_id,
                          data_before={"default_params": anteriores},
                          data_after={"default_params": nuevos}, cur=cur)
            conn.commit()
        return responder({"disease_id": disease_id, "parametros": nuevos}, "parametros")
