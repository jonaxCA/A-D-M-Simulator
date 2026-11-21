# Pruebas de integración contra los contenedores, en un compose aparte (bloque O2).
#
#     python infra/pruebas_integracion.py              levanta, prueba y borra
#     python infra/pruebas_integracion.py --conservar  deja arriba el compose de pruebas
#     python infra/pruebas_integracion.py -- -k flujo  lo que va después de -- es para pytest
#     python infra/pruebas_integracion.py --gpu        también levanta simulador-gpu (abm-gpu)
#     python infra/pruebas_integracion.py --nginx      los servicios detrás de nginx (D25)
#     python infra/pruebas_integracion.py --gpu-remoto abm-gpu desde un simulador fuera del compose (D23)
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
# Con --gpu-remoto el compose de pruebas hace de máquina de la nube, sin simulador-gpu, y el
# simulador de abm-gpu corre aparte, con infra/docker-compose.gpu-remoto.yml, como en una PC
# con GPU. Lo conecta un túnel simulado en los mismos puertos que el de verdad
# (infra/tunel_gpu.py): 15433, 16380 y 17018 en el 127.0.0.1 de esta máquina. Corre
# test_compose_gpu_remoto.py. Necesita una GPU de NVIDIA, como --gpu.
#
# Usa su propio proyecto (epidemia-pruebas), con sus propios volúmenes de PostgreSQL, Redis y MongoDB,
# y la base se llama simulador_epidemico_pruebas: nunca toca la base ni el Redis de la
# demostración. Sus contraseñas, aleatorias, van en infra/.env.pruebas (fuera de git). Publica
# los mismos puertos que el compose principal, así que ese tiene que estar abajo.
import os
import socket
import subprocess
import sys
import threading
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
# Los del catálogo, la consola, la web y los locales de PostgreSQL, Redis y MongoDB de este
# compose.
PUERTOS = [5000, 5201, 5202, 5203, 5204, 5211, 5212, 5213, 5214, 5215, 5221, 5222, 5223, 5224, 5225,
           5231, 5232, 5233, 5234, 5235, 5241, 5242, 5243, 5244, 5245, 5251, 5252, 5253, 5260,
           5261, 5262, 6382, 5435, 27019]
PUERTOS_NGINX = [80, 443]
# --gpu-remoto: el simulador de abm-gpu en su propio proyecto, y el túnel simulado. Cada puerto
# del túnel (los de infra/tunel_gpu.py) lleva al local de la base del compose de pruebas.
PROYECTO_REMOTO = "epidemia-pruebas-gpu-remoto"
ENTORNO_REMOTO = AQUI / ".env.gpu-remoto.pruebas"
ARCHIVO_REMOTO = AQUI / "docker-compose.gpu-remoto.yml"
TUNEL_SIMULADO = {15433: int(FIJOS["POSTGRES_PUERTO_LOCAL"]), 16380: int(FIJOS["REDIS_PUERTO_LOCAL"]),
                  17018: int(FIJOS["MONGO_PUERTO_LOCAL"])}


def prepara_entorno(gpu, nginx=False, gpu_remoto=False):
    motores = "abm-ref,abm-gpu" if gpu or gpu_remoto else "abm-ref"
    fijos = dict(FIJOS, MOTORES_HABILITADOS=motores)
    if nginx:
        fijos.update(FIJOS_NGINX)
    subprocess.run([sys.executable, str(AQUI / "genera_env.py"), str(ENTORNO)], check=True)
    lineas = [l for l in ENTORNO.read_text(encoding="utf-8").splitlines()
              if l.split("=", 1)[0] not in fijos]
    lineas += ["%s=%s" % par for par in fijos.items()]
    ENTORNO.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")


def prepara_entorno_remoto():
    """El .env del simulador remoto, como lo llenaría alguien con los secretos de la nube: aquí
    salen del .env.pruebas. notificaciones se alcanza por su puerto, en vez de por nginx."""
    valores = dict(l.split("=", 1) for l in ENTORNO.read_text(encoding="utf-8").splitlines()
                   if "=" in l and not l.startswith("#"))
    remoto = {clave: valores[clave] for clave in ("JWT_SECRET_KEY", "REDIS_PASSWORD",
                                                  "DB_PASSWORD_SIMULADOR", "MONGO_PASSWORD")}
    remoto["POSTGRES_DB"] = FIJOS["POSTGRES_DB"]
    remoto["SERVICIO_NOTIFICACIONES_URL"] = "http://host.docker.internal:5261"
    ENTORNO_REMOTO.write_text("".join("%s=%s\n" % par for par in remoto.items()),
                              encoding="utf-8", newline="\n")


