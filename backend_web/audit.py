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


def log_audit(contexto, action, entity_type, entity_id=None,
              data_before=None, data_after=None):
    """Registra un evento en audit_log, en una transaccion propia.

    `contexto` (backend_web.contexto.Contexto) dice quien y desde donde: de el
    salen user_id, ip_address y user_agent. Las corridas en segundo plano no
    tienen peticion HTTP detras y usan Contexto.sin_peticion(), con la IP en
    NULL.

    data_before / data_after son dicts opcionales. 003_sistema.sql tiene un
    CHECK (ck_audit_log_datos) que EXIGE al menos uno de los dos cuando la
    accion es CREATE, UPDATE o DELETE -- por eso el CRUD de usuarios siempre
    los manda. Nunca se guarda password_hash aqui (ver _limpia).
    """
    execute(
        """
        INSERT INTO audit_log (user_id, action, entity_type, entity_id,
                               ip_address, user_agent, data_before, data_after)
        VALUES (%s, %s, %s, %s, %s::inet, %s, %s::jsonb, %s::jsonb)
        """,
        (
            contexto.user_id, action, entity_type, entity_id,
            contexto.ip, contexto.user_agent,
            _serializa(data_before), _serializa(data_after),
        ),
    )


CAMPOS_SENSIBLES = {"password_hash", "password", "token_hash"}


def _limpia(datos):
    """Quita del snapshot cualquier campo sensible. La bitacora registra QUE
    cambio, no las credenciales."""
    return {k: v for k, v in datos.items() if k not in CAMPOS_SENSIBLES}


def _serializa(datos):
    if datos is None:
        return None
    return json.dumps(_limpia(datos), default=str, ensure_ascii=False)
