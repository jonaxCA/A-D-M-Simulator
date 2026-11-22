import json
import logging
import os
import uuid
from datetime import datetime, timezone

from flask import current_app, g, request

from backend_web.audit import log_audit
from epidemia_comun import llaves
from epidemia_comun.candados import CandadoOcupado, candado
from epidemia_comun.errores import ErrorAPI, respuesta_error
from epidemia_comun.formatos import leer_cuerpo, responder
from epidemia_comun.http import llamar
from epidemia_comun.redis_compartido import RedisNoDisponible, requerido
from epidemia_comun.seguridad import requiere_token, token_servicio
from epidemia_comun.validaciones import diccionario

log = logging.getLogger(__name__)

# Solo el CAPTURISTA captura (D1); el ADMINISTRADOR consulta cualquier lote.
ROLES_ENVIAN = ("CAPTURISTA",)
ROLES_LEEN = ("CAPTURISTA", "ADMINISTRADOR")
MAXIMO_CASOS = 100
# Una corrección hecha sin conexión (D47): el caso, la versión que tenía el teléfono, los campos
# que cambiaron y el motivo.
CAMPOS_ACTUALIZACION = {"case_id", "version", "changes", "reason"}
# Cuánto se recuerda un lote: una semana cubre un dispositivo sin red varios días.
TTL_LOTE = 7 * 24 * 3600
# Un lote de 100 casos con la espera máxima de llamar() (5 s) rebasaría esto solo en un
# día muy malo; si vence, local_uuid sigue evitando duplicados en casos.
TTL_CANDADO = 300


def _ttl_lote():
    try:
        return int(os.environ.get("SYNC_LOTE_TTL_SECONDS", TTL_LOTE))
    except ValueError:
        return TTL_LOTE


def llave_candado(lote_id):
    return llaves.candado_lote(lote_id)


def _lista_de_casos(valor):
    """JSON trae una lista; XML trae <cases><item>..</item></cases>, que de_xml entrega
    como dict (un solo item) o dict con lista."""
    if isinstance(valor, dict):
        valor = valor.get("item")
        if isinstance(valor, dict):
            valor = [valor]
    if not isinstance(valor, list) or not valor:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "cases debe traer al menos un caso.")
    if len(valor) > MAXIMO_CASOS:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "Un lote admite máximo %d casos." % MAXIMO_CASOS)
    if any(not isinstance(c, dict) for c in valor):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "Cada caso debe ser un objeto con campos.")
    return valor


def _vacio(valor):
    return valor in (None, "", [], {})


def _entero(valor, campo):
    texto = str(valor).strip() if isinstance(valor, (int, str)) and not isinstance(valor, bool) else ""
    if not texto.isdigit() or int(texto) < 1:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser un entero positivo." % campo)
    return int(texto)


def _lista_de_actualizaciones(valor):
    """Como cases: una lista en JSON, <updates><item>..</item></updates> en XML."""
    if isinstance(valor, dict):
        valor = valor.get("item")
        if isinstance(valor, dict):
            valor = [valor]
    if not isinstance(valor, list) or any(not isinstance(a, dict) for a in valor):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "updates debe ser una lista de correcciones.")
    salida = []
    for a in valor:
        desconocidos = set(a) - CAMPOS_ACTUALIZACION
        if desconocidos:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Campos no reconocidos en updates: "
                           + ", ".join(sorted(str(c) for c in desconocidos)) + ".")
        if not isinstance(a.get("changes"), dict) or not a["changes"]:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Cada corrección necesita changes con al menos un campo.")
        if a.get("reason") is not None and not isinstance(a["reason"], str):
            raise ErrorAPI(422, "DATOS_INVALIDOS", "reason debe ser texto.")
        salida.append({"case_id": _entero(a.get("case_id"), "case_id"),
                       "version": _entero(a.get("version"), "version"),
                       "changes": a["changes"], "reason": a.get("reason")})
    return salida


