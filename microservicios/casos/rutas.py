import json
import logging
import math
import uuid
from datetime import datetime, timezone

import psycopg2
from flask import current_app, g, request

from epidemia_comun import alcance, limites
from epidemia_comun.auditoria import log_audit
from epidemia_comun.bd import get_conn
from epidemia_comun.errores import ErrorAPI
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.http import llamar
from epidemia_comun.seguridad import requiere_token, token_servicio
from epidemia_comun.validaciones import diccionario, entero_positivo, fecha

from . import captura, formularios, seguimiento

log = logging.getLogger(__name__)

# Matriz de permisos: cases.create = solo CAPTURISTA (D1; la migración 034 se lo quita al
# ADMINISTRADOR); cases.read = los cuatro roles. El monolito deja capturar a cualquier
# usuario autenticado; aquí se aplica la matriz.
ROLES_ESCRITURA = ("CAPTURISTA",)
# D42: INVESTIGADOR y AUTORIDAD_SANITARIA leen (cases.read); la app los deja consultar (D56). El
# alcance por región de cada cuenta (D43) acota lo que ve cualquiera de ellos.
ROLES_LECTURA = ("CAPTURISTA", "EPIDEMIOLOGO", "ANALISTA", "ADMINISTRADOR", "INVESTIGADOR",
                 "AUTORIDAD_SANITARIA")
# Los formularios por enfermedad los arman quienes dan de alta enfermedades (D48, D1).
ROLES_FORMULARIOS = ("EPIDEMIOLOGO", "ADMINISTRADOR")

ESTADOS = ("pendiente", "validado", "duplicado", "descartado")
MAXIMO_POR_PAGINA = 100
# Un lote de POST /cases/batch: el mismo tope que uno de sincronizacion.
MAXIMO_POR_LOTE = 100
BIGINT_MAX = 2 ** 63 - 1

CAMPOS_ENTRADA = ("local_uuid", "device_id", "disease_id", "region_id", "report_date",
                  "onset_date", "age", "sex", "latitude", "longitude", "test_result",
                  "severity")
CAMPOS_SALIDA = ("id", "local_uuid", "device_id", "reported_by", "disease_id", "enfermedad",
                 "region_id", "municipio", "age", "sex", "onset_date", "report_date",
                 "latitude", "longitude", "test_result", "severity", "status",
                 "created_at", "synced_at", "version", "updated_at", "updated_by",
                 "status_reason", "duplicate_of", "form_id", "form_answers")

_SELECT = """
    SELECT c.id, c.local_uuid, c.device_id, c.reported_by, c.disease_id, d.name,
           c.region_id, r.name, c.age, c.sex, c.onset_date, c.report_date,
           c.latitude, c.longitude, c.test_result, c.severity, c.status,
           c.created_at, c.synced_at, c.version, c.updated_at, c.updated_by,
           c.status_reason, c.duplicate_of, c.form_id, c.form_answers
    FROM cases c
    JOIN diseases d ON d.id = c.disease_id
    JOIN regions  r ON r.id = c.region_id
"""

