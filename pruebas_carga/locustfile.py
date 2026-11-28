import csv
import os
import random
import threading
import time

from locust import HttpUser, between, constant, events, task

BASE = os.environ.get("BASE_SERVICIOS", "http://localhost")
PUERTOS = {"auth": 5201, "regiones": 5213, "casos": 5221, "escenarios": 5231,
           "corridas": 5241, "indicadores": 5251}
# Cuentas de demostración de docs/INSTALACION.md; se pueden cambiar con PRUEBAS_CUENTAS="u:p,u:p".
CUENTAS = dict(par.split(":", 1) for par in os.environ.get(
    "PRUEBAS_CUENTAS",
    "alex.cavazos:Epidemia2026!,diana.flores:Epidemia2026!,"
    "karla.trevino:Epidemia2026!,admin:Admin2026!").split(","))
USUARIOS = list(CUENTAS)
SIN_ESCENARIOS = "karla.trevino"
VERSION_ID = int(os.environ.get("VERSION_ID", "1"))
RESULTADOS = os.environ.get("RESULTADOS")

tokens = {}
candado = threading.Lock()
cronologia = []
contador = {"n": 0}


def url(servicio, ruta):
    return "%s:%d/api/v1%s" % (BASE, PUERTOS[servicio], ruta)


@events.request.add_listener
def anota(request_type, name, response_time, response, exception, **kw):
    cronologia.append((time.time(), request_type, name,
                       getattr(response, "status_code", 0), int(response_time)))


@events.quitting.add_listener
def guarda(environment, **kw):
    if RESULTADOS:
        with open(os.path.join(RESULTADOS, "cronologia.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t", "metodo", "nombre", "estado", "ms"])
            w.writerows(cronologia)


class Base(HttpUser):
    abstract = True
    host = BASE
    wait_time = between(0.5, 2)
    cuenta = None

    def on_start(self):
        with candado:
            self.cuenta = USUARIOS[contador["n"] % len(USUARIOS)]
            contador["n"] += 1

    def tomar(self, nombre, cuenta=None):
        cuenta = cuenta or self.cuenta
        with candado:
            if cuenta in tokens:
                return tokens[cuenta]
        for _ in range(5):
            captcha = self.client.get(url("auth", "/auth/captcha?format=json"),
                                      name="GET /auth/captcha").json()
            a, b = (int(x) for x in captcha["pregunta"].split("+"))
            with self.client.post(
                    url("auth", "/auth/login?format=json"), name="POST /auth/login",
                    json={"usuario": cuenta, "password": CUENTAS[cuenta],
                          "captcha_id": captcha["captcha_id"],
                          "captcha_respuesta": str(a + b)},
                    catch_response=True) as r:
                if r.status_code == 429:
                    espera = int(r.headers.get("Retry-After", "5"))
                    r.request_meta["name"] = "[429] POST /auth/login"
                    r.success()
                    time.sleep(espera + 1)
                    continue
                if r.status_code != 200:
                    r.failure("login %s" % r.status_code)
                    return None
                with candado:
                    tokens[cuenta] = r.json()["access_token"]
                return tokens[cuenta]
        return None

    def pide(self, metodo, servicio, ruta, nombre, cuenta=None, **kw):
        token = self.tomar(nombre, cuenta)
        if token is None:
            return
        for intento in range(2):
            with self.client.request(
                    metodo, url(servicio, ruta), name="%s %s" % (metodo, nombre),
                    headers={"Authorization": "Bearer " + token},
                    catch_response=True, **kw) as r:
                if r.status_code == 401 and intento == 0:
                    with candado:
                        tokens.pop(cuenta or self.cuenta, None)
                    r.success()
                    token = self.tomar(nombre, cuenta)
                    if token is None:
                        return
                    continue
                if r.status_code == 409 and metodo == "POST":
                    r.request_meta["name"] = "[409] %s %s" % (metodo, nombre)
                    r.success()
                    return
                if r.status_code == 429:
                    codigo = ""
                    try:
                        codigo = r.json().get("codigo", "")
                    except ValueError:
                        pass
                    r.request_meta["name"] = "[429] %s %s" % (metodo, nombre)
                    if r.headers.get("Retry-After") and codigo == "LIMITE_EXCEDIDO":
                        r.success()
                    else:
                        r.failure("429 sin Retry-After o sin LIMITE_EXCEDIDO")
                    return
                return

    def lector(self):
        return "alex.cavazos" if self.cuenta == SIN_ESCENARIOS else self.cuenta