def _leer_lote(cuerpo):
    datos = diccionario(cuerpo)
    desconocidos = set(datos) - {"batch_id", "lote_id", "device_id", "cases", "updates"}
    if desconocidos:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "Campos no reconocidos: " + ", ".join(sorted(str(c) for c in desconocidos)) + ".")
    crudo = datos.get("batch_id") or datos.get("lote_id")
    if datos.get("batch_id") and datos.get("lote_id") and datos["batch_id"] != datos["lote_id"]:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "batch_id y lote_id no coinciden.")
    lote_id = _uuid(crudo, "batch_id")
    # Un lote trae casos nuevos, correcciones (D47) o las dos cosas.
    actualizaciones = [] if _vacio(datos.get("updates")) else _lista_de_actualizaciones(datos["updates"])
    casos = [] if actualizaciones and _vacio(datos.get("cases")) else _lista_de_casos(datos.get("cases"))
    if len(casos) + len(actualizaciones) > MAXIMO_CASOS:
        raise ErrorAPI(422, "DATOS_INVALIDOS",
                       "Un lote admite máximo %d casos y correcciones en total." % MAXIMO_CASOS)
    for caso in casos:
        if not isinstance(caso.get("local_uuid"), str) or not caso["local_uuid"].strip():
            raise ErrorAPI(422, "DATOS_INVALIDOS", "Cada caso necesita su local_uuid.")
        _uuid(caso["local_uuid"], "local_uuid")
    device = datos.get("device_id")
    if isinstance(device, bool) or (device is not None and not isinstance(device, (int, str))):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "device_id debe ser un entero positivo.")
    return lote_id, device, casos, actualizaciones


def _uuid(valor, campo):
    try:
        return str(uuid.UUID(str(valor).strip()))
    except (ValueError, AttributeError):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "%s debe ser un UUID válido." % campo)


def _leer_guardado(lote_id):
    crudo = requerido("lote_leer", lambda r: r.get(llaves.lote(lote_id)))
    return json.loads(crudo) if crudo else None


def _publico(guardado, repetido):
    salida = {k: v for k, v in guardado.items() if k != "user_id"}
    salida["repetido"] = repetido
    return salida


def _resultado_de_caso(indice, local_uuid, respuesta):
    estado = respuesta.status_code
    try:
        cuerpo = respuesta.json()
    except ValueError:
        cuerpo = {}
    if not isinstance(cuerpo, dict):
        cuerpo = {}
    if estado in (200, 201):
        return {"indice": indice, "local_uuid": local_uuid,
                "resultado": "creado" if estado == 201 else "duplicado",
                "case_id": cuerpo.get("id"), "codigo": None, "errores": []}
    detalle = cuerpo.get("detail") or "El servicio de casos rechazó el caso."
    if estado in (400, 409, 413, 415, 422):
        # El codigo distingue un teléfono revocado (CONFLICTO, todo el lote) de datos que hay
        # que corregir (DATOS_INVALIDOS): la app no tiene que leer el mensaje.
        codigo = cuerpo.get("codigo") or ("CONFLICTO" if estado == 409 else "DATOS_INVALIDOS")
        return {"indice": indice, "local_uuid": local_uuid, "resultado": "rechazado",
                "case_id": None, "codigo": codigo, "errores": [detalle]}
    if estado == 429:
        # El límite por cuenta de casos (D31) llega tal cual, con su Retry-After: la app espera y
        # reenvía el lote, y local_uuid evita duplicar lo que ya se creó. Como 503, la app
        # reintentaba de inmediato contra el mismo límite (lo encontró la prueba de carga, F4).
        espera = getattr(respuesta, "headers", {}).get("Retry-After") or "60"
        raise ErrorAPI(429, "LIMITE_EXCEDIDO", detalle, {"Retry-After": espera})
    # 401/403 (el token ya no sirve o no alcanza), 5xx u otra cosa: no es culpa del caso.
    codigo = cuerpo.get("codigo") or "TOKEN_INVALIDO"
    if estado in (401, 403):
        raise ErrorAPI(estado, codigo, detalle)
    raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio de casos no pudo procesar el lote.")


