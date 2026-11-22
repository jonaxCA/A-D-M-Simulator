"""Alertas técnicas (F7): cuando un servicio cae, se degrada o se recupera, estado-servicios
avisa a los ADMINISTRADOR con un aviso SYSTEM de notificaciones.

Reglas, para que la bandeja no se llene de ruido:

- Un cambio de estado cuenta cuando se sostiene CONFIRMAR rondas seguidas (30 s con el sondeo
  cada 10 s): reiniciar un contenedor al actualizar no avisa.
- Al arrancar hay GRACIA (2 min) sin avisos: los servicios todavía se están levantando.
- Entre dos fallas avisadas del mismo servicio pasan al menos ESPERA_ENTRE_FALLAS (10 min); una
  falla que cae en ese lapso se avisa al terminar, si sigue. Que se recuperó se avisa siempre.
- Los cambios de una ronda van en un solo aviso: con Redis caído se degradan los 29 a la vez.
- Lo último que se avisó de cada servicio se guarda en Redis (alert:<servicio>), así que un
  reinicio de estado-servicios no repite ni pierde avisos; con Redis caído vive en la memoria.
- Si notificaciones no los recibe (también falla si se caen Redis o PostgreSQL, de los que
  depende), los cambios esperan y se mandan juntos cada REINTENTO (60 s) hasta que responda. Así
  una caída de Redis llega, aunque sea al final: «auth: en línea → degradado (redis) → en línea».
"""
import json
import logging
import os
import time

from epidemia_comun import llaves
from epidemia_comun.http import llamar
from epidemia_comun.redis_compartido import opcional
from epidemia_comun.seguridad import token_servicio

log = logging.getLogger(__name__)

ROL = "ADMINISTRADOR"
CONFIRMAR = 3
GRACIA = 120
ESPERA_ENTRE_FALLAS = 600
REINTENTO = 60
# Si un servicio sigue igual una semana, su registro vence y la falla se vuelve a avisar.
TTL_AVISADO = 7 * 86400
MAXIMO_PENDIENTES = 200
TITULO_MAX = 160
NOMBRES = {"ok": "en línea", "degradado": "degradado", "caido": "caído"}
DETALLES = {"sin_conexion": "sin conexión", "tiempo_agotado": "tiempo agotado",
            "respuesta_invalida": "respuesta inválida"}


def activas():
    """Prendidas salvo con ALERTAS_TECNICAS=0, y solo si hay a quién avisar: fuera de Docker no
    está SERVICIO_NOTIFICACIONES_URL."""
    if os.environ.get("ALERTAS_TECNICAS", "1").strip().lower() in ("0", "false", "no"):
        return False
    return bool(os.environ.get("SERVICIO_NOTIFICACIONES_URL"))


def _por_servicio(cambios):
    grupos = {}
    for cambio in cambios:
        grupos.setdefault(cambio["nombre"], []).append(cambio)
    return grupos


def _motivo(cambio):
    partes = list(cambio["causas"])
    if cambio["detalle"]:
        partes.append(DETALLES.get(cambio["detalle"], cambio["detalle"]))
    return " (%s)" % ", ".join(partes) if partes else ""


def titulo(cambios):
    grupos = _por_servicio(cambios)
    nombres = list(grupos)
    finales = [cs[-1]["estado"] for cs in grupos.values()]
    if all(e != "ok" for e in finales):
        texto = ("%s está %s" % (nombres[0], NOMBRES[finales[0]]) if len(nombres) == 1
                 else "%d servicios con fallas: %s" % (len(nombres), ", ".join(nombres)))
    elif all(e == "ok" for e in finales):
        texto = ("%s se recuperó" % nombres[0] if len(nombres) == 1
                 else "Se recuperaron %d servicios: %s" % (len(nombres), ", ".join(nombres)))
    else:
        texto = "Cambios en %d servicios: %s" % (len(nombres), ", ".join(nombres))
    return texto if len(texto) <= TITULO_MAX else texto[:TITULO_MAX - 1] + "…"


