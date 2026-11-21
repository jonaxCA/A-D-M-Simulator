"""Pruebas de carga por perfil de uso real (F4, RNF-A16).

Cinco perfiles, cada uno una clase de Locust con su peso y su ritmo:

- ConsultaWeb: gente en la web. Visitantes en el tablero público y personas con sesión
  recorriendo el tablero, el mapa, escenarios, simulaciones, monitoreo y comparación.
- CapturaMovil: la app móvil (cuenta CAPTURISTA). Lotes de casos por `sincronizacion`, de vez en
  cuando uno de 100 (RNF-A08) y fotos a `evidencias`; también notificaciones y su perfil.
- EscritorioReportes: la app de escritorio comparando: resultados y curvas de corridas,
  comparaciones, Pareto, el mapa de zonas, la situación y la exportación XML.
- PanelAdministracion: administradores en el panel: estado de los servicios, usuarios y avisos.
- CorridasAutomaticas: procesos que lanzan corridas y esperan su resultado (RNF-A14).

Dónde pega (variables de entorno):

    URL_SERVICIOS  plantilla con {servicio}, p. ej. https://35-222-19-202.sslip.io/{servicio}.
                   Sin ella, BASE_SERVICIOS (http://localhost) con el puerto del catálogo.
    URL_WEB        la web; por omisión http://localhost:5000.
    VERIFICAR_TLS  0 para aceptar un certificado autofirmado (nginx en local sin mkcert).
    PRUEBAS_CUENTAS "usuario:contraseña,..." (por omisión, las de demostración de INSTALACION).
    CUENTA_CAPTURISTA, CUENTA_ADMIN, CUENTAS_LANZAN: qué cuenta hace qué.
    RESULTADOS     carpeta donde se escriben cronologia.csv y usuarios.csv para analiza.py.

Uso, con la forma de escalones (sube usuarios y luego baja para medir la recuperación):

    locust -f pruebas_carga/perfiles.py,pruebas_carga/escalones.py --headless \
        --csv <dir>/locust --csv-full-history --html <dir>/reporte.html
    python pruebas_carga/analiza.py <dir>

Cada petición se nombra «perfil: MÉTODO servicio ruta», así analiza.py separa por perfil. Un 429
con Retry-After es el límite de D31 haciendo su trabajo: se cuenta aparte, como «[429] ...», y
no como error.
"""
import csv
import datetime
import json
import os
import random
import re
import threading
import time
import uuid

import gevent
from locust import HttpUser, between, events, task

URL_SERVICIOS = os.environ.get("URL_SERVICIOS")
BASE = os.environ.get("BASE_SERVICIOS", "http://localhost")
URL_WEB = os.environ.get("URL_WEB", "http://localhost:5000").rstrip("/")
VERIFICAR = os.environ.get("VERIFICAR_TLS", "1") != "0"
RESULTADOS = os.environ.get("RESULTADOS")
PUERTOS = {"auth": 5201, "usuarios": 5203, "enfermedades": 5211, "regiones": 5213,
           "casos": 5221, "sincronizacion": 5222, "evidencias": 5224, "escenarios": 5231,
           "escenarios-xml": 5235, "corridas": 5241, "resultados": 5243, "comparacion": 5244,
           "pareto": 5245, "indicadores": 5251, "series": 5252, "zonas": 5253,
           "notificaciones": 5261, "estado-servicios": 5262}

CUENTAS = dict(par.split(":", 1) for par in os.environ.get(
    "PRUEBAS_CUENTAS",
    "alex.cavazos:Epidemia2026!,diana.flores:Epidemia2026!,"
    "karla.trevino:Epidemia2026!,admin:Admin2026!").split(","))
CAPTURISTA = os.environ.get("CUENTA_CAPTURISTA", "karla.trevino")
ADMIN = os.environ.get("CUENTA_ADMIN", "admin")
LANZAN = os.environ.get("CUENTAS_LANZAN", "alex.cavazos,admin").split(",")
# Leen escenarios, corridas y reportes: todas menos la de captura.
LECTORES = [c for c in CUENTAS if c != CAPTURISTA]
LOTE = int(os.environ.get("TAMANO_LOTE", "5"))
# Una foto de 30 KB que pasa por JPEG (los primeros bytes son los que revisa evidencias).
FOTO = b"\xff\xd8\xff\xe0" + os.urandom(30 * 1024)

