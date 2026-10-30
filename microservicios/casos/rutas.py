import math
import uuid
from datetime import datetime, timezone

import psycopg2
from flask import g, request

from backend_web import queries
from backend_web.audit import log_audit
from backend_web.db import get_conn
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.seguridad import requiere_token
from epidemia_comun.validaciones import diccionario, entero_positivo, fecha

# Matriz de permisos (migración 010): cases.create = CAPTURISTA (+ ADMINISTRADOR, que
# lo tiene todo); cases.read = los cuatro roles. El monolito deja capturar a cualquier
# usuario autenticado; aquí se aplica la matriz.
ROLES_ESCRITURA = ("CAPTURISTA", "ADMINISTRADOR")
ROLES_LECTURA = ("CAPTURISTA", "EPIDEMIOLOGO", "ANALISTA", "ADMINISTRADOR")

ESTADOS = ("pendiente", "validado", "duplicado", "descartado")
MAXIMO_POR_PAGINA = 100
BIGINT_MAX = 2 ** 63 - 1

CAMPOS_ENTRADA = ("local_uuid", "device_id", "disease_id", "region_id", "report_date",
                  "onset_date", "age", "sex", "latitude", "longitude", "test_result",
                  "severity")
CAMPOS_SALIDA = ("id", "local_uuid", "device_id", "reported_by", "disease_id", "enfermedad",
                 "region_id", "municipio", "age", "sex", "onset_date", "report_date",
                 "latitude", "longitude", "test_result", "severity", "status",
                 "created_at", "synced_at")

_SELECT = """
    SELECT c.id, c.local_uuid, c.device_id, c.reported_by, c.disease_id, d.name,
           c.region_id, r.name, c.age, c.sex, c.onset_date, c.report_date,
           c.latitude, c.longitude, c.test_result, c.severity, c.status,
           c.created_at, c.synced_at
    FROM cases c
    JOIN diseases d ON d.id = c.disease_id
    JOIN regions  r ON r.id = c.region_id
"""

_INSERTA = """
    INSERT INTO cases (local_uuid, device_id, reported_by, disease_id, region_id, age, sex,
                       onset_date, report_date, latitude, longitude, test_result,
                       severity, synced_at)
    VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (local_uuid) DO NOTHING
    RETURNING id
"""


def _a_caso(fila):
    caso = dict(zip(CAMPOS_SALIDA, fila))
    caso["local_uuid"] = str(caso["local_uuid"])
    return caso


def _texto_de_formulario(clave, valor):
    """Lo que valida_caso espera de un formulario web: texto o nada. Un JSON trae
    números y un XML trae texto (o tipo="numero"); ambos llegan aquí iguales."""
    if valor is None:
        return None
    if isinstance(valor, bool) or isinstance(valor, (dict, list)):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El campo %s debe ser un valor simple." % clave)
    if isinstance(valor, float) and not math.isfinite(valor):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "El campo %s debe ser un número finito." % clave)
    return str(valor)


def _leer_caso(cuerpo):
    datos = diccionario(cuerpo)
    desconocidos = set(datos) - set(CAMPOS_ENTRADA)
    if desconocidos:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "Campos no reconocidos: " + ", ".join(sorted(str(c) for c in desconocidos)) + ".")
    return {c: _texto_de_formulario(c, datos.get(c)) for c in CAMPOS_ENTRADA}


def _uuid_opcional(texto):
    if texto is None or not texto.strip():
        return None
    try:
        return str(uuid.UUID(texto.strip()))
    except ValueError:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "local_uuid no es un UUID válido.")


def _dispositivo_opcional(texto):
    if texto is None or not texto.strip():
        return None
    try:
        valor = int(texto.strip())
    except ValueError:
        valor = 0
    if not 1 <= valor <= BIGINT_MAX:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "device_id debe ser un entero positivo.")
    return valor


def _existente(cur, local_uuid):
    cur.execute(_SELECT + " WHERE c.local_uuid = %s::uuid", (local_uuid,))
    fila = cur.fetchone()
    return _a_caso(fila) if fila else None


def _entero_de_consulta(nombre):
    crudo = request.args.get(nombre)
    return None if crudo is None else entero_positivo(crudo, nombre)


def _fecha_de_consulta(nombre):
    crudo = request.args.get(nombre)
    return None if crudo is None else fecha(crudo, nombre)