class UsoNormal(Base):
    @task(10)
    def casos(self):
        self.pide("GET", "casos", "/cases?format=json&per_page=20&page=%d" % (1 + int(time.time()) % 20),
                  "/cases")

    @task(3)
    def caso(self):
        self.pide("GET", "casos", "/cases/%d?format=json" % (3000 + int(time.time() * 10) % 800),
                  "/cases/{id}")

    @task(6)
    def regiones(self):
        self.client.get(url("regiones", "/regions?format=json"), name="GET /regions")

    @task(2)
    def region(self):
        self.client.get(url("regiones", "/regions/%d?format=json" % (12 + int(time.time()) % 41)),
                        name="GET /regions/{id}")

    @task(4)
    def escenarios(self):
        self.pide("GET", "escenarios", "/scenarios?format=json", "/scenarios", self.lector())

    @task(3)
    def versiones(self):
        self.pide("GET", "escenarios", "/scenarios/1/versions?format=json",
                  "/scenarios/{id}/versions", self.lector())

    @task(4)
    def corridas(self):
        self.pide("GET", "corridas", "/runs?format=json", "/runs", self.lector())

    @task(3)
    def indicadores(self):
        self.pide("GET", "indicadores", "/dashboard/indicators?format=json",
                  "/dashboard/indicators", self.lector())

    @task(1)
    def lanza(self):
        # Una corrida cada 2 minutos por usuario, repartidas entre las dos cuentas que pueden lanzar.
        if time.time() - getattr(self, "ultimo", 0) < 120:
            return
        self.ultimo = time.time()
        self.pide("POST", "corridas", "/runs?format=json", "/runs",
                  random.choice(("alex.cavazos", "admin")),
                  json={"scenario_version_id": VERSION_ID, "seed": int(time.time()) % 100000,
                        "engine": "seir-ref"})


class Estres(UsoNormal):
    wait_time = between(0.05, 0.3)
    weight = 1


class LimiteLogin(Base):
    wait_time = constant(0.1)
    weight = 1

    @task
    def login(self):
        with self.client.post(url("auth", "/auth/login?format=json"), name="POST /auth/login",
                              json={"usuario": "x", "password": "x", "captcha_id": "x",
                                    "captcha_respuesta": "0"},
                              catch_response=True) as r:
            if r.status_code == 429:
                r.request_meta["name"] = "[429] POST /auth/login"
                if r.headers.get("Retry-After"):
                    r.success()
                else:
                    r.failure("429 sin Retry-After")
            elif r.status_code == 422:
                r.success()


class LimiteCasos(Base):
    wait_time = constant(0.05)
    weight = 1

    @task
    def casos(self):
        self.pide("GET", "casos", "/cases?format=json&per_page=5", "/cases", "karla.trevino")


class LimiteCorridas(Base):
    wait_time = constant(0.2)
    weight = 1

    @task(1)
    def lanza(self):
        self.pide("POST", "corridas", "/runs?format=json", "/runs", "alex.cavazos",
                  json={"scenario_version_id": VERSION_ID, "seed": int(time.time() * 1000) % 100000,
                        "engine": "seir-ref"})

    @task(3)
    def lista(self):
        self.pide("GET", "corridas", "/runs?format=json", "/runs", "diana.flores")
