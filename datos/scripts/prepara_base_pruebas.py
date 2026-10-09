"""
Crea, o vuelve a crear desde cero, la base en la que corren las pruebas.

Hace lo mismo que los pasos 2 y 3 de docs/INSTALACION.md, pero sobre la base de
pruebas: el dump, las dos semillas, las migraciones que van fuera del dump y los
permisos del usuario de la app. Cual es la base de pruebas lo decide
backend_web/tests/__init__.py: DATABASE_URL_PRUEBAS, o la de DATABASE_URL con
"_pruebas" al final del nombre.

Se corre como el superusuario de PostgreSQL, porque crear bases y extensiones lo
exige. Pide su contrasena sin mostrarla, salvo que ya este en PGPASSWORD.
Nunca toca la base de la aplicacion: se niega si los nombres coinciden.

Uso, desde la raiz del repositorio:
    python datos/scripts/prepara_base_pruebas.py
    python datos/scripts/prepara_base_pruebas.py --superusuario postgres --psql "C:/ruta/psql.exe"

Conviene volver a correrlo cuando cambien el dump o las semillas.
"""
import argparse
import ast
import getpass
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

PROTEGIDAS = {"postgres", "template0", "template1"}


def busca_psql(indicado):
    if indicado:
        return indicado
    encontrado = os.environ.get("PSQL") or shutil.which("psql")
    if encontrado:
        return encontrado
    candidatos = sorted(glob.glob("C:/Program Files/PostgreSQL/*/bin/psql.exe"),
                        key=lambda r: int(Path(r).parts[-3]) if Path(r).parts[-3].isdigit() else 0)
    if candidatos:
        return candidatos[-1]
    sys.exit("No encontre psql. Pasa su ruta con --psql o agregalo al PATH.")


def migraciones_fuera_del_dump():
    """FUERA_DEL_DUMP de verifica_migraciones.py, leido sin importarlo: ese
    script corre su verificacion completa al importarse."""
    fuente = (RAIZ / "datos" / "scripts" / "verifica_migraciones.py").read_text(encoding="utf-8")
    for nodo in ast.parse(fuente).body:
        if isinstance(nodo, ast.Assign) and getattr(nodo.targets[0], "id", "") == "FUERA_DEL_DUMP":
            return sorted(ast.literal_eval(nodo.value))
    sys.exit("No encontre FUERA_DEL_DUMP en datos/scripts/verifica_migraciones.py.")


def corre(psql, conexion, sql, entorno):
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as f:
        f.write(sql)
        archivo = f.name
    try:
        subprocess.run([psql, *conexion, "-v", "ON_ERROR_STOP=1", "-q", "-f", archivo],
                       env=entorno, check=True)
    except subprocess.CalledProcessError:
        sys.exit("psql se detuvo con un error (arriba). La base de pruebas puede haber "
                 "quedado a medias: corrige y vuelve a correr este script.")
    finally:
        os.unlink(archivo)


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--superusuario", default="postgres")
    parser.add_argument("--psql", default="")
    parser.add_argument("--si", action="store_true", help="no preguntar antes de borrar")
    args = parser.parse_args()

    import backend_web.tests as pruebas            # deriva y valida la URL de pruebas
    fuera_del_dump = migraciones_fuera_del_dump()

    if not pruebas.URL_APP:
        sys.exit("Falta DATABASE_URL en el .env (docs/INSTALACION.md, paso 4.2).")
    url = urlsplit(os.environ["DATABASE_URL"])
    base = url.path.lstrip("/")
    rol_app = unquote(url.username or "")
    if base in PROTEGIDAS or base == pruebas.BASE_DE_LA_APP:
        sys.exit(f"Me niego a borrar la base {base!r}.")
    if not rol_app:
        sys.exit("La URL de pruebas no trae usuario; no sabria a quien dar permisos.")

    host, puerto = url.hostname or "localhost", str(url.port or 5432)
    print(f"Base de pruebas: {base!r} en {host}:{puerto}. Permisos para: {rol_app!r}.")
    print(f"La base de la aplicacion ({pruebas.BASE_DE_LA_APP!r}) no se toca.")
    if not args.si and input(f"Se va a BORRAR y volver a crear {base!r}. ¿Continuar? [s/N] ") \
            .strip().lower() not in ("s", "si", "sí"):
        sys.exit("Cancelado; no se toco nada.")

    entorno = dict(os.environ, PGCLIENTENCODING="UTF8")
    if "PGPASSWORD" not in entorno:
        entorno["PGPASSWORD"] = getpass.getpass(f"Contraseña de {args.superusuario}: ")
    psql = busca_psql(args.psql)
    conexion = ["-h", host, "-p", puerto, "-U", args.superusuario]

    print("1/3 Creando la base...")
    corre(psql, conexion + ["-d", "postgres"],
          f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE);\nCREATE DATABASE "{base}";\n', entorno)

    datos = RAIZ / "datos" / "postgres"
    archivos = [datos / "dump_completo.sql", datos / "semillas" / "nl_municipios_completos.sql",
                datos / "semillas" / "demo_datos_nl.sql"]
    archivos += [datos / "migraciones" / nombre for nombre in fuera_del_dump]
    cargas = "".join(f"\\i '{a.as_posix()}'\n" for a in archivos)
    permisos = f'''
GRANT USAGE ON SCHEMA public TO "{rol_app}";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{rol_app}";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{rol_app}";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{rol_app}";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO "{rol_app}";
'''
    print(f"2/3 Cargando el esquema, las semillas y {len(fuera_del_dump)} migracion(es) aparte...")
    corre(psql, conexion + ["-d", base], cargas + permisos, entorno)

    print("3/3 Comprobando con el usuario de la app...")
    from backend_web.db import query
    fila = query("SELECT current_database() AS base, (SELECT count(*) FROM cases) AS casos, "
                 "(SELECT count(*) FROM regions) AS regiones", one=True)
    print(f"Lista: {fila['base']} con {fila['casos']:,} casos y {fila['regiones']} regiones. "
          "Ya puedes correr las pruebas.")


if __name__ == "__main__":
    main()