tokens, cookies_web, catalogo = {}, {}, {}
candado = threading.Lock()
cronologia = []


def url(servicio, ruta):
    if URL_SERVICIOS:
        return URL_SERVICIOS.format(servicio=servicio).rstrip("/") + "/api/v1" + ruta
    return "%s:%d/api/v1%s" % (BASE, PUERTOS[servicio], ruta)


@events.request.add_listener
def anota(request_type, name, response_time, response_length, response, exception, **kw):
    cronologia.append((round(time.time(), 3), request_type, name,
                       getattr(response, "status_code", 0) if response is not None else 0,
                       int(response_time), response_length or 0, 1 if exception else 0))


def _muestrea_usuarios(environment, archivo):
    """Cada segundo, cuántos usuarios de cada perfil hay (para RNF-A06 y los escalones)."""
    w = csv.writer(archivo)
    clases = sorted(c.__name__ for c in environment.user_classes)
    w.writerow(["t", "total"] + clases)
    while True:
        cuenta = environment.runner.user_classes_count if environment.runner else {}
        w.writerow([round(time.time(), 3), sum(cuenta.values())] + [cuenta.get(c, 0) for c in clases])
        archivo.flush()
        gevent.sleep(1)


# Los ajustes de escalones.py, para que analiza.py separe los escalones con los mismos valores.
AJUSTES_FORMA = ("USUARIOS_PASO", "SEGUNDOS_PASO", "USUARIOS_MAX", "USUARIOS_BASE", "SEGUNDOS_RECUPERACION")


@events.test_start.add_listener
def al_empezar(environment, **kw):
    if RESULTADOS:
        os.makedirs(RESULTADOS, exist_ok=True)
        with open(os.path.join(RESULTADOS, "escalones.json"), "w", encoding="utf-8") as f:
            json.dump({k: os.environ[k] for k in AJUSTES_FORMA if os.environ.get(k)}, f)
        archivo = open(os.path.join(RESULTADOS, "usuarios.csv"), "w", newline="", encoding="utf-8")
        gevent.spawn(_muestrea_usuarios, environment, archivo)


@events.quitting.add_listener
def guarda(environment, **kw):
    if RESULTADOS:
        with open(os.path.join(RESULTADOS, "cronologia.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t", "tipo", "nombre", "estado", "ms", "bytes", "excepcion"])
            w.writerows(cronologia)


def _limite(r, nombre):
    """Un 429 de D31 con Retry-After cuenta aparte y no como fallo. Regresa True si fue 429."""
    if r.status_code != 429:
        return False
    r.request_meta["name"] = "[429] " + nombre
    if r.headers.get("Retry-After"):
        r.success()
    else:
        r.failure("429 sin Retry-After")
    return True


