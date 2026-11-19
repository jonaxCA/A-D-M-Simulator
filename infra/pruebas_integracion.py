# Pruebas de integración contra los contenedores, en un compose aparte (bloque O2).
#
#     python infra/pruebas_integracion.py              levanta, prueba y borra
#     python infra/pruebas_integracion.py --conservar  deja arriba el compose de pruebas
#     python infra/pruebas_integracion.py -- -k flujo  lo que va después de -- es para pytest
#     python infra/pruebas_integracion.py --gpu        también levanta simulador-gpu (abm-gpu)
#     python infra/pruebas_integracion.py --nginx      los servicios detrás de nginx (D25)
#
# Sin --gpu se levantan todos los perfiles menos gpu, que necesita una GPU de NVIDIA y NVIDIA
# Container Toolkit (en Windows, Docker Desktop con WSL 2). Con --gpu, corridas acepta además
# abm-gpu y test_compose_gpu.py corre una corrida en ese simulador; sin él, esa prueba se salta.
#
# Con --nginx se suma infra/docker-compose.nginx.yml: nginx en 80 y 443, y ningún servicio
# publica su puerto. Como las demás pruebas llaman a los servicios por su puerto, en ese modo
# solo corre test_compose_nginx.py. Si no existe el certificado de infra/nginx/certs/, se crea
# con infra/nginx/certificado_local.py.
#
# Usa su propio proyecto (epidemia-pruebas), con sus propios volúmenes de PostgreSQL, Redis y MongoDB,
# y la base se llama simulador_epidemico_pruebas: nunca toca la base ni el Redis de la
# demostración. Sus contraseñas, aleatorias, van en infra/.env.pruebas (fuera de git). Publica
# los mismos puertos que el compose principal, así que ese tiene que estar abajo.
import os
import socket
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
ENTORNO = AQUI / ".env.pruebas"
PROYECTO = "epidemia-pruebas"
FIJOS = {"POSTGRES_DB": "simulador_epidemico_pruebas", "REDIS_PUERTO_LOCAL": "6382",
         "POSTGRES_PUERTO_LOCAL": "5435", "MONGO_PUERTO_LOCAL": "27019"}
# Con --nginx: un tiempo máximo corto para la prueba del timeout, mayor que los 5 s de llamar().
FIJOS_NGINX = {"NGINX_TIEMPO_MAXIMO": "8s"}
ARCHIVOS = ["-f", str(AQUI / "docker-compose.yml"), "-f", str(AQUI / "docker-compose.pruebas.yml")]
ARCHIVO_NGINX = ["-f", str(AQUI / "docker-compose.nginx.yml")]
CONTENEDORES = RAIZ / "microservicios" / "pruebas_integracion" / "contenedores"
# Los del catálogo, la consola y los locales de PostgreSQL, Redis y MongoDB de este compose.
PUERTOS = [5201, 5202, 5203, 5204, 5211, 5212, 5213, 5214, 5215, 5221, 5222, 5223, 5224, 5225,
           5231, 5232, 5233, 5234, 5235, 5241, 5242, 5243, 5244, 5245, 5251, 5252, 5253, 5260,
           5261, 5262, 6382, 5435, 27019]
PUERTOS_NGINX = [80, 443]


def prepara_entorno(gpu, nginx=False):
    fijos = dict(FIJOS, MOTORES_HABILITADOS="abm-ref,abm-gpu" if gpu else "abm-ref")
    if nginx:
        fijos.update(FIJOS_NGINX)
    subprocess.run([sys.executable, str(AQUI / "genera_env.py"), str(ENTORNO)], check=True)
    lineas = [l for l in ENTORNO.read_text(encoding="utf-8").splitlines()
              if l.split("=", 1)[0] not in fijos]
    lineas += ["%s=%s" % par for par in fijos.items()]
    ENTORNO.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")


def comando_compose(gpu, nginx=False):
    """docker compose con el proyecto de pruebas y sus perfiles: todos, y gpu solo si se pide."""
    archivos = ARCHIVOS + (ARCHIVO_NGINX if nginx else [])
    base = ["docker", "compose", "-p", PROYECTO] + archivos + ["--env-file", str(ENTORNO)]
    perfiles = subprocess.run(base + ["config", "--profiles"], capture_output=True, text=True,
                              check=True).stdout.split()
    return base + [arg for p in perfiles if gpu or p != "gpu" for arg in ("--profile", p)]


def ocupados(nginx=False):
    resultado = []
    for puerto in PUERTOS + (PUERTOS_NGINX if nginx else []):
        with socket.socket() as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", puerto)) == 0:
                resultado.append(puerto)
    return resultado


def main(argumentos):
    propios = argumentos[:argumentos.index("--")] if "--" in argumentos else argumentos
    conservar = "--conservar" in propios
    gpu = "--gpu" in propios
    nginx = "--nginx" in propios
    para_pytest = argumentos[argumentos.index("--") + 1:] if "--" in argumentos else []
    en_uso = ocupados(nginx)
    if en_uso:
        sys.exit("Puertos ocupados: %s. Detén el compose de la demostración "
                 "(docker compose -f infra/docker-compose.yml down) y vuelve a correr esto."
                 % ", ".join(map(str, en_uso)))
    if nginx:
        subprocess.run([sys.executable, str(AQUI / "nginx" / "certificado_local.py")], check=True)
    prepara_entorno(gpu, nginx)
    COMPOSE = comando_compose(gpu, nginx)
    try:
        if subprocess.run(COMPOSE + ["up", "-d", "--build", "--wait"]).returncode:
            subprocess.run(COMPOSE + ["ps", "-a"])
            sys.exit("El compose de pruebas no quedó healthy.")
        entorno = dict(os.environ, EPIDEMIA_PRUEBAS_ENV=str(ENTORNO),
                       EPIDEMIA_PRUEBAS_PROYECTO=PROYECTO)
        destino = [str(CONTENEDORES)]
        if nginx:
            entorno["EPIDEMIA_PRUEBAS_NGINX"] = "https://localhost"
            destino = [str(CONTENEDORES / "test_compose_nginx.py")]
        codigo = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider"]
                                + destino + para_pytest, cwd=RAIZ, env=entorno).returncode
    finally:
        if not conservar:
            subprocess.run(COMPOSE + ["down", "-v", "--remove-orphans"])
    sys.exit(codigo)


if __name__ == "__main__":
    main(sys.argv[1:])
