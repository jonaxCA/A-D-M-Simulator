from dataclasses import dataclass
from typing import Optional

from .bd import a_jsonb, execute

CAMPOS_SENSIBLES = {"password_hash", "password", "token_hash"}

_INSERTA = """
    INSERT INTO audit_log (user_id, action, entity_type, entity_id,
                           ip_address, user_agent, data_before, data_after)
    VALUES (%s, %s, %s, %s, %s::inet, %s, %s::jsonb, %s::jsonb)
"""


@dataclass(frozen=True)
class Contexto:
    user_id: Optional[int]
    ip: Optional[str]
    user_agent: str


def _serializa(datos):
    return None if datos is None else a_jsonb({k: v for k, v in datos.items() if k not in CAMPOS_SENSIBLES})


def log_audit(contexto, action, entity_type, entity_id=None,
              data_before=None, data_after=None, *, cur=None):
    params = (contexto.user_id, action, entity_type,
              None if entity_id is None else str(entity_id),
              contexto.ip, contexto.user_agent,
              _serializa(data_before), _serializa(data_after))
    if cur is None:
        execute(_INSERTA, params)
    else:
        cur.execute(_INSERTA, params)