class Base(HttpUser):
    abstract = True
    host = BASE
    perfil = "base"

    def on_start(self):
        self.client.verify = VERIFICAR

    # --- Sesión por API (auth) ------------------------------------------------------------
    def token(self, cuenta):
        with candado:
            if cuenta in tokens:
                return tokens[cuenta]
        for _ in range(5):
            captcha = self.client.get(url("auth", "/auth/captcha?format=json"),
                                      name="%s: GET auth /auth/captcha" % self.perfil)
            if captcha.status_code != 200:
                gevent.sleep(float(captcha.headers.get("Retry-After", 2)))
                continue
            a, b = (int(x) for x in captcha.json()["pregunta"].split("+"))
            nombre = "%s: POST auth /auth/login" % self.perfil
            with self.client.post(url("auth", "/auth/login?format=json"), name=nombre,
                                  json={"usuario": cuenta, "password": CUENTAS[cuenta],
                                        "captcha_id": captcha.json()["captcha_id"],
                                        "captcha_respuesta": str(a + b)},
                                  catch_response=True) as r:
                if _limite(r, nombre):
                    gevent.sleep(int(r.headers.get("Retry-After", "5")) + 1)
                    continue
                if r.status_code != 200:
                    r.failure("login de %s: %s" % (cuenta, r.status_code))
                    return None
                with candado:
                    tokens[cuenta] = r.json()["access_token"]
                return tokens[cuenta]
        return None

    def api(self, metodo, servicio, ruta, nombre, cuenta, **kw):
        """La respuesta, o None si no hubo sesión. Renueva el token una vez con un 401."""
        nombre = "%s: %s %s %s" % (self.perfil, metodo, servicio, nombre)
        propias = kw.pop("headers", {})
        for intento in range(2):
            token = self.token(cuenta)
            if token is None:
                return None
            cabeceras = dict(propias, Authorization="Bearer " + token)
            espera = 0
            with self.client.request(metodo, url(servicio, ruta), name=nombre, headers=cabeceras,
                                     catch_response=True, **kw) as r:
                if r.status_code == 401 and intento == 0:
                    with candado:
                        tokens.pop(cuenta, None)
                    r.success()
                    continue
                if _limite(r, nombre):
                    espera = min(60, int(r.headers.get("Retry-After") or 5))
                elif r.status_code == 409 and metodo == "POST":
                    r.request_meta["name"] = "[409] " + nombre
                    r.success()
                elif r.status_code >= 400:
                    r.failure("%s %s" % (r.status_code, r.text[:120]))
            # Como las apps: con un 429, espera lo que dice Retry-After (hasta 60 s). Fuera del
            # with, para que la petición quede anotada con su hora real.
            if espera:
                gevent.sleep(espera)
            return r
        return None

    def ids_catalogo(self, cuenta):
        """Ids de enfermedades y municipios, una vez para todos."""
        with candado:
            if catalogo:
                return catalogo
        enf = self.api("GET", "enfermedades", "/diseases?format=json", "/diseases", cuenta)
        reg = self.api("GET", "regiones", "/regions?format=json&per_page=200", "/regions", cuenta)
        if not (enf is not None and enf.ok and reg is not None and reg.ok):
            return None
        enfermedades = _lista(enf.json(), "enfermedades", "diseases")
        regiones = _lista(reg.json(), "regiones", "regions")
        municipios = [r["id"] for r in regiones if r.get("parent_region_id")] or [r["id"] for r in regiones]
        with candado:
            catalogo.update(enfermedades=[e["id"] for e in enfermedades if e.get("is_active", True)],
                            regiones=municipios)
        return catalogo


def _lista(cuerpo, *llaves):
    if isinstance(cuerpo, list):
        return cuerpo
    for llave in llaves + ("items", "datos", "resultados"):
        if isinstance(cuerpo.get(llave), list):
            return cuerpo[llave]
    return next((v for v in cuerpo.values() if isinstance(v, list)), [])


# --- 1. La web ------------------------------------------------------------------------------
class ConsultaWeb(Base):
    weight = 4
    wait_time = between(2, 6)
    perfil = "web"
    PAGINAS = [("/dashboard", 3), ("/mapa", 1), ("/api/mapa", 2), ("/escenarios", 1),
               ("/simulaciones", 1), ("/monitoreo", 1), ("/comparacion", 1)]

    def on_start(self):
        super().on_start()
        self.cuenta = random.choice(LECTORES)

    def entra(self):
        """Inicia sesión en la web una vez por cuenta y comparte sus cookies."""
        with candado:
            guardadas = cookies_web.get(self.cuenta)
        if guardadas is None:
            pagina = self.client.get(URL_WEB + "/login", name="web: GET /login")
            pid = re.search(r'name="captcha_id" value="([^"]+)"', pagina.text)
            pregunta = re.search(r"(\d+)\s*\+\s*(\d+)", pagina.text)
            if not (pid and pregunta):
                return False
            r = self.client.post(URL_WEB + "/login", name="web: POST /login", allow_redirects=False,
                                 data={"usuario": self.cuenta, "password": CUENTAS[self.cuenta],
                                       "captcha_id": pid.group(1),
                                       "captcha_respuesta": str(int(pregunta.group(1)) + int(pregunta.group(2)))})
            if r.status_code != 302:
                return False
            guardadas = dict(r.cookies)
            with candado:
                cookies_web[self.cuenta] = guardadas
        for nombre, valor in guardadas.items():
            self.client.cookies.set(nombre, valor)
        return True

    @task(3)
    def tablero_publico(self):
        self.client.get(URL_WEB + "/", name="web: GET / (tablero)")

    @task(8)
    def con_sesion(self):
        if not self.client.cookies and not self.entra():
            return
        ruta = random.choices([p for p, _ in self.PAGINAS], [w for _, w in self.PAGINAS])[0]
        with self.client.get(URL_WEB + ruta, name="web: GET " + ruta, allow_redirects=False,
                             catch_response=True) as r:
            if r.status_code in (302, 303) and "/login" in r.headers.get("Location", ""):
                # La sesión venció: se vuelve a entrar.
                r.success()
                with candado:
                    cookies_web.pop(self.cuenta, None)
                self.client.cookies.clear()
            elif r.status_code != 200:
                r.failure(str(r.status_code))


