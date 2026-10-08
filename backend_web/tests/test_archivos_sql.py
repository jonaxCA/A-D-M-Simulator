"""
Los .sql que se cargan con psql declaran su codificacion.

En Windows, psql lee un archivo con la pagina de codigos de la consola
(WIN1252) si el archivo no dice otra cosa: "Anáhuac" llego a la base como
"AnÃ¡huac" en 9 municipios. Cada archivo que se carga por su cuenta empieza con
SET client_encoding = 'UTF8', en ASCII y antes de cualquier acento.

Ejecutar:
    python -m unittest backend_web.tests.test_archivos_sql -v
"""
import os
import pathlib
import subprocess
import sys
import unittest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
POSTGRES = RAIZ / "datos" / "postgres"
DECLARACION = b"SET client_encoding = 'UTF8';"


def _cargados_con_psql():
    """El dump y las semillas: lo que el Paso 2 de docs/INSTALACION.md corre
    con psql -f."""
    return [POSTGRES / "dump_completo.sql", *sorted((POSTGRES / "semillas").glob("*.sql"))]


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
        """Byte por byte, tambien en Windows, donde la salida redirigida del
        generador saldria en cp1252 si no la fijara en UTF-8."""
        entorno = {k: v for k, v in os.environ.items()
                   if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
        salida = subprocess.run(
            [sys.executable, str(RAIZ / "datos" / "scripts" / "build_regiones_sql.py")],
            capture_output=True, check=True, env=entorno).stdout
        self.assertEqual(salida, (POSTGRES / "semillas" / "nl_municipios_completos.sql").read_bytes())


if __name__ == "__main__":
    unittest.main()
