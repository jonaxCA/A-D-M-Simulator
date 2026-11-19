"""El certificado de nginx en local (D26): infra/nginx/certs/epidemia.pem y epidemia-key.pem.

Let's Encrypt no emite certificados para localhost, así que en local:

1. Con mkcert (recomendado): el certificado lo firma una autoridad local que mkcert instala en
   la máquina, y el navegador, el escritorio y el emulador de Android confían en él. Instalar esa
   autoridad lo hace cada quien, una vez, porque cambia los certificados en que confía su
   sistema:

       mkcert -install

2. Sin mkcert: uno autofirmado con OpenSSL (el de Git en Windows sirve). Sirve para probar
   nginx, pero nadie confía en él: curl necesita -k y el navegador muestra un aviso.

    python infra/nginx/certificado_local.py           crea el certificado si no existe
    python infra/nginx/certificado_local.py --nuevo   lo vuelve a crear

Nombres que cubre: localhost, 127.0.0.1, ::1, 10.0.2.2 (el emulador de Android) y el nombre de
la máquina. La carpeta certs/ no entra a git: la llave privada nunca se versiona.
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

CARPETA = Path(__file__).resolve().parent / "certs"
CERTIFICADO = CARPETA / "epidemia.pem"
LLAVE = CARPETA / "epidemia-key.pem"
NOMBRES = ["localhost", "127.0.0.1", "::1", "10.0.2.2", socket.gethostname().lower()]
OPENSSL_DE_GIT = Path(r"C:\Program Files\Git\usr\bin\openssl.exe")


def _openssl():
    encontrado = shutil.which("openssl")
    if encontrado:
        return encontrado
    return str(OPENSSL_DE_GIT) if OPENSSL_DE_GIT.exists() else None


def con_mkcert(mkcert):
    subprocess.run([mkcert, "-cert-file", str(CERTIFICADO), "-key-file", str(LLAVE)] + NOMBRES,
                   check=True)
    print("Certificado de mkcert en %s." % CARPETA)
    print("Si es la primera vez en esta máquina, corre tú `mkcert -install` para confiar en él.")


def con_openssl(openssl):
    alternos = ",".join(("IP:%s" if n.replace(".", "").replace(":", "").isdigit() or ":" in n
                         else "DNS:%s") % n for n in NOMBRES)
    # Una configuración propia: la de OPENSSL_CONF puede no existir (la deja, por ejemplo, el
    # instalador del ODBC de PostgreSQL). MSYS_NO_PATHCONV: el OpenSSL de Git no convierte
    # /CN=... en una ruta de Windows.
    entorno = {k: v for k, v in os.environ.items() if k != "OPENSSL_CONF"}
    entorno["MSYS_NO_PATHCONV"] = "1"
    with tempfile.TemporaryDirectory() as temporal:
        config = Path(temporal) / "openssl.cnf"
        config.write_text("[req]\ndistinguished_name = dn\nprompt = no\n[dn]\nCN = EPIDEMIA local\n",
                          encoding="ascii")
        resultado = subprocess.run(
            [openssl, "req", "-config", str(config), "-x509", "-newkey", "rsa:2048", "-nodes",
             "-sha256", "-days", "825", "-subj", "/CN=EPIDEMIA local",
             "-addext", "subjectAltName=" + alternos,
             "-keyout", str(LLAVE), "-out", str(CERTIFICADO)],
            env=entorno, capture_output=True, text=True)
    if resultado.returncode:
        raise SystemExit("openssl falló:\n" + resultado.stderr)
    print("Certificado AUTOFIRMADO en %s: nadie confía en él (curl -k, aviso en el navegador)." % CARPETA)
    print("Para uno de confianza, instala mkcert y corre esto con --nuevo.")


def main(argumentos):
    if CERTIFICADO.exists() and LLAVE.exists() and "--nuevo" not in argumentos:
        print("Ya existe %s; para reemplazarlo usa --nuevo." % CERTIFICADO)
        return 0
    CARPETA.mkdir(exist_ok=True)
    mkcert = shutil.which("mkcert")
    if mkcert:
        con_mkcert(mkcert)
        return 0
    openssl = _openssl()
    if openssl:
        con_openssl(openssl)
        return 0
    print("No encontré mkcert ni openssl. Instala mkcert (https://github.com/FiloSottile/mkcert).")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
