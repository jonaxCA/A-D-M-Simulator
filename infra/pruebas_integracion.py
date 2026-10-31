# Pruebas de integración contra los contenedores, en un compose aparte (bloque O2).
#
#     python infra/pruebas_integracion.py              levanta, prueba y borra
#     python infra/pruebas_integracion.py --conservar  deja arriba el compose de pruebas
#     python infra/pruebas_integracion.py -- -k flujo  lo que va después de -- es para pytest
#
# Usa su propio proyecto (epidemia-pruebas), con sus propios volúmenes de PostgreSQL y de Redis,
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
         "POSTGRES_PUERTO_LOCAL": "5435"}
COMPOSE = ["docker", "compose", "-p", PROYECTO, "-f", str(AQUI / "docker-compose.yml"),
           "-f", str(AQUI / "docker-compose.pruebas.yml"), "--env-file", str(ENTORNO), "--profile", "*"]
# Los del catálogo, la consola y los locales de PostgreSQL y Redis de este compose.
PUERTOS = [5201, 5202, 5203, 5204, 5211, 5212, 5213, 5214, 5215, 5221, 5222, 5223, 5231, 5232, 5233,
           5234, 5235, 5241, 5242, 5243, 5244, 5245, 5251, 5252, 5253, 5260, 5261, 5262, 6382, 5435]


def prepara_entorno():
    subprocess.run([sys.executable, str(AQUI / "genera_env.py"), str(ENTORNO)], check=True)
    lineas = [l for l in ENTORNO.read_text(encoding="utf-8").splitlines()
              if l.split("=", 1)[0] not in FIJOS]
    lineas += ["%s=%s" % par for par in FIJOS.items()]
    ENTORNO.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")


def ocupados():
    resultado = []
    for puerto in PUERTOS:
        with socket.socket() as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", puerto)) == 0:
                resultado.append(puerto)
    return resultado


def main(argumentos):
    conservar = "--conservar" in argumentos
    para_pytest = argumentos[argumentos.index("--") + 1:] if "--" in argumentos else []
    en_uso = ocupados()
    if en_uso:
        sys.exit("Puertos ocupados: %s. Detén el compose de la demostración "
                 "(docker compose -f infra/docker-compose.yml down) y vuelve a correr esto."
                 % ", ".join(map(str, en_uso)))
    prepara_entorno()
    try:
        if subprocess.run(COMPOSE + ["up", "-d", "--build", "--wait"]).returncode:
            subprocess.run(COMPOSE + ["ps", "-a"])
            sys.exit("El compose de pruebas no quedó healthy.")
        entorno = dict(os.environ, EPIDEMIA_PRUEBAS_ENV=str(ENTORNO),
                       EPIDEMIA_PRUEBAS_PROYECTO=PROYECTO)
        codigo = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
                                 str(RAIZ / "microservicios" / "pruebas_integracion" / "contenedores")]
                                + para_pytest, cwd=RAIZ, env=entorno).returncode
    finally:
        if not conservar:
            subprocess.run(COMPOSE + ["down", "-v", "--remove-orphans"])
    sys.exit(codigo)


if __name__ == "__main__":
    main(sys.argv[1:])
