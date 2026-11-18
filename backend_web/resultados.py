import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger(__name__)


class SinAcceso(Exception):
    pass


def curvas_de_corrida(token, run_id, correlacion=None):
    base = (os.environ.get("SERVICIO_RESULTADOS_URL") or "").rstrip("/")
    if not base:
        return None
    cabeceras = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if correlacion:
        cabeceras["X-Correlation-ID"] = correlacion
    peticion = urllib.request.Request("%s/api/v1/runs/%d/curves" % (base, run_id),
                                      headers=cabeceras)
    try:
        timeout = float(os.environ.get("SERVICIO_RESULTADOS_TIMEOUT") or 3)
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            return json.load(respuesta)["serie"]
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise SinAcceso(error.code)
        log.warning("resultados respondió %s para la corrida %s", error.code, run_id)
    except (OSError, ValueError, KeyError) as error:
        log.warning("resultados no responde para la corrida %s: %s", run_id, error)
    return None