class _RespuestaDeCaso:
    """El resultado de un caso dentro de la respuesta de POST /cases/batch, con la forma que
    espera _resultado_de_caso (la de una respuesta de POST /cases)."""

    def __init__(self, estado, cuerpo):
        self.status_code, self._cuerpo, self.headers = estado, cuerpo, {}

    def json(self):
        return self._cuerpo


def _envia_a_casos(casos, cuerpos, token):
    """Todo el lote en una sola llamada a casos (POST /api/v1/cases/batch). Antes era una llamada
    por caso, y con carga un lote de 5 tardaba segundos (prueba de carga en la nube, F4). Si casos
    todavía no tiene esa ruta (404 o 405), caso por caso como antes."""
    respuesta = llamar("casos", "POST", "/api/v1/cases/batch", formato="json",
                       cuerpo={"cases": cuerpos}, token=token)
    if respuesta.status_code in (404, 405):
        return [_resultado_de_caso(i, caso["local_uuid"],
                                   llamar("casos", "POST", "/api/v1/cases", formato="json",
                                          cuerpo=cuerpo, token=token))
                for i, (caso, cuerpo) in enumerate(zip(casos, cuerpos))]
    if respuesta.status_code != 200:
        if respuesta.status_code in (401, 403, 429) or respuesta.status_code >= 500:
            _resultado_de_caso(0, casos[0]["local_uuid"], respuesta)  # lanza el error que toca
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio de casos no pudo procesar el lote.")
    try:
        filas = respuesta.json().get("resultados")
    except (ValueError, AttributeError):
        filas = None
    if not isinstance(filas, list) or len(filas) != len(casos):
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio de casos no pudo procesar el lote.")
    resultados = []
    for indice, (caso, fila) in enumerate(zip(casos, filas)):
        estado = fila.get("estado")
        cuerpo = fila.get("caso") if estado in (200, 201) else {
            "codigo": fila.get("codigo"), "detail": fila.get("detail")}
        resultados.append(_resultado_de_caso(indice, caso["local_uuid"],
                                             _RespuestaDeCaso(estado, cuerpo or {})))
    return resultados


def _cuerpo_json(respuesta):
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return {}
    return cuerpo if isinstance(cuerpo, dict) else {}


def _mismo(pedido, actual):
    if pedido is None or actual is None:
        return pedido is None and actual is None
    if isinstance(pedido, (int, float)) and not isinstance(pedido, bool):
        try:
            return abs(float(pedido) - float(actual)) < 1e-6
        except (TypeError, ValueError):
            return False
    return str(pedido) == str(actual)


def _ya_aplicada(cambios, caso):
    """Un lote que falló a medias se reenvía completo: una corrección que ya entró choca con su
    propia versión. Si el caso ya tiene exactamente lo que se pidió, no es un conflicto."""
    return all(campo in caso and _mismo(valor, caso[campo]) for campo, valor in cambios.items())


