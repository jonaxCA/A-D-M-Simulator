#!/usr/bin/env python3
# Atajos para levantar y usar el proyecto. Desde cualquier carpeta:
#
#     python epidemia.py up        microservicios en Docker (crea infra/.env si falta)
#     python epidemia.py web       sitio en http://localhost:5000
#     python epidemia.py desktop   app de escritorio (usa frontend_desktop/.venv si existe)
#     python epidemia.py estado    estado de los contenedores
#     python epidemia.py logs [servicio]
#     python epidemia.py pruebas   motor, microservicios y escritorio
#     python epidemia.py down      baja los contenedores (conserva la base)
import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PERFILES = ["identidad", "catalogos", "vigilancia", "escenarios", "simulacion", "analitica", "plataforma"]
COMPOSE = ["docker", "compose", "-f", "infra/docker-compose.yml"]
PRUEBAS = ["microservicios", "procesamiento/tests", "frontend_desktop"]


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


def main():
    ap = argparse.ArgumentParser(description="Atajos de EPIDEMIA.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    comandos = {
        "up": ("Levanta los microservicios en Docker", up),
        "down": ("Baja todos los contenedores; conserva la base", lambda a: compose("down", todos=True)),
        "web": ("Corre el sitio web en :5000", web),
        "desktop": ("Abre la app de escritorio", lambda a: python("-m", "frontend_desktop.run", carpeta="frontend_desktop")),
        "estado": ("Estado de los contenedores", lambda a: compose("ps")),
        "pruebas": ("Corre pytest del motor, los microservicios y el escritorio",
                    lambda a: python("-m", "pytest", *PRUEBAS)),
    }
    for nombre, (ayuda, f) in comandos.items():
        sub.add_parser(nombre, help=ayuda).set_defaults(f=f)
    logs = sub.add_parser("logs", help="Sigue los logs de un servicio (o de todos)")
    logs.add_argument("servicio", nargs="?")
    logs.set_defaults(f=lambda a: compose("logs", "-f", "--tail", "100", *([a.servicio] if a.servicio else [])))
    args = ap.parse_args()
    sys.exit(args.f(args))


if __name__ == "__main__":
    main()