# --- 2. La app móvil ------------------------------------------------------------------------
class CapturaMovil(Base):
    weight = 3
    wait_time = between(1, 4)
    perfil = "movil"

    def on_start(self):
        super().on_start()
        self.casos_creados = []

    def lote(self, n):
        ids = self.ids_catalogo(CAPTURISTA)
        if not ids:
            return
        hoy = datetime.date.today()
        casos = [{"local_uuid": str(uuid.uuid4()), "disease_id": random.choice(ids["enfermedades"]),
                  "region_id": random.choice(ids["regiones"]),
                  "report_date": (hoy - datetime.timedelta(days=random.randint(0, 20))).isoformat()}
                 for _ in range(n)]
        nombre = "/sync/cases (%d casos)" % n
        r = self.api("POST", "sincronizacion", "/sync/cases?format=json", nombre, CAPTURISTA,
                     json={"batch_id": str(uuid.uuid4()), "cases": casos}, timeout=120)
        if r is None or r.status_code not in (200, 201):
            return
        cuerpo = r.json()
        creados = [c.get("case_id") for c in cuerpo.get("resultados", []) if c.get("case_id")]
        # Para RNF-A05: cuántos casos quedaron guardados, como evento aparte.
        events.request.fire(request_type="CASOS", name="movil: casos guardados", response_time=0,
                            response_length=cuerpo.get("creados", len(creados)), exception=None,
                            context={}, response=None)
        self.casos_creados = (self.casos_creados + creados)[-20:]

    @task(10)
    def sincroniza(self):
        self.lote(LOTE)

    @task(1)
    def sincroniza_cien(self):
        self.lote(100)

    @task(3)
    def foto(self):
        if self.casos_creados:
            caso = random.choice(self.casos_creados)
            self.api("POST", "evidencias", "/cases/%d/attachments?format=json" % caso,
                     "/cases/{id}/attachments", CAPTURISTA, data=FOTO,
                     headers={"Content-Type": "image/jpeg"})

    @task(3)
    def avisos(self):
        self.api("GET", "notificaciones", "/notifications?format=json", "/notifications", CAPTURISTA)

    @task(1)
    def perfil_propio(self):
        self.api("GET", "usuarios", "/users/me?format=json", "/users/me", CAPTURISTA)


# --- 3. El escritorio -----------------------------------------------------------------------
class EscritorioReportes(Base):
    weight = 2
    wait_time = between(2, 5)
    perfil = "escritorio"

    def on_start(self):
        super().on_start()
        self.cuenta = random.choice(LECTORES)
        self.corridas, self.escenarios = [], []
        self.corridas_lista()
        r = self.api("GET", "escenarios", "/scenarios?format=json", "/scenarios", self.cuenta)
        if r is not None and r.ok:
            self.escenarios = [e["id"] for e in _lista(r.json(), "escenarios", "scenarios")]

    def algunas(self, n):
        return ",".join(str(i) for i in random.sample(self.corridas, min(n, len(self.corridas))))

    @task(2)
    def corridas_lista(self):
        # También renueva las terminadas: en una base sin corridas, las va dejando
        # CorridasAutomaticas.
        r = self.api("GET", "corridas", "/runs?format=json&limit=50", "/runs", self.cuenta)
        if r is not None and r.ok:
            self.corridas = [c["id"] for c in r.json().get("corridas", [])
                             if c.get("status") == "completado"] or self.corridas

    @task(3)
    def resultados(self):
        if self.corridas:
            self.api("GET", "resultados", "/runs/%d/results?format=json" % random.choice(self.corridas),
                     "/runs/{id}/results", self.cuenta)

    @task(2)
    def curvas(self):
        if self.corridas:
            self.api("GET", "resultados", "/runs/%d/curves?format=json" % random.choice(self.corridas),
                     "/runs/{id}/curves", self.cuenta)

    @task(2)
    def compara(self):
        if len(self.corridas) >= 2:
            self.api("GET", "comparacion", "/comparisons?format=json&runs=" + self.algunas(3),
                     "/comparisons", self.cuenta)

    @task(1)
    def pareto(self):
        if len(self.corridas) >= 2:
            self.api("GET", "pareto", "/pareto?format=json&metric=fallecimientos&runs=" + self.algunas(5),
                     "/pareto", self.cuenta)

    @task(2)
    def mapa(self):
        self.api("GET", "zonas", "/zones/map?format=json", "/zones/map", self.cuenta)

    @task(1)
    def situacion(self):
        self.api("GET", "indicadores", "/dashboard/situation?format=json", "/dashboard/situation",
                 self.cuenta)

    @task(1)
    def exporta(self):
        if self.escenarios:
            self.api("GET", "escenarios-xml", "/scenarios/%d/export" % random.choice(self.escenarios),
                     "/scenarios/{id}/export", self.cuenta)


