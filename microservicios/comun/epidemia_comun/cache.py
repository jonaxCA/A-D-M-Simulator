# No hay invalidación: el monolito escribe directo en la base sin avisar a los
# servicios, así que lo único que limita lo viejo es el TTL.
import json
from datetime import date, datetime
from decimal import Decimal

from . import llaves
from .redis_compartido import opcional

_SIN_REDIS = object()


def obtener(servicio, clave, ttl, calcular):
    llave = llaves.cache(servicio, clave)
    guardado = opcional("cache_leer", lambda r: r.get(llave), defecto=_SIN_REDIS)
    if guardado is _SIN_REDIS:
        return calcular()
    if guardado is not None:
        try:
            return json.loads(guardado, object_hook=_decodifica)
        except ValueError:
            pass
    datos = calcular()
    texto = json.dumps(datos, default=_codifica, ensure_ascii=False)
    opcional("cache_guardar", lambda r: r.set(llave, texto, ex=ttl))
    return datos


def _codifica(valor):
    # Decimal y fechas se guardan con su tipo, para que lo leído de la caché sea
    # igual a lo que regresa la base.
    if isinstance(valor, Decimal):
        return {"__tipo__": "decimal", "valor": str(valor)}
    if isinstance(valor, datetime):
        return {"__tipo__": "fecha_hora", "valor": valor.isoformat()}
    if isinstance(valor, date):
        return {"__tipo__": "fecha", "valor": valor.isoformat()}
    raise TypeError(f"La caché no sabe guardar {type(valor).__name__}")


_TIPOS = {"decimal": Decimal, "fecha_hora": datetime.fromisoformat, "fecha": date.fromisoformat}


def _decodifica(objeto):
    tipo = objeto.get("__tipo__")
    return _TIPOS[tipo](objeto["valor"]) if tipo in _TIPOS else objeto
