"""Corregir un caso y cambiar su estado, con control de versión e historial (D47, F7).

Las reglas (D47):

- Corregir datos (PATCH /cases/{id}): el EPIDEMIOLOGO, cualquier caso pendiente o validado; el
  CAPTURISTA, solo los que capturó y mientras estén pendientes. Uno descartado o duplicado se
  reabre antes de corregirlo.
- Cambiar el estado (POST /cases/{id}/status): solo el EPIDEMIOLOGO, con las transiciones de
  TRANSICIONES. Descartar, marcar duplicado y reabrir piden motivo; duplicado, además, el caso
  original.
- Todo cambio manda en If-Match la versión que leyó (el ETag de GET /cases/{id}). Si el caso
  cambió desde entonces, 412 con el ETag de la versión actual y nada se toca: nunca se sobrescribe
  en silencio lo que hizo otra persona. Sin If-Match, 428.
- Cada cambio sube la versión, deja una fila en case_history y se audita.

Aquí van las reglas que no tocan la base; rutas.py las aplica dentro de la transacción.
"""
from datetime import date, datetime
from decimal import Decimal

from flask import g, request

from epidemia_comun.errores import ErrorAPI

ROLES_CORRIGEN = ("CAPTURISTA", "EPIDEMIOLOGO")
ROLES_REVISAN = ("EPIDEMIOLOGO",)
EDITABLES = ("disease_id", "region_id", "report_date", "onset_date", "age", "sex",
             "latitude", "longitude", "test_result", "severity")
# Estado actual -> a cuáles puede pasar.
TRANSICIONES = {"pendiente": ("validado", "descartado", "duplicado"),
                "validado": ("descartado", "duplicado", "pendiente"),
                "descartado": ("pendiente",),
                "duplicado": ("pendiente",)}
# Descartar, marcar duplicado y reabrir (volver a pendiente) se explican.
CON_MOTIVO = ("descartado", "duplicado", "pendiente")
CORREGIBLES = ("pendiente", "validado")
MOTIVO_MAXIMO = 500


def version_pedida():
    """La versión de If-Match: «3», «"3"» o «W/"3"». 428 si no viene."""
    crudo = (request.headers.get("If-Match") or "").strip()
    if not crudo:
        raise ErrorAPI(428, "DATOS_INVALIDOS",
                       "Manda en If-Match la versión del caso que leíste (su ETag), por ejemplo \"3\".")
    valor = crudo[2:] if crudo.startswith("W/") else crudo
    valor = valor.strip().strip('"')
    if not valor.isdigit() or int(valor) < 1 or len(valor) > 9:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "If-Match debe ser la versión del caso, por ejemplo \"3\".")
    return int(valor)


def etag(caso):
    return '"%d"' % caso["version"]


def verifica_version(caso, esperada):
    if caso["version"] != esperada:
        raise ErrorAPI(412, "CONFLICTO",
                       "El caso cambió desde que lo leíste: tenías la versión %d y ya va en la %d. "
                       "Vuelve a consultarlo y decide con lo que tiene ahora." % (esperada, caso["version"]),
                       {"ETag": etag(caso)})


def puede_corregir(caso):
    """403 o 409 antes de comparar versiones: quién puede tocar este caso."""
    roles = g.usuario.get("roles") or []
    if "EPIDEMIOLOGO" not in roles and str(caso["reported_by"]) != str(g.usuario["sub"]):
        raise ErrorAPI(403, "PERMISO_INSUFICIENTE", "Solo puedes corregir los casos que capturaste.")


def puede_corregir_en_su_estado(caso):
    """Después de comparar versiones: el estado que se leyó admite la corrección."""
    roles = g.usuario.get("roles") or []
    if "EPIDEMIOLOGO" not in roles and caso["status"] != "pendiente":
        raise ErrorAPI(403, "PERMISO_INSUFICIENTE",
                       "Solo puedes corregir tus casos mientras están pendientes; ya está %s." % caso["status"])
    if caso["status"] not in CORREGIBLES:
        raise ErrorAPI(409, "CONFLICTO",
                       "El caso está %s: reábrelo (status pendiente) antes de corregirlo." % caso["status"])


def motivo(cuerpo, obligatorio, para=""):
    valor = cuerpo.get("reason")
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obligatorio:
            raise ErrorAPI(422, "DATOS_INVALIDOS", "reason es obligatorio %s." % para)
        return None
    if not isinstance(valor, str):
        raise ErrorAPI(422, "DATOS_INVALIDOS", "reason debe ser texto.")
    valor = valor.strip()
    if len(valor) > MOTIVO_MAXIMO:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "reason no puede pasar de %d caracteres." % MOTIVO_MAXIMO)
    return valor


def transicion(actual, nuevo):
    if nuevo not in TRANSICIONES:
        raise ErrorAPI(422, "DATOS_INVALIDOS", "status debe ser uno de: %s." % ", ".join(TRANSICIONES))
    if nuevo not in TRANSICIONES[actual]:
        raise ErrorAPI(409, "CONFLICTO", "Un caso %s no puede pasar a %s; desde %s puede pasar a: %s."
                       % (actual, nuevo, actual, ", ".join(TRANSICIONES[actual])))


def a_json(valor):
    """Para case_history.changes y la auditoría: fechas en ISO y decimales como número."""
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def igual(campo, antes, despues):
    # La base guarda las coordenadas con 6 decimales: 25.68 y 25.680000 son la misma.
    if campo in ("latitude", "longitude") and antes is not None and despues is not None:
        return round(Decimal(str(antes)), 6) == round(Decimal(str(despues)), 6)
    return antes == despues


def cambios(actual, datos, pedidos):
    """{campo: {antes, despues}} de los campos pedidos que de verdad cambian."""
    return {c: {"antes": a_json(actual[c]), "despues": a_json(datos[c])}
            for c in pedidos if not igual(c, actual[c], datos[c])}
