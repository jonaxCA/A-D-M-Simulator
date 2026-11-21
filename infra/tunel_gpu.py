"""Túnel de la PC con GPU a las bases de la máquina de GCP, para el simulador de abm-gpu
remoto (infra/docker-compose.gpu-remoto.yml, D23).

    python infra/tunel_gpu.py --vm epidemia --zona us-central1-a [--proyecto <id>]

Abre una sesión SSH a la máquina por IAP (gcloud compute ssh --tunnel-through-iap) que solo
reenvía puertos: los de Redis, PostgreSQL y MongoDB, que la máquina publica solo en su
127.0.0.1, quedan en el 127.0.0.1 de la PC. La conexión la abre la PC, así que funciona detrás
de un módem, y en la máquina no se abre ningún puerto a internet: IAP solo deja entrar a
quien tiene permiso en el proyecto (regla de firewall para 35.235.240.0/20 en el puerto 22).

Se queda abierto hasta Ctrl+C. Necesita el SDK de Google Cloud con tu sesión (gcloud auth
login); la primera vez gcloud crea tu llave SSH. En Windows, gcloud usa PuTTY (plink).

    PC                         máquina
    127.0.0.1:16380   ──▶      127.0.0.1:6380   Redis
    127.0.0.1:15433   ──▶      127.0.0.1:5433   PostgreSQL
    127.0.0.1:17018   ──▶      127.0.0.1:27018  MongoDB
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import time

# (nombre, puerto en la PC, puerto en la máquina): los de TUNEL_* y los locales del compose.
PUERTOS = [("Redis", 16380, 6380), ("PostgreSQL", 15433, 5433), ("MongoDB", 17018, 27018)]


def reenvios(puertos=PUERTOS):
    argumentos = []
    for _, local, remoto in puertos:
        argumentos += ["-L", "%d:127.0.0.1:%d" % (local, remoto)]
    return argumentos


def comando(vm, zona, proyecto=None, iap=True, windows=os.name == "nt"):
    gcloud = shutil.which("gcloud") or "gcloud"
    cmd = [gcloud, "compute", "ssh", vm, "--zone", zona]
    if proyecto:
        cmd += ["--project", proyecto]
    if iap:
        cmd.append("--tunnel-through-iap")
    # Lo que va después de -- es para el cliente SSH: -N, solo reenvía, sin abrir una consola.
    extra = ["-N"] + reenvios()
    if not windows:
        # OpenSSH: cortar si un puerto no se pudo reenviar, y mantener viva la conexión.
        extra += ["-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=30"]
    return cmd + ["--"] + extra


def abierto(puerto):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def main(argumentos):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vm", required=True, help="nombre de la máquina en Compute Engine")
    ap.add_argument("--zona", required=True, help="por ejemplo us-central1-a")
    ap.add_argument("--proyecto", help="id del proyecto; si no, el de gcloud config")
    ap.add_argument("--sin-iap", action="store_true",
                    help="SSH directo a la IP externa (el puerto 22 abierto solo a tu IP)")
    args = ap.parse_args(argumentos)

    ocupados = [local for _, local, _ in PUERTOS if abierto(local)]
    if ocupados:
        sys.exit("Ya hay algo escuchando en %s: ¿otro túnel abierto?" % ocupados)
    cmd = comando(args.vm, args.zona, args.proyecto, iap=not args.sin_iap)
    print("Abriendo el túnel:", " ".join(cmd))
    proceso = subprocess.Popen(cmd)
    try:
        for _ in range(60):
            if proceso.poll() is not None:
                sys.exit("gcloud terminó (código %d). Revisa la sesión de gcloud, la zona y la "
                         "regla de firewall de IAP." % proceso.returncode)
            if all(abierto(local) for _, local, _ in PUERTOS):
                break
            time.sleep(1)
        for nombre, local, remoto in PUERTOS:
            print("  %-10s 127.0.0.1:%d -> máquina 127.0.0.1:%d  %s"
                  % (nombre, local, remoto, "listo" if abierto(local) else "SIN RESPUESTA"))
        print("Túnel abierto. Ctrl+C para cerrarlo.")
        return proceso.wait()
    except KeyboardInterrupt:
        proceso.terminate()
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