_INSERTA = """
    INSERT INTO cases (local_uuid, device_id, reported_by, disease_id, region_id, age, sex,
                       onset_date, report_date, latitude, longitude, test_result,
                       severity, synced_at, form_id, form_answers)
    VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
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
    desconocidos = set(datos) - set(CAMPOS_ENTRADA) - {"form_id", "form_answers"}
    if desconocidos:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "Campos no reconocidos: " + ", ".join(sorted(str(c) for c in desconocidos)) + ".")
    entrada = {c: _texto_de_formulario(c, datos.get(c)) for c in CAMPOS_ENTRADA}
    # El formulario de la enfermedad (D48): la versión, como texto, y las respuestas, tal cual.
    entrada["form_id"] = _texto_de_formulario("form_id", datos.get("form_id"))
    entrada["form_answers"] = datos.get("form_answers")
    return entrada


def _entero_opcional(texto, campo):
    if texto is None or not str(texto).strip():
        return None
    try:
        valor = int(str(texto).strip())
    except ValueError:
        valor = 0
    if not 1 <= valor <= BIGINT_MAX:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser un entero positivo." % campo)
    return valor


def _version_de_formulario(form_id, vistos):
    clave = ("id", form_id)
    if clave not in vistos:
        vistos[clave] = formularios.por_id(form_id)
    return vistos[clave]


def _vigente(disease_id, vistos):
    clave = ("vigente", disease_id)
    if clave not in vistos:
        vigentes = formularios.vigentes(disease_id)
        vistos[clave] = vigentes[0] if vigentes else None
    return vistos[clave]


def _formulario_del_caso(form_id, crudas, disease_id, vistos):
    """(form_id, respuestas validadas) o (None, None) (D48). Sin formulario se acepta, salvo que
    la versión vigente de la enfermedad lo pida (required)."""
    if form_id is None:
        if crudas not in (None, "", {}):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "form_answers va con form_id: la versión del formulario.")
        vigente = _vigente(disease_id, vistos)
        if vigente and vigente["required"]:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "Esta enfermedad pide su formulario: manda form_id (%d, versión %d) y form_answers."
                           % (vigente["id"], vigente["version"]))
        return None, None
    formulario = formularios.para_caso(_version_de_formulario(form_id, vistos), disease_id)
    return form_id, formularios.respuestas(formulario, crudas if crudas is not None else {})


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


def _lista_de_casos(valor):
    """JSON trae una lista; XML trae <cases><item>..</item></cases>, que de_xml entrega como dict
    (un solo item) o dict con lista. Los mismos topes que un lote de sincronizacion."""
    if isinstance(valor, dict):
        valor = valor.get("item")
        if isinstance(valor, dict):
            valor = [valor]
    if not isinstance(valor, list) or not valor:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "cases debe traer al menos un caso.")
    if len(valor) > MAXIMO_POR_LOTE:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Un lote admite máximo %d casos." % MAXIMO_POR_LOTE)
    if any(not isinstance(c, dict) for c in valor):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Cada caso debe ser un objeto con campos.")
    return valor


def _catalogos():
    return captura.get_enfermedades_para_captura(), captura.get_municipios_catalogo()


def _verifica_dispositivo(device_id, vistos=None):
    """Un dispositivo ajeno es 422; uno revocado, 409 (comentario de devices)."""
    vistos = {} if vistos is None else vistos
    if device_id not in vistos:
        vistos[device_id] = captura.estado_para_captura(device_id, g.contexto.user_id)
    if vistos[device_id] == "ajeno":
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "device_id no es un dispositivo registrado de esta cuenta.")
    if vistos[device_id] == "revocado":
        raise ErrorAPI(409, "CONFLICTO",
                       "El dispositivo está revocado: ya no puede capturar ni sincronizar casos.")


# ------------------------------------------------- corrección, estado e historial (D47)

_ACTUALIZA = ("UPDATE cases SET {}, version = version + 1, updated_at = now(), updated_by = %s "
              "WHERE id = %s AND version = %s RETURNING version")
_HISTORIAL = """
    INSERT INTO case_history (case_id, version, action, changed_by, status_before, status_after,
                              changes, reason, device_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
"""
COLUMNAS_HISTORIAL = ("version", "action", "changed_by", "changed_at", "status_before",
                      "status_after", "changes", "reason", "device_id")


def _para_cambiar(cur, case_id):
    """El caso, bloqueado hasta el commit: dos cambios a la vez se forman en fila y el segundo
    ve la versión que dejó el primero."""
    cur.execute(_SELECT + " WHERE c.id = %s FOR UPDATE OF c", (case_id,))
    fila = cur.fetchone()
    if fila is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el caso.")
    return _a_caso(fila)


def _guarda_cambio(cur, actual, columnas, valores, accion, motivo, cambios, device_id, estado):
    cur.execute(_ACTUALIZA.format(", ".join("%s = %%s" % c for c in columnas)),
                tuple(valores) + (g.usuario["sub"], actual["id"], actual["version"]))
    fila = cur.fetchone()
    if fila is None:  # con el FOR UPDATE no pasa; si pasa, otro cambio ganó
        raise ErrorAPI(412, "CONFLICTO", "El caso cambió mientras se guardaba; vuelve a consultarlo.")
    cur.execute(_HISTORIAL, (actual["id"], fila[0], accion, g.usuario["sub"], actual["status"],
                             estado, json.dumps(cambios, ensure_ascii=False), motivo, device_id))
    cur.execute(_SELECT + " WHERE c.id = %s", (actual["id"],))
    return _a_caso(cur.fetchone())


def _con_version(respuesta, caso):
    respuesta.headers["ETag"] = seguimiento.etag(caso)
    return respuesta


def _restriccion(exc):
    restriccion = getattr(getattr(exc, "diag", None), "constraint_name", "") or ""
    return ErrorAPI(422, "DATOS_INVALIDOS",
                    "La base rechazó el cambio por una restricción: %s." % restriccion)


def _desconocidos(cuerpo, permitidos):
    desconocidos = set(cuerpo) - set(permitidos)
    if desconocidos:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "Campos no reconocidos: " + ", ".join(sorted(str(c) for c in desconocidos)) + ".")


def corrige(case_id, cuerpo, esperada):
    """PATCH /cases/{id}: los campos que vienen en el cuerpo, validados junto con el resto del
    caso. Regresa el caso como queda; si nada cambia, el mismo, sin subir la versión."""
    cuerpo = diccionario(cuerpo)
    _desconocidos(cuerpo, seguimiento.EDITABLES + ("reason", "device_id", "form_id", "form_answers"))
    pedidos = [c for c in seguimiento.EDITABLES if c in cuerpo]
    con_formulario = "form_id" in cuerpo or "form_answers" in cuerpo
    if not pedidos and not con_formulario:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Manda al menos un campo que corregir.")
    motivo = seguimiento.motivo(cuerpo, obligatorio=False)
    device_id = _dispositivo_opcional(_texto_de_formulario("device_id", cuerpo.get("device_id")))
    if device_id is not None:
        _verifica_dispositivo(device_id)
    enfermedades, municipios = _catalogos()
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                actual = _para_cambiar(cur, case_id)
                seguimiento.puede_corregir(actual)
                seguimiento.verifica_version(actual, esperada)
                seguimiento.puede_corregir_en_su_estado(actual)
                entrada = {c: _texto_de_formulario(c, actual[c]) for c in seguimiento.EDITABLES}
                entrada.update({c: _texto_de_formulario(c, cuerpo[c]) for c in pedidos})
                # Lo que no se corrige no se vuelve a juzgar contra el catálogo de hoy: una
                # enfermedad desactivada después de capturar el caso no lo deja congelado.
                enfermedades_validas = list(enfermedades) + (
                    [] if "disease_id" in pedidos else [{"id": actual["disease_id"]}])
                municipios_validos = list(municipios) + (
                    [] if "region_id" in pedidos else [{"id": actual["region_id"]}])
                datos, errores = captura.valida_caso(entrada, enfermedades_validas, municipios_validos)
                if errores:
                    raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
                diferencias = seguimiento.cambios(actual, datos, pedidos)
                valores = {c: datos[c] for c in diferencias}
                for campo, valor in _formulario_corregido(actual, cuerpo, datos["disease_id"],
                                                          con_formulario).items():
                    if valor != actual[campo]:
                        diferencias[campo] = {"antes": actual[campo], "despues": valor}
                        valores[campo] = (json.dumps(valor, ensure_ascii=False)
                                          if campo == "form_answers" and valor is not None else valor)
                if not diferencias:
                    return actual
                caso = _guarda_cambio(cur, actual, list(valores), list(valores.values()),
                                      "correccion", motivo, diferencias, device_id, actual["status"])
                log_audit(g.contexto, "UPDATE", "cases", case_id,
                          data_after={"version": caso["version"], "cambios": diferencias,
                                      "reason": motivo}, cur=cur)
            conn.commit()
    except (psycopg2.errors.CheckViolation, psycopg2.errors.ForeignKeyViolation) as exc:
        raise _restriccion(exc) from exc
    return caso


def _formulario_corregido(actual, cuerpo, disease_id, con_formulario):
    """{form_id, form_answers} como quedan tras la corrección, o {} si no cambian (D48)."""
    if not con_formulario:
        if actual["form_id"] is not None and disease_id != actual["disease_id"]:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "Cambiaste la enfermedad: manda form_id y form_answers de la nueva, o "
                           "form_id null para quitar el formulario.")
        return {}
    form_id = (_entero_opcional(_texto_de_formulario("form_id", cuerpo["form_id"]), "form_id")
               if "form_id" in cuerpo else actual["form_id"])
    crudas = cuerpo["form_answers"] if "form_answers" in cuerpo else actual["form_answers"]
    if form_id is None:
        if crudas not in (None, "", {}) and "form_answers" in cuerpo:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "form_answers va con form_id: la versión del formulario.")
        return {"form_id": None, "form_answers": None}
    if "form_id" in cuerpo and "form_answers" not in cuerpo and form_id != actual["form_id"]:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Con otra versión del formulario, manda también form_answers.")
    formulario = formularios.para_caso(formularios.por_id(form_id), disease_id)
    return {"form_id": form_id, "form_answers": formularios.respuestas(formulario, crudas or {})}


def cambia_estado(case_id, cuerpo, esperada):
    """POST /cases/{id}/status: validar, descartar, marcar duplicado o reabrir."""
    cuerpo = diccionario(cuerpo)
    _desconocidos(cuerpo, ("status", "reason", "duplicate_of"))
    nuevo = cuerpo.get("status")
    if not isinstance(nuevo, str) or nuevo not in seguimiento.TRANSICIONES:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "status debe ser uno de: %s." % ", ".join(seguimiento.TRANSICIONES))
    motivo = seguimiento.motivo(cuerpo, obligatorio=nuevo in seguimiento.CON_MOTIVO,
                                para="para pasar el caso a %s" % nuevo)
    original = None
    if nuevo == "duplicado":
        original = entero_positivo(_texto_de_formulario("duplicate_of", cuerpo.get("duplicate_of")),
                                   "duplicate_of")
    elif cuerpo.get("duplicate_of") not in (None, ""):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "duplicate_of solo va con status duplicado.")
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                actual = _para_cambiar(cur, case_id)
                seguimiento.verifica_version(actual, esperada)
                seguimiento.transicion(actual["status"], nuevo)
                if original is not None:
                    _verifica_original(cur, actual, original)
                cambios = {"status": {"antes": actual["status"], "despues": nuevo}}
                if actual["duplicate_of"] != original:
                    cambios["duplicate_of"] = {"antes": actual["duplicate_of"], "despues": original}
                caso = _guarda_cambio(cur, actual, ["status", "status_reason", "duplicate_of"],
                                      [nuevo, motivo, original], "estado", motivo, cambios, None, nuevo)
                log_audit(g.contexto, "UPDATE", "cases", case_id,
                          data_after={"version": caso["version"], "cambios": cambios,
                                      "reason": motivo}, cur=cur)
            conn.commit()
    except (psycopg2.errors.CheckViolation, psycopg2.errors.ForeignKeyViolation) as exc:
        raise _restriccion(exc) from exc
    if nuevo in ("descartado", "duplicado"):
        _avisa_rechazo(caso)
    return caso


def _verifica_original(cur, caso, original):
    if original == caso["id"]:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Un caso no puede ser duplicado de sí mismo.")
    cur.execute("SELECT id, disease_id, status FROM cases WHERE id = %s", (original,))
    fila = cur.fetchone()
    if fila is None:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "duplicate_of no es un caso que exista.")
    if fila[2] == "duplicado":
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "El caso %d también es un duplicado: apunta al original." % original)
    if fila[1] != caso["disease_id"]:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "El caso %d es de otra enfermedad: no puede ser el original." % original)


# Lo que un caso debería traer aunque no sea obligatorio (D49): sin ello sirve menos.
IMPORTANTES = (("age", "edad"), ("sex", "sexo"), ("onset_date", "inicio de síntomas"),
               ("test_result", "resultado de prueba"), ("severity", "gravedad"),
               ("latitude", "ubicación"))
_SIN_IMPORTANTES = " OR ".join("c.%s IS NULL" % campo for campo, _ in IMPORTANTES)


def faltantes(caso):
    return [nombre for campo, nombre in IMPORTANTES if caso.get(campo) is None]


def _avisa_incompletos(creados):
    """Un aviso DATA_INCOMPLETE a quien capturó, por captura o por lote, con lo que falta.
    Best-effort: el caso ya quedó guardado."""
    incompletos = [(c["id"], faltantes(c)) for c in creados if faltantes(c)]
    if not incompletos:
        return
    cuenta = {}
    for _, nombres in incompletos:
        for nombre in nombres:
            cuenta[nombre] = cuenta.get(nombre, 0) + 1
    if len(incompletos) == 1:
        titulo = "El caso %d tiene datos incompletos" % incompletos[0][0]
        detalle = ", ".join(cuenta)
    else:
        titulo = "%d casos con datos incompletos" % len(incompletos)
        detalle = ", ".join("%s (%d)" % par for par in cuenta.items())
    try:
        resp = llamar("notificaciones", "POST", "/api/v1/notifications", formato="json", timeout=3,
                      token=token_servicio(current_app.config, "casos"),
                      cuerpo={"user_id": int(g.usuario["sub"]), "type": "DATA_INCOMPLETE",
                              "title": titulo,
                              "body": "Falta: %s. Complétalos si tienes el dato." % detalle,
                              "payload": {"case_ids": [i for i, _ in incompletos], "faltantes": cuenta}})
        if resp.status_code >= 400:
            log.warning("notificaciones respondió %d al avisar datos incompletos", resp.status_code)
    except Exception as exc:
        log.warning("No se pudo avisar de datos incompletos: %s", exc)


def _avisa_rechazo(caso):
    """Best-effort, como los demás avisos: si notificaciones no responde, el cambio ya quedó."""
    if caso["status"] == "duplicado":
        titulo = "Tu caso %d se marcó como duplicado del %d" % (caso["id"], caso["duplicate_of"])
    else:
        titulo = "Tu caso %d se descartó" % caso["id"]
    try:
        resp = llamar("notificaciones", "POST", "/api/v1/notifications", formato="json", timeout=3,
                      token=token_servicio(current_app.config, "casos"),
                      cuerpo={"user_id": int(caso["reported_by"]), "type": "CASE_REJECTED",
                              "title": titulo, "body": caso["status_reason"] or "",
                              "payload": {"case_id": caso["id"], "status": caso["status"],
                                          "duplicate_of": caso["duplicate_of"],
                                          "version": caso["version"]}})
        if resp.status_code >= 400:
            log.warning("notificaciones respondió %d al avisar el caso %s", resp.status_code, caso["id"])
    except Exception as exc:  # incluye el 503 de llamar(): el cambio ya está guardado
        log.warning("No se pudo avisar el caso %s: %s", caso["id"], exc)


def _en_su_alcance(condiciones, params):
    """D43: una cuenta con alcance por región solo ve los casos de sus municipios. Una nacional
    no cambia la consulta."""
    permitidas = alcance.regiones_permitidas()
    if permitidas is not None:
        condiciones.append("c.region_id = ANY(%s)")
        params.append(sorted(permitidas))


def _region_del_caso(case_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT region_id FROM cases WHERE id = %s", (case_id,))
            fila = cur.fetchone()
    return fila[0] if fila else None


def historial(case_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version FROM cases WHERE id = %s", (case_id,))
            fila = cur.fetchone()
            if fila is None:
                raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el caso.")
            cur.execute("SELECT " + ", ".join(COLUMNAS_HISTORIAL) + " FROM case_history "
                        "WHERE case_id = %s ORDER BY version", (case_id,))
            cambios = [dict(zip(COLUMNAS_HISTORIAL, f)) for f in cur.fetchall()]
    return {"case_id": case_id, "version": fila[0], "cambios": cambios}


def _crea(entrada, catalogos=None, dispositivos_vistos=None, formularios_vistos=None):
    """Crea un caso: (201, caso), o (200, caso) si su local_uuid ya existía. Lanza ErrorAPI 422 o
    409 si no pasa. Un lote comparte `catalogos` y `dispositivos_vistos` para no repetir las
    mismas consultas en cada caso."""
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
            return 200, previo

    # Un dispositivo revocado no captura aunque el token siga vigente (comentario de devices).
    if device_id is not None:
        _verifica_dispositivo(device_id, dispositivos_vistos)

    enfermedades, municipios = catalogos or _catalogos()
    datos, errores = captura.valida_caso(entrada, enfermedades, municipios)
    if errores:
        raise ErrorAPI(422, "DATOS_INVALIDOS", " ".join(errores))
    form_id, respuestas = _formulario_del_caso(
        _entero_opcional(entrada.get("form_id"), "form_id"), entrada.get("form_answers"),
        datos["disease_id"], {} if formularios_vistos is None else formularios_vistos)
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
                    datos["test_result"], datos["severity"], sincronizado, form_id,
                    None if respuestas is None else json.dumps(respuestas, ensure_ascii=False)))
                nuevo = cur.fetchone()
                if nuevo is None:
                    # Otra petición con el mismo local_uuid ganó la carrera.
                    previo = _existente(cur, local_uuid)
                    conn.rollback()
                    previo["duplicado"] = True
                    return 200, previo
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
    return 201, caso


def registrar(app):
    @app.post("/api/v1/cases")
    @requiere_token(roles=ROLES_ESCRITURA)
    def crear():
        estado, caso = _crea(_leer_caso(leer_cuerpo()))
        if estado == 201:
            _avisa_incompletos([caso])
        return responder(caso, "caso", estado=estado)

    @app.post("/api/v1/cases/batch")
    @requiere_token(roles=ROLES_ESCRITURA)
    def crear_lote():
        """Varios casos en una sola petición; la usa sincronizacion (F4). Cada caso tiene el
        resultado que tendría en POST /cases (201, 200 si ya existía, 409 o 422), en el mismo
        orden y en su propia transacción: uno rechazado no detiene a los demás. El límite de D31
        cuenta los casos, no la petición, en la misma cuenta que POST /cases. Si la base o algo
        más falla, el lote completo responde 503 y se reenvía: local_uuid evita duplicados."""
        cuerpo = diccionario(leer_cuerpo())
        desconocidos = set(cuerpo) - {"cases"}
        if desconocidos:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "Campos no reconocidos: " + ", ".join(sorted(str(c) for c in desconocidos)) + ".")
        casos = _lista_de_casos(cuerpo.get("cases"))
        limites.consumir(g.usuario["sub"], cantidad=len(casos), ruta="POST:/api/v1/cases")
        catalogos, vistos, versiones, resultados = _catalogos(), {}, {}, []
        for indice, crudo in enumerate(casos):
            try:
                estado, caso = _crea(_leer_caso(crudo), catalogos, vistos, versiones)
                resultados.append({"indice": indice, "estado": estado, "caso": caso})
            except ErrorAPI as error:
                if error.estado not in (409, 422):
                    raise
                resultados.append({"indice": indice, "estado": error.estado,
                                   "codigo": error.codigo, "detail": error.detalle})
        # Un solo aviso de datos incompletos por lote (D49), solo de los casos nuevos.
        _avisa_incompletos([r["caso"] for r in resultados if r["estado"] == 201])
        return responder({"total": len(resultados), "resultados": resultados}, "resultado_lote_casos")

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
            if sexo not in captura.SEXOS:
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
        _en_su_alcance(condiciones, params)
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

    # Los casos a los que les falta algo importante (D49): el panel del capturista. Cada quien ve los
    # que capturó; los demás roles, todos. Sin los descartados ni los duplicados.
    @app.get("/api/v1/cases/incomplete")
    @requiere_token(roles=ROLES_LECTURA)
    def incompletos():
        pagina = entero_positivo(request.args.get("page", "1"), "page")
        por_pagina = entero_positivo(request.args.get("per_page", "20"), "per_page")
        if por_pagina > MAXIMO_POR_PAGINA:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "per_page no puede ser mayor que %d." % MAXIMO_POR_PAGINA)
        condiciones = ["c.status IN ('pendiente', 'validado')", "(%s)" % _SIN_IMPORTANTES]
        params = []
        if set(g.usuario.get("roles") or []) <= {"CAPTURISTA"}:
            condiciones.append("c.reported_by = %s")
            params.append(g.usuario["sub"])
        _en_su_alcance(condiciones, params)
        donde = " WHERE " + " AND ".join(condiciones)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM cases c" + donde, tuple(params))
                total = cur.fetchone()[0]
                cur.execute(_SELECT + donde + " ORDER BY c.report_date DESC, c.id DESC"
                            " LIMIT %s OFFSET %s",
                            tuple(params) + (por_pagina, (pagina - 1) * por_pagina))
                casos = [_a_caso(f) for f in cur.fetchall()]
        for caso in casos:
            caso["faltantes"] = faltantes(caso)
        return responder({"casos": casos, "total": total, "pagina": pagina, "por_pagina": por_pagina,
                          "paginas": int(math.ceil(total / float(por_pagina)))}, "casos_incompletos")

    @app.get("/api/v1/cases/<int:case_id>")
    @requiere_token(roles=ROLES_LECTURA)
    def detalle(case_id):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(_SELECT + " WHERE c.id = %s", (case_id,))
                fila = cur.fetchone()
        if fila is None:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el caso.")
        caso = _a_caso(fila)
        alcance.exige_region(caso["region_id"])
        return _con_version(responder(caso, "caso"), caso)

    # Corregir datos (D47): el EPIDEMIOLOGO cualquiera pendiente o validado; el CAPTURISTA los
    # suyos mientras estén pendientes. If-Match con la versión que se leyó.
    @app.patch("/api/v1/cases/<int:case_id>")
    @requiere_token(roles=seguimiento.ROLES_CORRIGEN)
    def corregir(case_id):
        cuerpo = leer_cuerpo()  # un cuerpo ilegible es 400 antes de mirar If-Match
        caso = corrige(case_id, cuerpo, seguimiento.version_pedida())
        return _con_version(responder(caso, "caso"), caso)

    # Validar, descartar, marcar duplicado o reabrir (D47): solo el EPIDEMIOLOGO.
    @app.post("/api/v1/cases/<int:case_id>/status")
    @requiere_token(roles=seguimiento.ROLES_REVISAN)
    def cambiar_estado(case_id):
        cuerpo = leer_cuerpo()
        caso = cambia_estado(case_id, cuerpo, seguimiento.version_pedida())
        return _con_version(responder(caso, "caso"), caso)

    # ---------------------------------------------- formularios por enfermedad (D48)

    def _puede_ver_borradores():
        return bool(set(g.usuario.get("roles") or []) & set(ROLES_FORMULARIOS))

    @app.get("/api/v1/forms")
    @requiere_token(roles=ROLES_LECTURA)
    def lista_formularios():
        disease_id = _entero_de_consulta("disease_id")
        estado = request.args.get("status")
        if estado is not None and estado not in ("borrador", "publicado", "retirado"):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "status debe ser borrador, publicado o retirado.")
        filas = formularios.lista(disease_id, estado)
        if not _puede_ver_borradores():
            filas = [f for f in filas if f["status"] != "borrador"]
        return responder({"total": len(filas), "formularios": filas}, "lista_formularios")

    # La versión vigente de cada enfermedad (o de una): lo que la app guarda para capturar sin red.
    @app.get("/api/v1/forms/current")
    @requiere_token(roles=ROLES_LECTURA)
    def formularios_vigentes():
        filas = formularios.vigentes(_entero_de_consulta("disease_id"))
        return responder({"total": len(filas), "formularios": filas}, "lista_formularios")

    @app.get("/api/v1/forms/<int:form_id>")
    @requiere_token(roles=ROLES_LECTURA)
    def formulario(form_id):
        fila = formularios.por_id(form_id)
        if fila is None or (fila["status"] == "borrador" and not _puede_ver_borradores()):
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el formulario.")
        return responder(fila, "formulario")

    @app.post("/api/v1/forms")
    @requiere_token(roles=ROLES_FORMULARIOS)
    def crea_formulario():
        cuerpo = diccionario(leer_cuerpo())
        _desconocidos(cuerpo, ("disease_id", "title", "fields", "required"))
        disease_id = entero_positivo(_texto_de_formulario("disease_id", cuerpo.get("disease_id")), "disease_id")
        nuevo = formularios.crea_borrador(disease_id, formularios.definicion(cuerpo), g.usuario["sub"])
        log_audit(g.contexto, "CREATE", "case_forms", nuevo["id"],
                  data_after={"disease_id": disease_id, "version": nuevo["version"]})
        return responder(nuevo, "formulario", estado=201)

    @app.put("/api/v1/forms/<int:form_id>")
    @requiere_token(roles=ROLES_FORMULARIOS)
    def reemplaza_formulario(form_id):
        cuerpo = diccionario(leer_cuerpo())
        _desconocidos(cuerpo, ("title", "fields", "required"))
        fila = formularios.reemplaza_borrador(form_id, formularios.definicion(cuerpo))
        log_audit(g.contexto, "UPDATE", "case_forms", form_id, data_after={"version": fila["version"]})
        return responder(fila, "formulario")

    @app.post("/api/v1/forms/<int:form_id>/publish")
    @requiere_token(roles=ROLES_FORMULARIOS)
    def publica_formulario(form_id):
        fila = formularios.publica(form_id, g.usuario["sub"])
        log_audit(g.contexto, "UPDATE", "case_forms", form_id,
                  data_after={"status": "publicado", "version": fila["version"]})
        return responder(fila, "formulario")

    @app.get("/api/v1/cases/<int:case_id>/history")
    @requiere_token(roles=ROLES_LECTURA)
    def historial_de_caso(case_id):
        alcance.exige_region_de(lambda: _region_del_caso(case_id))
        return responder(historial(case_id), "historial_caso")
