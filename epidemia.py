#!/usr/bin/env python3
# Atajos para levantar y usar el proyecto. Desde cualquier carpeta:
#
#     python epidemia.py up        microservicios en Docker (crea infra/.env si falta)
#     python epidemia.py web       sitio en http://localhost:5000
#     python epidemia.py desktop   app de escritorio (usa frontend_desktop/.venv si existe)
#     python epidemia.py desktop --nube   la misma, contra los servicios de https://epidemos.app
#     python epidemia.py estado    estado de los contenedores
#     python epidemia.py logs [servicio]
#     python epidemia.py pruebas [args]  motor, microservicios y escritorio; args van a pytest
#     python epidemia.py lint      ruff (sintaxis de Python 3.12, nombres sin definir)
#     python epidemia.py prepara-pruebas  crea de nuevo la base de pruebas
#     python epidemia.py verifica  compara el dump con las migraciones
#     python epidemia.py psql | redis | mongo   consola dentro del contenedor
#     python epidemia.py doctor    revisa Python, Docker, infra/.env y la salud de los servicios
#     python epidemia.py down      baja los contenedores (conserva la base)
import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PERFILES = ["identidad", "catalogos", "vigilancia", "escenarios", "simulacion", "analitica", "plataforma"]
DIRECTORIO_NUBE = "https://epidemos.app/estado-servicios"
COMPOSE = ["docker", "compose", "-f", "infra/docker-compose.yml"]
PRUEBAS = ["microservicios", "procesamiento/tests", "frontend_desktop"]
CONSOLAS = {
    "psql": ("postgres", 'psql -U postgres -d "$POSTGRES_DB"'),
    "redis": ("redis", "redis-cli"),
    "mongo": ("mongodb", 'mongosh -u root -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin epidemia'),
}


def correr(cmd):
    try:
        return subprocess.call(cmd, cwd=str(RAIZ))
    except FileNotFoundError:
        sys.exit("No se encontró «%s». Instálalo (ver docs/INSTALACION.md)." % cmd[0])
    except KeyboardInterrupt:
        return 130


def compose(*args, todos=False):
    perfiles = ["--profile", "*"] if todos else [p for n in PERFILES for p in ("--profile", n)]
    return correr(COMPOSE + perfiles + list(args))


def python(*args, carpeta=None):
    venv = RAIZ / (carpeta or "") / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return correr([str(venv) if carpeta and venv.exists() else sys.executable] + list(args))


def up(_):
    python("infra/genera_env.py")
    return compose("up", "-d", "--build", "--wait")


def web(_):
    try:
        urllib.request.urlopen("http://127.0.0.1:5201/health", timeout=2)
    except Exception:
        print("Aviso: `auth` no responde en :5201; levanta los servicios con `python epidemia.py up`.")
    return python("-m", "frontend_web.run")


def desktop(a):
    if a.nube:
        os.environ["EPIDEMIA_DIRECTORIO"] = DIRECTORIO_NUBE
    return python("-m", "frontend_desktop.run", carpeta="frontend_desktop")


def es_ruta(arg):
    return not arg.startswith("-") and (RAIZ / arg.split("::")[0]).exists()


def salud(puerto):
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/health" % puerto, timeout=2)
        return True
    except Exception:
        return False


def doctor(_):
    fallas = 0

    def reporta(ok, texto):
        nonlocal fallas
        fallas += not ok
        print("[%s] %s" % ("ok" if ok else "!!", texto))

    reporta(sys.version_info >= (3, 12), "Python %d.%d (se pide 3.12 o más)" % sys.version_info[:2])
    docker = shutil.which("docker")
    reporta(bool(docker), "docker en el PATH")
    if docker:
        ok = subprocess.call(["docker", "compose", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
        reporta(ok, "docker compose disponible")
    reporta((RAIZ / "infra" / ".env").exists(), "infra/.env existe (si no: python infra/genera_env.py)")
    compose_yml = (RAIZ / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    puertos = sorted(set(int(p) for p in re.findall(r'"(52\d\d):8000"', compose_yml)))
    caidos = [p for p in puertos if not salud(p)]
    reporta(not caidos, "%d de %d servicios responden /health" % (len(puertos) - len(caidos), len(puertos)))
    if caidos and len(caidos) < len(puertos):
        print("     sin respuesta en: %s" % ", ".join(map(str, caidos)))
    elif caidos:
        print("     ninguno responde; ¿falta `python epidemia.py up`?")
    return 1 if fallas else 0


def main():
    ap = argparse.ArgumentParser(description="Atajos de EPIDEMIA.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    comandos = {
        "up": ("Levanta los microservicios en Docker", up),
        "down": ("Baja todos los contenedores; conserva la base", lambda a: compose("down", todos=True)),
        "web": ("Corre el sitio web en :5000", web),
        "estado": ("Estado de los contenedores", lambda a: compose("ps")),
        "lint": ("Corre ruff sobre todo el repositorio", lambda a: python("-m", "ruff", "check", ".")),
        "prepara-pruebas": ("Crea de nuevo la base de pruebas",
                            lambda a: python("datos/scripts/prepara_base_pruebas.py")),
        "verifica": ("Compara el dump con las migraciones", lambda a: python("datos/scripts/verifica_migraciones.py")),
        "doctor": ("Revisa Python, Docker, infra/.env y la salud de los servicios", doctor),
    }
    for nombre, (servicio, cmd) in CONSOLAS.items():
        comandos[nombre] = ("Consola de %s en su contenedor" % servicio,
                            lambda a, s=servicio, c=cmd: compose("exec", s, "sh", "-c", c))
    for nombre, (ayuda, f) in comandos.items():
        sub.add_parser(nombre, help=ayuda).set_defaults(f=f)
    escritorio = sub.add_parser("desktop", help="Abre la app de escritorio")
    escritorio.add_argument("--nube", action="store_true", help="usa los servicios de %s" % DIRECTORIO_NUBE)
    escritorio.set_defaults(f=desktop)
    pruebas = sub.add_parser("pruebas", help="Corre pytest del motor, los microservicios y el escritorio")
    pruebas.add_argument("args", nargs="*", help="se pasan a pytest; sin rutas corre las tres carpetas")
    pruebas.set_defaults(f=lambda a: python("-m", "pytest", *(a.args if any(es_ruta(x) for x in a.args)
                                                              else PRUEBAS + a.args)))
    logs = sub.add_parser("logs", help="Sigue los logs de un servicio (o de todos)")
    logs.add_argument("servicio", nargs="?")
    logs.set_defaults(f=lambda a: compose("logs", "-f", "--tail", "100", *([a.servicio] if a.servicio else [])))
    argv = sys.argv[1:]
    args = ap.parse_args(argv[:1] if argv[:1] == ["pruebas"] else argv)
    if args.cmd == "pruebas":
        args.args = argv[1:]
    sys.exit(args.f(args))


if __name__ == "__main__":
    main()