def comando_remoto():
    return ["docker", "compose", "-p", PROYECTO_REMOTO, "--env-file", str(ENTORNO_REMOTO),
            "-f", str(ARCHIVO_REMOTO)]


def _canaliza(origen, destino):
    try:
        while True:
            datos = origen.recv(65536)
            if not datos:
                break
            destino.sendall(datos)
    except OSError:
        pass
    finally:
        for s in (origen, destino):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def tunel_simulado(pares=TUNEL_SIMULADO):
    """Reenvía cada puerto del 127.0.0.1 local a otro, como el -L de SSH. Regresa los sockets
    que escuchan; cerrarlos lo detiene."""
    servidores = []
    for local, destino in pares.items():
        servidor = socket.create_server(("127.0.0.1", local))

        def acepta(servidor=servidor, destino=destino):
            while True:
                try:
                    cliente, _ = servidor.accept()
                    remoto = socket.create_connection(("127.0.0.1", destino), timeout=5)
                    remoto.settimeout(None)
                except OSError:
                    if servidor.fileno() == -1:
                        return
                    continue
                for a, b in ((cliente, remoto), (remoto, cliente)):
                    threading.Thread(target=_canaliza, args=(a, b), daemon=True).start()

        threading.Thread(target=acepta, daemon=True).start()
        servidores.append(servidor)
    return servidores


def comando_compose(gpu, nginx=False):
    """docker compose con el proyecto de pruebas y sus perfiles: todos, y gpu solo si se pide."""
    archivos = ARCHIVOS + (ARCHIVO_NGINX if nginx else [])
    base = ["docker", "compose", "-p", PROYECTO] + archivos + ["--env-file", str(ENTORNO)]
    perfiles = subprocess.run(base + ["config", "--profiles"], capture_output=True, text=True,
                              check=True).stdout.split()
    return base + [arg for p in perfiles if gpu or p != "gpu" for arg in ("--profile", p)]


def ocupados(nginx=False, gpu_remoto=False):
    resultado = []
    extra = (PUERTOS_NGINX if nginx else []) + (list(TUNEL_SIMULADO) if gpu_remoto else [])
    for puerto in PUERTOS + extra:
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
    gpu_remoto = "--gpu-remoto" in propios
    para_pytest = argumentos[argumentos.index("--") + 1:] if "--" in argumentos else []
    en_uso = ocupados(nginx, gpu_remoto)
    if en_uso:
        sys.exit("Puertos ocupados: %s. Detén el compose de la demostración "
                 "(docker compose -f infra/docker-compose.yml down) y vuelve a correr esto."
                 % ", ".join(map(str, en_uso)))
    if nginx:
        subprocess.run([sys.executable, str(AQUI / "nginx" / "certificado_local.py")], check=True)
    prepara_entorno(gpu, nginx, gpu_remoto)
    COMPOSE = comando_compose(gpu, nginx)
    tunel = []
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
        if gpu_remoto:
            tunel = tunel_simulado()
            prepara_entorno_remoto()
            if subprocess.run(comando_remoto() + ["up", "-d", "--build", "--wait"]).returncode:
                subprocess.run(comando_remoto() + ["logs", "--tail", "40"])
                sys.exit("El simulador remoto no quedó healthy.")
            entorno["EPIDEMIA_PRUEBAS_GPU_REMOTO"] = PROYECTO_REMOTO
            destino = [str(CONTENEDORES / "test_compose_gpu_remoto.py")]
        codigo = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider"]
                                + destino + para_pytest, cwd=RAIZ, env=entorno).returncode
    finally:
        if gpu_remoto and not conservar:
            if ENTORNO_REMOTO.exists():
                subprocess.run(comando_remoto() + ["down", "-v", "--remove-orphans"])
            ENTORNO_REMOTO.unlink(missing_ok=True)
        for servidor in tunel:
            servidor.close()
        if not conservar:
            subprocess.run(COMPOSE + ["down", "-v", "--remove-orphans"])
    sys.exit(codigo)


if __name__ == "__main__":
    main(sys.argv[1:])
