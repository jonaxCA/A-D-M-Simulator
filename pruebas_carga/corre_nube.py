"""Corre los cinco perfiles (perfiles.py) con escalones contra la máquina de GCP y deja el
resumen. Pide la contraseña de cada cuenta sin mostrarla: no queda en pantalla, en el historial
de la terminal ni en ningún archivo.

    C:\\Temp\\locust\\Scripts\\python.exe pruebas_carga\\corre_nube.py --url https://epidemos.app

Antes, la ventana abierta en la máquina (pruebas_carga/ventana_nube.sh abre); al terminar, se
cierra. Los resultados quedan en docs/pruebas/carga/<fecha>_nube_perfiles/ (o --resultados):
los CSV de Locust, reporte.html, cronologia.csv, usuarios.csv y resumen.md.
"""
import argparse
import datetime
import getpass
import os
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
CUENTAS = ("alex.cavazos", "diana.flores", "karla.trevino", "admin")


def main(argumentos):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", required=True, help="https://<dominio> de la máquina")
    ap.add_argument("--resultados", help="carpeta de resultados")
    ap.add_argument("--paso", type=int, default=20, help="usuarios por escalón (20)")
    ap.add_argument("--segundos", type=int, default=60, help="segundos por escalón (60)")
    ap.add_argument("--maximo", type=int, default=200, help="usuarios del último escalón (200)")
    ap.add_argument("--recuperacion", type=int, default=120, help="segundos de recuperación (120)")
    args = ap.parse_args(argumentos)

    url = args.url.rstrip("/")
    carpeta = Path(args.resultados or RAIZ / "docs" / "pruebas" / "carga" /
                   ("%s_nube_perfiles" % datetime.date.today().isoformat()))
    carpeta.mkdir(parents=True, exist_ok=True)
    escalones = args.maximo // args.paso
    minutos = (escalones * args.segundos + args.recuperacion) / 60
    print("Escalones de %d usuarios cada %d s hasta %d, y %d s de recuperación: unos %.0f minutos."
          % (args.paso, args.segundos, args.maximo, args.recuperacion, minutos))

    cuentas = []
    for cuenta in CUENTAS:
        clave = getpass.getpass("Contraseña de %s (no se muestra): " % cuenta)
        if not clave:
            sys.exit("Sin contraseña para %s: no corro nada." % cuenta)
        cuentas.append("%s:%s" % (cuenta, clave))

    entorno = dict(os.environ, PRUEBAS_CUENTAS=",".join(cuentas), URL_SERVICIOS=url + "/{servicio}",
                   URL_WEB=url, RESULTADOS=str(carpeta), USUARIOS_PASO=str(args.paso),
                   SEGUNDOS_PASO=str(args.segundos), USUARIOS_MAX=str(args.maximo),
                   SEGUNDOS_RECUPERACION=str(args.recuperacion))
    comando = [sys.executable, "-m", "locust", "-f",
               "%s,%s" % (AQUI / "perfiles.py", AQUI / "escalones.py"), "--headless",
               "--csv", str(carpeta / "locust"), "--csv-full-history",
               "--html", str(carpeta / "reporte.html"), "--only-summary"]
    with open(carpeta / "consola.txt", "w", encoding="utf-8") as consola:
        codigo = subprocess.run(comando, env=entorno, stdout=consola, stderr=subprocess.STDOUT).returncode
    print("Locust terminó (código %d). Consola en %s" % (codigo, carpeta / "consola.txt"))
    subprocess.run([sys.executable, str(AQUI / "analiza.py"), str(carpeta)])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