def registrar(app):
    @app.post("/api/v1/cases")
    @requiere_token(roles=ROLES_ESCRITURA)
    def crear():
        entrada = _leer_caso(leer_cuerpo())
        local_uuid = _uuid_opcional(entrada["local_uuid"])
        device_id = _dispositivo_opcional(entrada["device_id"])

        # Idempotencia: un reintento de la sincronización con el mismo local_uuid
        # regresa el caso que ya existe, sin volver a validar ni a escribir.
        if local_uuid:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    previo = _existente(cur, local_uuid)
            if previo:
                previo["duplicado"] = True
                return responder(previo, "caso", estado=200)

        datos, errores = queries.valida_caso(
            entrada, queries.get_enfermedades_para_captura(), queries.get_municipios_catalogo())
        if errores:
            raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
        local_uuid = local_uuid or str(uuid.uuid4())
        # synced_at: el caso llegó desde un dispositivo (trae device_id).
        sincronizado = datetime.now(timezone.utc) if device_id else None

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(_INSERTA, (
                        local_uuid, device_id, g.usuario["sub"], datos["disease_id"],
                        datos["region_id"], datos["age"], datos["sex"], datos["onset_date"],
                        datos["report_date"], datos["latitude"], datos["longitude"],
                        datos["test_result"], datos["severity"], sincronizado))
                    nuevo = cur.fetchone()
                    if nuevo is None:
                        # Otra petición con el mismo local_uuid ganó la carrera.
                        previo = _existente(cur, local_uuid)
                        conn.rollback()
                        previo["duplicado"] = True
                        return responder(previo, "caso", estado=200)
                    cur.execute(_SELECT + " WHERE c.id = %s", (nuevo[0],))
                    caso = _a_caso(cur.fetchone())
                    log_audit(g.contexto, "CREATE", "cases", caso["id"],
                              data_after=dict(caso), cur=cur)
                conn.commit()
        except psycopg2.errors.ForeignKeyViolation as exc:
            restriccion = getattr(getattr(exc, "diag", None), "constraint_name", "") or ""
            mensaje = ("El dispositivo no existe." if "device" in restriccion
                       else "La enfermedad o el municipio seleccionados ya no existen.")
            raise ErrorAPI(422, "DATOS_INVALIDOS", mensaje) from exc
        except psycopg2.errors.CheckViolation as exc:
            restriccion = getattr(getattr(exc, "diag", None), "constraint_name", "") or ""
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "La base rechazó el caso por una restricción: %s." % restriccion) from exc
        caso["duplicado"] = False
        return responder(caso, "caso", estado=201)

    @app.get("/api/v1/cases")
    @requiere_token(roles=ROLES_LECTURA)
    def lista():
        pagina = entero_positivo(request.args.get("page", "1"), "page")
        por_pagina = entero_positivo(request.args.get("per_page", "20"), "per_page")
        if por_pagina > MAXIMO_POR_PAGINA:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "per_page no puede ser mayor que %d." % MAXIMO_POR_PAGINA)
        condiciones, params = [], []
        for nombre, columna in (("disease_id", "c.disease_id"), ("region_id", "c.region_id")):
            valor = _entero_de_consulta(nombre)
            if valor is not None:
                condiciones.append(columna + " = %s")
                params.append(valor)
        estado = request.args.get("status")
        if estado is not None:
            if estado not in ESTADOS:
                raise ErrorAPI(422, "DATOS_INVALIDOS", "status debe ser uno de: " + ", ".join(ESTADOS) + ".")
            condiciones.append("c.status = %s")
            params.append(estado)
        sexo = request.args.get("sex")
        if sexo is not None:
            if sexo not in queries.SEXOS:
                raise ErrorAPI(422, "DATOS_INVALIDOS", "sex debe ser M, F u O.")
            condiciones.append("c.sex = %s")
            params.append(sexo)
        desde, hasta = _fecha_de_consulta("from"), _fecha_de_consulta("to")
        if desde and hasta and desde > hasta:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "from no puede ser posterior a to.")
        if desde:
            condiciones.append("c.report_date >= %s")
            params.append(desde)
        if hasta:
            condiciones.append("c.report_date <= %s")
            params.append(hasta)
        donde = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM cases c" + donde, tuple(params))
                total = cur.fetchone()[0]
                cur.execute(_SELECT + donde + " ORDER BY c.report_date DESC, c.id DESC"
                            " LIMIT %s OFFSET %s",
                            tuple(params) + (por_pagina, (pagina - 1) * por_pagina))
                casos = [_a_caso(f) for f in cur.fetchall()]
        return responder({"casos": casos, "total": total, "pagina": pagina,
                          "por_pagina": por_pagina,
                          "paginas": int(math.ceil(total / float(por_pagina)))},
                         "lista_casos")

    @app.get("/api/v1/cases/<int:case_id>")
    @requiere_token(roles=ROLES_LECTURA)
    def detalle(case_id):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(_SELECT + " WHERE c.id = %s", (case_id,))
                fila = cur.fetchone()
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el caso.")
        return responder(_a_caso(fila), "caso")
