"""
Los .sql que se cargan con psql declaran su codificacion.

En Windows, psql lee un archivo con la pagina de codigos de la consola
(WIN1252) si el archivo no dice otra cosa: "Anáhuac" llego a la base como
"AnÃ¡huac" en 9 municipios. Cada archivo que se carga por su cuenta empieza con
SET client_encoding = 'UTF8', en ASCII y antes de cualquier acento.

Las dos semillas salen de un generador: si alguien edita el archivo y no el
script, la siguiente regeneracion borra el cambio sin que nada falle. Ya le
ocurrio a un comentario de la semilla de demostracion.

Ejecutar:
    python -m unittest backend_web.tests.test_archivos_sql -v
"""
import os
import pathlib
import re
import subprocess
import sys
import unittest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
POSTGRES = RAIZ / "datos" / "postgres"
DECLARACION = b"SET client_encoding = 'UTF8';"
HASH_BCRYPT = re.compile(rb"\$2b\$12\$[./A-Za-z0-9]{53}")


def _cargados_con_psql():
    """El dump y las semillas: lo que el Paso 2 de docs/INSTALACION.md corre
    con psql -f."""
    return [POSTGRES / "dump_completo.sql", *sorted((POSTGRES / "semillas").glob("*.sql"))]


def _salida_del_generador(script):
    """Lo que escribe el generador, sin PYTHONUTF8 ni PYTHONIOENCODING: en
    Windows su salida redirigida saldria en cp1252 si no la fijara en UTF-8."""
    entorno = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    return subprocess.run([sys.executable, str(RAIZ / "datos" / "scripts" / script)],
                          capture_output=True, check=True, env=entorno).stdout


class CodificacionDeclaradaTests(unittest.TestCase):
    def test_cada_archivo_declara_utf8_antes_de_cualquier_acento(self):
        archivos = _cargados_con_psql()
        self.assertEqual(len(archivos), 3)
        for ruta in archivos:
            with self.subTest(archivo=ruta.name):
                datos = ruta.read_bytes()
                datos.decode("utf-8")
                antes, encontrada, _ = datos.partition(DECLARACION)
                self.assertTrue(encontrada, "no declara su codificacion")
                self.assertTrue(antes.isascii(), "hay acentos antes de la declaracion")
                self.assertTrue(antes.endswith(b"\n"), "la declaracion no va en su propia linea")

    def test_la_semilla_de_municipios_sale_igual_de_su_generador(self):
        """Byte por byte, tambien en Windows."""
        self.assertEqual(_salida_del_generador("build_regiones_sql.py"),
                         (POSTGRES / "semillas" / "nl_municipios_completos.sql").read_bytes())

    def test_la_semilla_de_demostracion_sale_igual_de_su_generador(self):
        """Byte por byte salvo los tres hashes de contrasena, que cambian en
        cada corrida por la sal. Que cada hash sea de su contrasena lo prueban
        los inicios de sesion de las pruebas de rutas, que entran con estas
        cuentas a la base de pruebas cargada con esta semilla."""
        salida, en_salida = HASH_BCRYPT.subn(b"<hash>", _salida_del_generador("gen_demo_data.py"))
        archivo, en_archivo = HASH_BCRYPT.subn(
            b"<hash>", (POSTGRES / "semillas" / "demo_datos_nl.sql").read_bytes())
        self.assertEqual((en_salida, en_archivo), (3, 3))
        self.assertEqual(salida, archivo)


if __name__ == "__main__":
    unittest.main()