def _resultado_de_actualizacion(indice, actualizacion, respuesta, token):
    estado, cuerpo = respuesta.status_code, _cuerpo_json(respuesta)
    base = {"indice": indice, "case_id": actualizacion["case_id"]}
    if estado == 200:
        return dict(base, resultado="actualizado", version=cuerpo.get("version"), codigo=None,
                    errores=[], caso=None)
    detalle = cuerpo.get("detail") or "El servicio de casos rechazó la corrección."
    if estado == 412:
        # Alguien cambió el caso desde que el teléfono lo leyó: se regresa como está ahora, para
        # que la app muestre el conflicto y la persona decida. Nunca se sobrescribe.
        actual = llamar("casos", "GET", "/api/v1/cases/%d" % actualizacion["case_id"],
                        formato="json", token=token)
        caso = _cuerpo_json(actual) if actual.status_code == 200 else None
        if caso and _ya_aplicada(actualizacion["changes"], caso):
            return dict(base, resultado="actualizado", version=caso.get("version"), codigo=None,
                        errores=[], caso=None)
        return dict(base, resultado="conflicto", version=(caso or {}).get("version"),
                    codigo="CONFLICTO", errores=[detalle], caso=caso)
    if estado in (400, 403, 404, 409, 413, 415, 422, 428):
        return dict(base, resultado="rechazado", version=None,
                    codigo=cuerpo.get("codigo") or "DATOS_INVALIDOS", errores=[detalle], caso=None)
    if estado == 429:
        espera = getattr(respuesta, "headers", {}).get("Retry-After") or "60"
        raise ErrorAPI(429, "LIMITE_EXCEDIDO", detalle, {"Retry-After": espera})
    if estado == 401:
        raise ErrorAPI(401, cuerpo.get("codigo") or "TOKEN_INVALIDO", detalle)
    raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio de casos no pudo procesar el lote.")


def _aplica_actualizaciones(actualizaciones, device_id, token):
    """Una corrección por llamada a PATCH /cases/{id}, con If-Match: la versión que tenía el
    teléfono (D47). Cada una tiene su resultado: actualizado, conflicto o rechazado."""
    resultados = []
    for indice, a in enumerate(actualizaciones):
        cuerpo = dict(a["changes"])
        if a["reason"]:
            cuerpo["reason"] = a["reason"]
        if device_id is not None:
            cuerpo.setdefault("device_id", device_id)
        respuesta = llamar("casos", "PATCH", "/api/v1/cases/%d" % a["case_id"], formato="json",
                           cuerpo=cuerpo, token=token, cabeceras={"If-Match": '"%d"' % a["version"]})
        resultados.append(_resultado_de_actualizacion(indice, a, respuesta, token))
    return resultados


def _bitacora(lote_id, resumen):
    # sincronizacion no escribe tablas: solo deja un SYNC por lote, en su propia transacción.
    try:
        log_audit(g.contexto, "SYNC", "sync_batches", lote_id, data_after=resumen)
    except Exception:
        log.exception("No se pudo registrar el SYNC del lote %s", lote_id)


def _avisar_casos_nuevos(guardado):
    # Un solo aviso por lote. Solo se llama cuando el lote se procesa por primera vez: un
    # reintento lo contesta _repetido_o_none con lo guardado, sin llegar aquí. Si falla, el lote
    # ya está guardado: solo se anota.
    n = guardado["creados"]
    try:
        resp = llamar("notificaciones", "POST", "/api/v1/notifications", formato="json", timeout=3,
                      token=token_servicio(current_app.config, "sincronizacion"),
                      cuerpo={"role": "EPIDEMIOLOGO", "type": "NEW_CASES",
                              "title": "Lote con %d caso%s nuevo%s" % (n, "" if n == 1 else "s",
                                                                       "" if n == 1 else "s"),
                              "body": "Un lote sincronizado desde un dispositivo trajo %d caso%s nuevo%s."
                                      % (n, "" if n == 1 else "s", "" if n == 1 else "s"),
                              "payload": {"batch_id": guardado["batch_id"], "creados": n,
                                          "total": guardado["total"]}})
        if resp.status_code >= 400:
            log.warning("notificaciones respondió %d al avisar el lote %s",
                        resp.status_code, guardado["batch_id"])
    except Exception as exc:
        log.warning("No se pudo avisar el lote %s: %s", guardado["batch_id"], exc)


