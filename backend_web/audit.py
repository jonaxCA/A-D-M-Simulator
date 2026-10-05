"""
Bitacora de auditoria real. A diferencia de los casos sinteticos (que si se
generan con datos falsos por diseno), audit_log se llena con eventos reales
de uso de esta app: cada login, logout, exportacion y operacion de CRUD que
ocurre de verdad mientras alguien usa el sistema genera un renglon aqui.

No hay historial previo cargado a proposito: la pantalla de Auditoria se ve
vacia hasta que alguien de verdad usa el sistema, y eso es lo correcto.
"""
import json

from .db import execute


_INSERTA = """
    INSERT INTO audit_log (user_id, action, entity_type, entity_id,
                           ip_address, user_agent, data_before, data_after)
    VALUES (%s, %s, %s, %s, %s::inet, %s, %s::jsonb, %s::jsonb)
"""


def log_audit(contexto, action, entity_type, entity_id=None,
              data_before=None, data_after=None, *, cur=None):
    """Registra un evento en audit_log. Es la unica escritura a esa tabla.

    `cur`: el cursor de la transaccion que hace el cambio. Con el, el registro
    se confirma o se deshace JUNTO con el cambio que describe; es lo que tiene
    que usar toda funcion de la capa de datos que modifique algo y lo audite.
    Sin el, se escribe en una transaccion propia: para eventos que no
    acompanan a un cambio en la base (login, exportaciones, permiso denegado)
    o que ocurren despues de confirmarlo.

    `contexto` (backend_web.contexto.Contexto) dice quien y desde donde: de el
    salen user_id, ip_address y user_agent. Las corridas en segundo plano no
    tienen peticion HTTP detras y usan Contexto.sin_peticion(), con la IP en
    NULL.

    data_before / data_after son dicts opcionales: None se guarda como NULL.
    003_sistema.sql tiene un CHECK (ck_audit_log_datos) que EXIGE al menos uno
    de los dos cuando la accion es CREATE, UPDATE o DELETE. Nunca se guarda
    password_hash aqui (ver _limpia).
    """
    params = (
        contexto.user_id, action, entity_type,
        None if entity_id is None else str(entity_id),
        contexto.ip, contexto.user_agent,
        _serializa(data_before), _serializa(data_after),
    )
    if cur is None:
        execute(_INSERTA, params)
    else:
        cur.execute(_INSERTA, params)


CAMPOS_SENSIBLES = {"password_hash", "password", "token_hash"}


def _limpia(datos):
    """Quita del snapshot cualquier campo sensible. La bitacora registra QUE
    cambio, no las credenciales."""
    return {k: v for k, v in datos.items() if k not in CAMPOS_SENSIBLES}


def _serializa(datos):
    if datos is None:
        return None
    return json.dumps(_limpia(datos), default=str, ensure_ascii=False)
