import getpass
import http.cookiejar
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AYUDA = '''Demostración de caídas (N5) contra el compose de la demostración (infra/docker-compose.yml, perfil '*').

    python infra/demo_fallos.py --lista            muestra los escenarios
    python infra/demo_fallos.py                    corre todos
    python infra/demo_fallos.py redis timeout      corre solo esos

Escenario extra 'web': con DEMO_WEB_URL (la web corriendo), comprueba que cerrar sesión revoca la cookie;
el de redis también revisa la web (D33).

Necesita el compose arriba y una cuenta de la demostración: DEMO_USUARIO (por defecto admin) y
DEMO_PASSWORD (si falta, la pide). Por escenario: detiene o pausa un contenedor, llama a las
rutas, imprime lo esperado contra lo observado, restaura y verifica que todo regrese.
MongoDB ya está en el compose principal (D1). El bucket todavía no (bloque D2); para la demostración
existe infra/docker-compose.fallos.yml (un emulador del bucket, declarado en evidencias). Se usa con
DEMO_COMPOSE_FILES=infra/docker-compose.yml,infra/docker-compose.fallos.yml (y se levanta el compose
con esos mismos archivos). Sin él, el escenario del bucket queda PENDIENTE.'''

RAIZ = Path(__file__).resolve().parent.parent
HOST = os.environ.get("DEMO_HOST", "127.0.0.1")
PROYECTO = os.environ.get("DEMO_PROYECTO")
REDIS, POSTGRES = "redis", "postgres"
MONGO = "mongodb"
BUCKET = "bucket"
PUERTOS = {"auth": 5201, "regiones": 5213, "enfermedades": 5211, "casos": 5221, "escenarios": 5231,
           "estado-servicios": 5262, "resultados": 5243, "evidencias": 5224}
ARCHIVOS = os.environ.get("DEMO_COMPOSE_FILES", "infra/docker-compose.yml").split(",")
BASE = ["docker", "compose"] + (["-p", PROYECTO] if PROYECTO else [])
for archivo in ARCHIVOS:
    BASE += ["-f", str(RAIZ / archivo)]
BASE += ["--profile", "*"]
RESULTADOS = []
CUENTA = {}


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


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
    CUENTA.update(usuario=usuario, clave=clave)
    _, captcha, _ = pide("auth", "/api/v1/auth/captcha")
    a, b = captcha["pregunta"].split("+")
    estado, sesion, _ = pide("auth", "/api/v1/auth/login", "POST", cuerpo={
        "usuario": usuario, "password": clave, "captcha_id": captcha["captcha_id"],
        "captcha_respuesta": str(int(a) + int(b))})
    if estado != 200:
        sys.exit("No se pudo iniciar sesión (%d). ¿Está arriba el compose y es correcta la cuenta?" % estado)
    return sesion["access_token"]


def web_pide(opener, ruta, datos=None):
    base = os.environ["DEMO_WEB_URL"].rstrip("/")
    cuerpo = urllib.parse.urlencode(datos).encode() if datos else None
    try:
        with opener.open(base + ruta, cuerpo, timeout=15) as r:
            return r.status, r.headers.get("Location", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location", ""), e.read().decode("utf-8", "replace")


def web_sesion():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), SinRedireccion)
    estado, _, _ = web_pide(opener, "/login", {"usuario": CUENTA["usuario"], "password": CUENTA["clave"]})
    return opener, jar, estado


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
    simulables = [e for e in enfermedades["enfermedades"]
                  if all(p["estado"] != "sin_fuente" for p in e["parametros"]["detalle"])]
    return {"name": "Demo fallos %d" % time.time(), "description": "Demostración de caídas.",
            "disease_id": (simulables or enfermedades["enfermedades"])[0]["id"], "region_id": regiones["municipios"][0]["id"],
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
    web = os.environ.get("DEMO_WEB_URL")
    abierta = web_sesion() if web else None
    compose("stop", REDIS)
    try:
        r, cuerpo, _ = pide("casos", "/api/v1/cases", token=token)
        publica, _, _ = pide("regiones", "/api/v1/regions")
        veredicto("Redis caído", "ruta protegida 503 SERVICIO_NO_DISPONIBLE (falla cerrada); catálogo público 200",
                  "protegida=%d %s, pública=%d" % (r, codigo(cuerpo), publica),
                  r == 503 and codigo(cuerpo) == "SERVICIO_NO_DISPONIBLE" and publica == 200)
        if web:
            continua, _, _ = web_pide(abierta[0], "/dashboard")
            nueva = web_sesion()[2]
            _, _, texto = web_pide(urllib.request.build_opener(SinRedireccion), "/login",
                                   {"usuario": CUENTA["usuario"], "password": CUENTA["clave"]})
            veredicto("Redis caído (web)", "una sesión abierta sigue en 200; entrar de nuevo da 503 con un mensaje amable, sin 500 (D33)",
                      "sesión abierta /dashboard=%d (login previo=%d), login nuevo=%d, mensaje amable=%s"
                      % (continua, abierta[2], nueva, "no está disponible" in texto),
                      abierta[2] == 302 and continua == 200 and nueva == 503 and "no está disponible" in texto)
        else:
            print("  (web) sin DEMO_WEB_URL: probar a mano que /login muestre el aviso y que una sesión abierta siga (D33)")
    finally:
        compose("start", REDIS)
    ok = espera(lambda: pide("casos", "/api/v1/cases", token=token)[0] == 200)
    veredicto("Redis caído (recuperación)", "la misma sesión vuelve a 200 sin reiniciar servicios",
              "recuperó" if ok else "no recuperó", ok)
    if web:
        estado, _, _ = web_pide(abierta[0], "/dashboard")
        nuevo_login = web_sesion()[2]
        veredicto("Redis caído (web, recuperación)", "la sesión abierta sigue en 200 y se puede entrar de nuevo",
                  "dashboard=%d, login nuevo=%d" % (estado, nuevo_login), estado == 200 and nuevo_login == 302)


def web_cierre(token):
    if not os.environ.get("DEMO_WEB_URL"):
        print("  pendiente: define DEMO_WEB_URL (p. ej. http://127.0.0.1:5050) con la web arriba.")
        RESULTADOS.append(("web: cierre de sesión", None))
        return
    opener, jar, login = web_sesion()
    antes, _, _ = web_pide(opener, "/dashboard")
    copia = http.cookiejar.CookieJar()
    for c in jar:
        copia.set_cookie(c)
    web_pide(opener, "/logout")
    copiado = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(copia), SinRedireccion)
    despues, destino, _ = web_pide(copiado, "/dashboard")
    veredicto("web: cierre de sesión", "tras /logout, la cookie copiada ya no sirve: /dashboard redirige a /login",
              "login=%d, /dashboard antes=%d, con la cookie copiada después=%d -> %s" % (login, antes, despues, destino),
              login == 302 and antes == 200 and despues == 302 and "/login" in destino)