# --- 4. El panel de administración ----------------------------------------------------------
class PanelAdministracion(Base):
    weight = 1
    wait_time = between(3, 8)
    perfil = "panel"

    @task(2)
    def directorio(self):
        self.api("GET", "estado-servicios", "/services?format=json", "/services", ADMIN)

    @task(2)
    def salud(self):
        self.api("GET", "estado-servicios", "/services/health?format=json", "/services/health", ADMIN)

    @task(1)
    def usuarios(self):
        self.api("GET", "usuarios", "/users?format=json", "/users", ADMIN)

    @task(1)
    def resumen(self):
        self.api("GET", "usuarios", "/users/summary?format=json", "/users/summary", ADMIN)

    @task(1)
    def avisos(self):
        self.api("GET", "notificaciones", "/notifications?format=json", "/notifications", ADMIN)


# --- 5. Corridas automáticas ----------------------------------------------------------------
class CorridasAutomaticas(Base):
    weight = 1
    wait_time = between(5, 15)
    perfil = "corridas"
    version = None

    def on_start(self):
        super().on_start()
        self.cuenta = random.choice([c for c in LANZAN if c in CUENTAS])
        if CorridasAutomaticas.version is None:
            CorridasAutomaticas.version = int(os.environ.get("VERSION_ID") or 0) or self.version_aprobada()

    def version_aprobada(self):
        """La versión vigente aprobada de algún escenario: GET /scenarios/{id} la trae en «version»."""
        r = self.api("GET", "escenarios", "/scenarios?format=json", "/scenarios", self.cuenta)
        if r is None or not r.ok:
            return None
        for escenario in _lista(r.json(), "escenarios", "scenarios"):
            d = self.api("GET", "escenarios", "/scenarios/%d?format=json" % escenario["id"],
                         "/scenarios/{id}", self.cuenta)
            version = (d.json().get("version") or {}) if d is not None and d.ok else {}
            if version.get("status") == "aprobado":
                return version["id"]
        return None

    @task
    def lanza_y_espera(self):
        if not self.version:
            return
        inicio = time.time()
        r = self.api("POST", "corridas", "/runs?format=json", "/runs", self.cuenta,
                     json={"scenario_version_id": self.version, "seed": random.randint(1, 99999),
                           "engine": "seir-ref"})
        if r is None or r.status_code != 202:
            return
        corrida = r.json()["id"]
        while time.time() - inicio < 180:
            gevent.sleep(2)
            e = self.api("GET", "corridas", "/runs/%s?format=json" % corrida, "/runs/{id}", self.cuenta)
            if e is not None and e.ok and e.json().get("terminal"):
                exito = e.json().get("status") == "completado"
                events.request.fire(request_type="CORRIDA", name="corridas: seir-ref de lanzar a terminar",
                                    response_time=int((time.time() - inicio) * 1000), response_length=0,
                                    exception=None if exito else Exception(e.json().get("status")),
                                    context={}, response=None)
                if exito:
                    self.api("GET", "resultados", "/runs/%s/results?format=json" % corrida,
                             "/runs/{id}/results", self.cuenta)
                return
