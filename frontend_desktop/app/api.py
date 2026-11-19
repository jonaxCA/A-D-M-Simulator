import threading
import time
import uuid

import requests

from . import bitacora, config, esquemas, xmlio

FIN_DE_SESION = ("TOKEN_AUSENTE", "TOKEN_INVALIDO", "TOKEN_REVOCADO")
MENSAJES = {403: "No tienes permiso para esta operación.",
            503: "El servicio no está disponible. Intenta más tarde."}


class ErrorServicio(Exception):
    def __init__(self, mensaje, status=None, codigo=None, errores=None):
        self.status = status
        self.codigo = codigo
        self.errores = errores or []
        super().__init__(mensaje)


class SesionCerrada(ErrorServicio):
    pass


def _problema(servicio, respuesta):
    try:
        esquemas.validar_con(esquemas.PROBLEMA, respuesta.content)
        datos = xmlio.leer(respuesta.content)
    except Exception:
        return ErrorServicio("Respuesta inválida de %s (HTTP %s)." % (servicio, respuesta.status_code),
                             respuesta.status_code)
    detalle = datos.get("detail") or MENSAJES.get(respuesta.status_code) or datos.get("title")
    if respuesta.status_code == 403:
        detalle = MENSAJES[403]
    return ErrorServicio(detalle, respuesta.status_code, datos.get("codigo"), datos.get("errores") or [])


class Cliente:
    def __init__(self, directorio=config.DIRECTORIO, http=None):
        self.directorio = directorio
        self.http = http or requests.Session()
        self.urls = {}
        self.access = None
        self.refresh = None
        self.usuario = None
        self._candado = threading.RLock()

    def url(self, servicio):
        with self._candado:
            if servicio not in self.urls:
                try:
                    r = self.http.get(self.directorio + "/api/v1/services",
                                      headers={"Accept": "application/xml"}, timeout=config.TIEMPO_ESPERA)
                except requests.RequestException:
                    raise ErrorServicio("No se pudo conectar con el directorio de servicios (%s)." % self.directorio)
                if r.status_code != 200:
                    raise ErrorServicio("El directorio de servicios respondió %s." % r.status_code, r.status_code)
                self.urls = {s["nombre"]: s["url"].rstrip("/") for s in xmlio.leer(r.content)["servicios"]}
            if servicio not in self.urls:
                raise ErrorServicio("El directorio no conoce el servicio %s." % servicio)
            return self.urls[servicio]

    def _una_vez(self, servicio, metodo, ruta, cuerpo, params, publico):
        cid = str(uuid.uuid4())
        headers = {"Accept": "application/xml", "X-Correlation-ID": cid}
        if cuerpo is not None:
            headers["Content-Type"] = "application/xml"
        if not publico and self.access:
            headers["Authorization"] = "Bearer " + self.access
        inicio = time.monotonic()
        try:
            r = self.http.request(metodo, self.url(servicio) + ruta, data=cuerpo, params=params,
                                  headers=headers, timeout=config.TIEMPO_ESPERA)
        except requests.RequestException:
            bitacora.error("sin conexión con %s %s %s cid=%s" % (servicio, metodo, ruta, cid))
            raise ErrorServicio("No se pudo conectar con %s." % servicio)
        bitacora.peticion(metodo, servicio, ruta, r.status_code, r.headers.get("X-Correlation-ID", cid),
                          (time.monotonic() - inicio) * 1000)
        return r

    def enviar(self, servicio, metodo, ruta, cuerpo=None, params=None, publico=False):
        token = self.access
        r = self._una_vez(servicio, metodo, ruta, cuerpo, params, publico)
        if r.status_code == 401 and not publico:
            error = _problema(servicio, r)
            if error.codigo == "TOKEN_EXPIRADO":
                self._renovar(token)
                r = self._una_vez(servicio, metodo, ruta, cuerpo, params, publico)
            elif error.codigo in FIN_DE_SESION:
                self.olvidar()
                raise SesionCerrada(error.args[0], 401, error.codigo)
        if r.status_code >= 400:
            error = _problema(servicio, r)
            bitacora.error("%s %s %s -> %s %s" % (servicio, metodo, ruta, r.status_code, error.codigo))
            if r.status_code == 401 and not publico:
                self.olvidar()
                raise SesionCerrada(error.args[0], 401, error.codigo)
            raise error
        return r

    def pedir(self, servicio, metodo, ruta, datos=None, raiz="solicitud", params=None, publico=False):
        cuerpo = None if datos is None else xmlio.escribir(datos, raiz)
        r = self.enviar(servicio, metodo, ruta, cuerpo, params, publico)
        if not r.content:
            return {}
        try:
            xsd = esquemas.xsd_de(servicio, xmlio.raiz(r.content))
            if xsd:
                esquemas.validar_con(xsd, r.content)
                bitacora.validado(servicio, xsd.split("/")[-1])
            return xmlio.leer(r.content)
        except esquemas.XMLInvalido as exc:
            bitacora.error("respuesta de %s no cumple %s" % (servicio, exc.xsd))
            raise ErrorServicio("Respuesta inválida de %s: no cumple %s." % (servicio, exc.xsd),
                                errores=exc.errores)
        except Exception:
            bitacora.error("respuesta de %s no es XML" % servicio)
            raise ErrorServicio("Respuesta inválida de %s: no es XML." % servicio)

    def _renovar(self, token_usado):
        with self._candado:
            if self.access != token_usado:
                return
            if not self.refresh:
                self.olvidar()
                raise SesionCerrada("La sesión terminó. Vuelve a iniciar sesión.", 401)
            try:
                datos = self.pedir("sesiones", "POST", "/api/v1/sessions/refresh",
                                   {"refresh_token": self.refresh}, "refresh", publico=True)
            except ErrorServicio as exc:
                if exc.status == 401:
                    self.olvidar()
                    raise SesionCerrada("La sesión terminó. Vuelve a iniciar sesión.", 401, exc.codigo)
                raise
            self.access = datos["access_token"]
            self.refresh = datos["refresh_token"]
            bitacora.accion(self.nombre_usuario(), "renovó el token de acceso")

    def iniciar_sesion(self, usuario, password, captcha_id, respuesta):
        datos = self.pedir("auth", "POST", "/api/v1/auth/login",
                           {"usuario": usuario, "password": password,
                            "captcha_id": captcha_id, "captcha_respuesta": respuesta},
                           "login", publico=True)
        self.access = datos["access_token"]
        self.refresh = datos["refresh_token"]
        self.usuario = datos.get("usuario") or {}
        bitacora.accion(self.nombre_usuario(), "inició sesión")
        return datos

    def cerrar_sesion(self):
        if self.access:
            try:
                self.enviar("sesiones", "POST", "/api/v1/sessions/logout")
            except ErrorServicio:
                pass
            bitacora.accion(self.nombre_usuario(), "cerró sesión")
        self.olvidar()

    def olvidar(self):
        self.access = None
        self.refresh = None

    def nombre_usuario(self):
        return (self.usuario or {}).get("username")

    def roles(self):
        return list((self.usuario or {}).get("roles") or [])