def postgres_caido(token):
    compose("stop", POSTGRES)
    try:
        salud, _, _ = pide("casos", "/health")
        r, cuerpo, _ = pide("casos", "/api/v1/cases", token=token)
        codigo = cuerpo.get("codigo") if isinstance(cuerpo, dict) else None
        veredicto("PostgreSQL caído", "/health en 503 y la lectura de casos da 503 SERVICIO_NO_DISPONIBLE (no 500), sin datos a medias",
                  "/health=%d, casos=%d %s" % (salud, r, codigo), salud == 503 and r == 503 and codigo == "SERVICIO_NO_DISPONIBLE")
    finally:
        compose("start", POSTGRES)
    ok = espera(lambda: pide("casos", "/health")[0] == 200 and pide("casos", "/api/v1/cases", token=token)[0] == 200, 120, 3)
    veredicto("PostgreSQL caído (recuperación)", "/health vuelve a 200 y casos responde",
              "recuperó" if ok else "no recuperó", ok)


def panel_de(nombre):
    _, panel, _ = pide("estado-servicios", "/api/v1/services/health")
    return next((s for s in panel.get("servicios", []) if s["nombre"] == nombre), {})


def servicio_externo(nombre, contenedor, usuario, esperado):
    def corre(token):
        if contenedor not in compose("config", "--services").split():
            print("  pendiente: %r no está en el compose; usa DEMO_COMPOSE_FILES con infra/docker-compose.fallos.yml."
                  % contenedor)
            RESULTADOS.append((nombre, None))
            return
        compose("stop", contenedor)
        try:
            salud, cuerpo, _ = pide(usuario, "/health")
            en_panel = espera(lambda: contenedor in (panel_de(usuario).get("causas") or []), 90)
            ficha = panel_de(usuario)
            otro, _, _ = pide("regiones", "/api/v1/regions")
            veredicto(nombre, esperado,
                      "%s /health=%d estado=%s %s=%s; panel: estado=%s causas=%s; regiones=%d"
                      % (usuario, salud, cuerpo.get("estado"), contenedor, cuerpo.get(contenedor),
                         ficha.get("estado"), ficha.get("causas"), otro),
                      salud == 503 and cuerpo.get("estado") == "degradado" and cuerpo.get(contenedor) is False
                      and en_panel and ficha.get("estado") == "degradado" and otro == 200)
        finally:
            compose("start", contenedor)
        ok = espera(lambda: pide(usuario, "/health")[0] == 200 and panel_de(usuario).get("estado") == "ok", 120)
        veredicto(nombre + " (recuperación)", "/health de %s vuelve a 200 y el panel a ok" % usuario,
                  "recuperó" if ok else "no recuperó", ok)
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
    "mongodb": servicio_externo("MongoDB caído", MONGO, "resultados",
                                "resultados: /health 503 degradado con mongodb en false; el panel lista mongodb en causas; los demás siguen"),
    "postgres": postgres_caido,
    "bucket": servicio_externo("bucket caído", BUCKET, "evidencias",
                               "evidencias: /health 503 degradado con bucket en false; el panel lista bucket en causas; los demás siguen"),
    "timeout": timeout,
    "web": web_cierre,
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