def registrar(app):
    @app.errorhandler(RedisNoDisponible)
    def redis_caido(exc):
        return respuesta_error(ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "Redis no está disponible."))

    @app.errorhandler(CandadoOcupado)
    def lote_ocupado(exc):
        return respuesta_error(ErrorAPI(409, "CONFLICTO", "Ese lote ya se está procesando; intenta de nuevo."))

    def _repetido_o_none(lote_id):
        guardado = _leer_guardado(lote_id)
        if guardado is None:
            return None
        if guardado.get("user_id") != g.contexto.user_id:
            raise ErrorAPI(409, "CONFLICTO", "Ese lote ya fue enviado por otra persona.")
        return responder(_publico(guardado, True), "resultado_lote")

    @app.post("/api/v1/sync/cases")
    @requiere_token(roles=ROLES_ENVIAN)
    def enviar():
        lote_id, device_id, casos, actualizaciones = _leer_lote(leer_cuerpo())
        previo = _repetido_o_none(lote_id)
        if previo is not None:
            return previo
        token = request.headers.get("Authorization", "")[7:].strip()
        with candado(llave_candado(lote_id), TTL_CANDADO):
            # Otra petición pudo terminar el mismo lote entre la primera lectura y el candado.
            previo = _repetido_o_none(lote_id)
            if previo is not None:
                return previo
            cuerpos = []
            for caso in casos:
                cuerpo = {k: v for k, v in caso.items()}
                if device_id is not None and cuerpo.get("device_id") in (None, ""):
                    cuerpo["device_id"] = device_id
                cuerpos.append(cuerpo)
            # Sin reintentos: si casos no contesta, todo el lote responde 503 y el cliente lo
            # reenvía; local_uuid evita duplicar lo que ya se hubiera creado.
            resultados = _envia_a_casos(casos, cuerpos, token) if casos else []
            cuenta = {"creado": 0, "duplicado": 0, "rechazado": 0}
            for r in resultados:
                cuenta[r["resultado"]] += 1
            guardado = {"batch_id": lote_id, "device_id": device_id,
                        "recibido_en": datetime.now(timezone.utc).isoformat(),
                        "total": len(resultados), "creados": cuenta["creado"],
                        "duplicados": cuenta["duplicado"], "rechazados": cuenta["rechazado"],
                        "resultados": resultados, "user_id": g.contexto.user_id}
            if actualizaciones:
                # Después de los casos nuevos. Un reenvío del lote ya guardado no llega aquí, así
                # que una corrección nunca se aplica dos veces ni choca consigo misma.
                hechas = _aplica_actualizaciones(actualizaciones, device_id, token)
                guardado.update(
                    actualizados=sum(r["resultado"] == "actualizado" for r in hechas),
                    conflictos=sum(r["resultado"] == "conflicto" for r in hechas),
                    actualizaciones_rechazadas=sum(r["resultado"] == "rechazado" for r in hechas),
                    actualizaciones=hechas)
            requerido("lote_guardar", lambda r: r.set(
                llaves.lote(lote_id), json.dumps(guardado, ensure_ascii=False), ex=_ttl_lote()))
            if guardado["creados"]:
                _avisar_casos_nuevos(guardado)
        _bitacora(lote_id, {"batch_id": lote_id, "device_id": device_id, "total": guardado["total"],
                            "creados": guardado["creados"], "duplicados": guardado["duplicados"],
                            "rechazados": guardado["rechazados"],
                            **{k: guardado[k] for k in ("actualizados", "conflictos",
                                                        "actualizaciones_rechazadas") if k in guardado}})
        return responder(_publico(guardado, False), "resultado_lote")

    @app.get("/api/v1/sync/batches/<batch_id>")
    @requiere_token(roles=ROLES_LEEN)
    def consultar(batch_id):
        lote_id = _uuid(batch_id, "batch_id")
        guardado = _leer_guardado(lote_id)
        propio = guardado is not None and (
            guardado.get("user_id") == g.contexto.user_id
            or "ADMINISTRADOR" in g.usuario.get("roles", []))
        if not propio:
            raise ErrorAPI(404, "NO_ENCONTRADO", "No existe ese lote, o ya venció.")
        return responder(_publico(guardado, True), "resultado_lote")
