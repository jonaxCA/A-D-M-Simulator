import getpass
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AYUDA = '''Demostración de caídas (N5) contra el compose de la demostración (infra/docker-compose.yml, perfil '*').

    python infra/demo_fallos.py --lista            muestra los escenarios
    python infra/demo_fallos.py                    corre todos
    python infra/demo_fallos.py redis timeout      corre solo esos

Necesita el compose arriba y una cuenta de la demostración: DEMO_USUARIO (por defecto admin) y
DEMO_PASSWORD (si falta, la pide). Por escenario: detiene o pausa un contenedor, llama a las
rutas, imprime lo esperado contra lo observado, restaura y verifica que todo regrese.
Lo que no está en el compose (MongoDB, bucket) se salta con un aviso; al agregar el servicio,
basta con poner su nombre en MONGO o BUCKET.'''

RAIZ = Path(__file__).resolve().parent.parent
HOST = os.environ.get("DEMO_HOST", "127.0.0.1")
PROYECTO = os.environ.get("DEMO_PROYECTO")
REDIS, POSTGRES = "redis", "postgres"
MONGO = "mongo"
BUCKET = "bucket"
PUERTOS = {"auth": 5201, "regiones": 5213, "enfermedades": 5211, "casos": 5221, "escenarios": 5231,
           "estado-servicios": 5262}
BASE = ["docker", "compose"] + (["-p", PROYECTO] if PROYECTO else []) + [
    "-f", str(RAIZ / "infra/docker-compose.yml"), "--profile", "*"]
RESULTADOS = []


def compose(*args, check=True):
    return subprocess.run(BASE + list(args), capture_output=True, text=True, check=check).stdout


def pide(servicio, ruta, metodo="GET", token=None, cuerpo=None, timeout=15):
    url = "http://%s:%d%s%sformat=json" % (HOST, PUERTOS[servicio], ruta, "&" if "?" in ruta else "?")
    cabeceras = {"Accept": "application/json"}
    datos = None
    if token:
        cabeceras["Authorization"] = "Bearer " + token
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode()
        cabeceras["Content-Type"] = "application/json"
    inicio = time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, datos, cabeceras, metodo), timeout=timeout) as r:
            estado, texto = r.status, r.read()
    except urllib.error.HTTPError as e:
        estado, texto = e.code, e.read()
    except (urllib.error.URLError, OSError):
        return 0, {}, time.monotonic() - inicio
    try:
        cuerpo_json = json.loads(texto)
    except ValueError:
        cuerpo_json = {}
    return estado, cuerpo_json, time.monotonic() - inicio


def espera(condicion, limite=90, cada=2):
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        if condicion():
            return True
        time.sleep(cada)
    return False


def abre_sesion():
    usuario = os.environ.get("DEMO_USUARIO", "admin")
    clave = os.environ.get("DEMO_PASSWORD") or getpass.getpass("Contraseña de %s: " % usuario)
    _, captcha, _ = pide("auth", "/api/v1/auth/captcha")
    a, b = captcha["pregunta"].split("+")
    estado, sesion, _ = pide("auth", "/api/v1/auth/login", "POST", cuerpo={
        "usuario": usuario, "password": clave, "captcha_id": captcha["captcha_id"],
        "captcha_respuesta": str(int(a) + int(b))})
    if estado != 200:
        sys.exit("No se pudo iniciar sesión (%d). ¿Está arriba el compose y es correcta la cuenta?" % estado)
    return sesion["access_token"]


def codigo(cuerpo):
    return cuerpo.get("codigo", "-")


def veredicto(escenario, esperado, observado, bien):
    print("  esperado : %s\n  observado: %s\n  => %s" % (esperado, observado, "OK" if bien else "DIFERENTE"))
    RESULTADOS.append((escenario, bien))


def estado_en_panel(nombre):
    _, panel, _ = pide("estado-servicios", "/api/v1/services/health")
    return next((s["estado"] for s in panel.get("servicios", []) if s["nombre"] == nombre), "?")


def cuerpo_escenario(token):
    _, enfermedades, _ = pide("enfermedades", "/api/v1/diseases", token=token)
    _, regiones, _ = pide("regiones", "/api/v1/regions", token=token)
    return {"name": "Demo fallos %d" % time.time(), "description": "Demostración de caídas.",
            "disease_id": enfermedades["enfermedades"][0]["id"], "region_id": regiones["municipios"][0]["id"],
            "population_size": 100000, "horizon_days": 90, "initial_infected": 10, "stratify": False,
            "notes": None}


def servicio_caido(token):
    compose("stop", "casos")
    try:
        r, _, _ = pide("casos", "/api/v1/cases", token=token, timeout=5)
        otro, _, _ = pide("regiones", "/api/v1/regions")
        en_panel = espera(lambda: estado_en_panel("casos") == "caido", 90)
        veredicto("servicio caído", "casos no responde; regiones sigue en 200; el panel marca casos como caído",
                  "casos=%s (0 = sin conexión), regiones=%d, panel=%s" % (r, otro, "caído" if en_panel else "sin cambio"),
                  r == 0 and otro == 200 and en_panel)
    finally:
        compose("start", "casos")
    ok = espera(lambda: pide("casos", "/api/v1/cases", token=token)[0] == 200 and estado_en_panel("casos") == "ok")
    veredicto("servicio caído (recuperación)", "casos vuelve a 200 con la misma sesión y el panel a ok",
              "recuperó" if ok else "no recuperó", ok)