def cuerpo(cambios):
    """Una línea por servicio con sus estados en orden: «zonas: en línea → caído (proceso, sin
    conexión) → en línea»."""
    lineas = []
    for nombre, cs in _por_servicio(cambios).items():
        pasos = [NOMBRES[cs[0]["anterior"]]] + [NOMBRES[c["estado"]] + _motivo(c) for c in cs]
        lineas.append("%s: %s" % (nombre, " → ".join(pasos)))
    return "\n".join(lineas)


class Alertas:
    """Lleva la cuenta entre rondas. La usa solo el hilo del sondeo (sondeo._ciclo)."""

    def __init__(self, ajustes, reloj=time.time):
        self.ajustes, self.reloj = ajustes, reloj
        self.inicio = reloj()
        self.racha = {}        # servicio -> [estado, rondas seguidas en él]
        self.avisado = None    # servicio -> {"estado", "falla"}: lo último avisado y cuándo falló
        self.pendientes = []   # cambios que notificaciones todavía no recibe
        self.descartados = 0
        self.reintentar_en = 0.0

    def revisar(self, registros):
        """Una ronda del sondeo. Regresa los cambios que se entregaron en ella."""
        ahora = self.reloj()
        if self.avisado is None:
            self.avisado = self._carga([r["nombre"] for r in registros])
        for r in registros:
            previa = self.racha.get(r["nombre"])
            seguidas = previa[1] + 1 if previa and previa[0] == r["estado"] else 1
            self.racha[r["nombre"]] = [r["estado"], seguidas]
        if ahora - self.inicio < GRACIA:
            return []
        for r in registros:
            self._detecta(r, ahora)
        return self._entrega(ahora)

    def _carga(self, nombres):
        valores = opcional("estado-servicios: leer las alertas",
                           lambda r: r.mget([llaves.alerta(n) for n in nombres]))
        return {n: json.loads(v) for n, v in zip(nombres, valores or []) if v}

    def _detecta(self, registro, ahora):
        nombre, estado = registro["nombre"], registro["estado"]
        previo = self.avisado.get(nombre) or {"estado": "ok", "falla": 0}
        if estado == previo["estado"] or self.racha[nombre][1] < CONFIRMAR:
            return
        if estado != "ok" and ahora - previo.get("falla", 0) < ESPERA_ENTRE_FALLAS:
            return
        self.pendientes.append({"nombre": nombre, "anterior": previo["estado"], "estado": estado,
                                "causas": list(registro["causas"]), "detalle": registro["detalle"],
                                "revisado": registro["revisado"]})
        self.avisado[nombre] = {"estado": estado,
                                "falla": ahora if estado != "ok" else previo.get("falla", 0)}
        valor = json.dumps(self.avisado[nombre])
        opcional("estado-servicios: guardar la alerta",
                 lambda r: r.set(llaves.alerta(nombre), valor, ex=TTL_AVISADO))
        if len(self.pendientes) > MAXIMO_PENDIENTES:
            self.descartados += len(self.pendientes) - MAXIMO_PENDIENTES
            del self.pendientes[:-MAXIMO_PENDIENTES]

    def _entrega(self, ahora):
        if not self.pendientes or ahora < self.reintentar_en:
            return []
        cambios = self.pendientes
        texto = cuerpo(cambios)
        if self.descartados:
            texto += ("\n(Se omitió el cambio más antiguo.)" if self.descartados == 1
                      else "\n(Se omitieron los %d cambios más antiguos.)" % self.descartados)
        try:
            resp = llamar("notificaciones", "POST", "/api/v1/notifications", timeout=3,
                          token=token_servicio(self.ajustes, "estado-servicios"),
                          cuerpo={"role": ROL, "type": "SYSTEM", "title": titulo(cambios),
                                  "body": texto, "payload": {"servicios": cambios}})
            entregado = resp.status_code < 400
            if not entregado:
                log.warning("notificaciones respondió %d a la alerta técnica; se reintenta",
                            resp.status_code)
        except Exception as exc:  # incluye el 503 de llamar(): nunca tumba al sondeo
            log.warning("No se pudo mandar la alerta técnica; se reintenta: %s", exc)
            entregado = False
        if not entregado:
            self.reintentar_en = ahora + REINTENTO
            return []
        self.pendientes, self.descartados, self.reintentar_en = [], 0, 0.0
        return cambios