def redis_caido(token):
    compose("stop", REDIS)
    try:
        r, cuerpo, _ = pide("casos", "/api/v1/cases", token=token)
        publica, _, _ = pide("regiones", "/api/v1/regions")
        veredicto("Redis caído", "ruta protegida 503 SERVICIO_NO_DISPONIBLE (falla cerrada); catálogo público 200",
                  "protegida=%d %s, pública=%d" % (r, codigo(cuerpo), publica),
                  r == 503 and codigo(cuerpo) == "SERVICIO_NO_DISPONIBLE" and publica == 200)
        web = os.environ.get("DEMO_WEB_URL")
        if web:
            try:
                estado_web = urllib.request.urlopen(web.rstrip("/") + "/login", timeout=10).status
            except urllib.error.HTTPError as e:
                estado_web = e.code
            veredicto("Redis caído (web)", "/login responde 200 con un mensaje amable, sin 500 (D33)",
                      "/login=%d" % estado_web, estado_web == 200)
        else:
            print("  (web) sin DEMO_WEB_URL: probar a mano que /login muestre el aviso y que una sesión abierta siga (D33)")
    finally:
        compose("start", REDIS)
    ok = espera(lambda: pide("casos", "/api/v1/cases", token=token)[0] == 200)
    veredicto("Redis caído (recuperación)", "la misma sesión vuelve a 200 sin reiniciar servicios",
              "recuperó" if ok else "no recuperó", ok)


def postgres_caido(token):
    compose("stop", POSTGRES)
    try:
        salud, _, _ = pide("casos", "/health")
        r, _, _ = pide("casos", "/api/v1/cases", token=token)
        veredicto("PostgreSQL caído", "/health en 503 y la lectura de casos falla (5xx), sin datos a medias",
                  "/health=%d, casos=%d" % (salud, r), salud == 503 and r >= 500)
    finally:
        compose("start", POSTGRES)
    ok = espera(lambda: pide("casos", "/health")[0] == 200 and pide("casos", "/api/v1/cases", token=token)[0] == 200, 120, 3)
    veredicto("PostgreSQL caído (recuperación)", "/health vuelve a 200 y casos responde",
              "recuperó" if ok else "no recuperó", ok)


def servicio_externo(nombre, contenedor, esperado):
    def corre(token):
        if contenedor not in compose("config", "--services").split():
            print("  pendiente: el servicio %r no está en el compose; define %s en infra/demo_fallos.py al agregarlo."
                  % (contenedor, "MONGO" if contenedor == MONGO else "BUCKET"))
            RESULTADOS.append((nombre, None))
            return
        compose("stop", contenedor)
        try:
            salud, _, _ = pide("estado-servicios", "/api/v1/services/health")
            veredicto(nombre, esperado, "panel=%d (revisar a mano la ruta que lo usa)" % salud, salud == 200)
        finally:
            compose("start", contenedor)
        ok = espera(lambda: pide("casos", "/health")[0] == 200)
        veredicto(nombre + " (recuperación)", "/health vuelve a 200", "recuperó" if ok else "no recuperó", ok)
    return corre


def timeout(token):
    cuerpo = cuerpo_escenario(token)
    compose("pause", "validacion")
    try:
        r, resp, tardo = pide("escenarios", "/api/v1/scenarios", "POST", token, cuerpo, timeout=30)
        veredicto("timeout", "escenarios corta a los ~5 s y responde 503 SERVICIO_NO_DISPONIBLE",
                  "%d %s en %.1f s" % (r, codigo(resp), tardo),
                  r == 503 and codigo(resp) == "SERVICIO_NO_DISPONIBLE" and 4 <= tardo <= 10)
    finally:
        compose("unpause", "validacion")
    ok = espera(lambda: pide("escenarios", "/api/v1/scenarios", token=token)[0] == 200)
    veredicto("timeout (recuperación)", "escenarios vuelve a responder", "recuperó" if ok else "no recuperó", ok)


ESCENARIOS = {
    "servicio": servicio_caido,
    "redis": redis_caido,
    "mongodb": servicio_externo("MongoDB caído", MONGO,
                                "el panel marca la dependencia caída y la corrida termina con su resumen en PostgreSQL"),
    "postgres": postgres_caido,
    "bucket": servicio_externo("bucket caído", BUCKET,
                               "la subida responde 503 y el caso ya creado no se pierde"),
    "timeout": timeout,
}


def main(args):
    if "--lista" in args or "--help" in args or "-h" in args:
        print(AYUDA)
        print("Escenarios: " + ", ".join(ESCENARIOS))
        return 0
    elegidos = args or list(ESCENARIOS)
    desconocidos = [e for e in elegidos if e not in ESCENARIOS]
    if desconocidos:
        sys.exit("Escenarios desconocidos: %s. Disponibles: %s" % (desconocidos, ", ".join(ESCENARIOS)))
    token = abre_sesion()
    for nombre in elegidos:
        print("\n== %s ==" % nombre)
        ESCENARIOS[nombre](token)
    print("\nResumen")
    for nombre, bien in RESULTADOS:
        print("  %-36s %s" % (nombre, {True: "OK", False: "DIFERENTE", None: "PENDIENTE"}[bien]))
    return 1 if any(bien is False for _, bien in RESULTADOS) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
