import subprocess
import sys
import unittest
from pathlib import Path

from epidemia_comun.bd import query
from microservicios.pruebas_bd import tiene_base
from microservicios.regiones import datos

RAIZ = Path(__file__).resolve().parents[3]
MIGRACION = RAIZ / "datos/postgres/migraciones/043_jurisdicciones_y_censos.sql"


class MigracionGeneradaTests(unittest.TestCase):
    def test_la_043_sale_igual_de_su_script(self):
        salida = subprocess.run([sys.executable, str(RAIZ / "datos/scripts/build_censos_y_jurisdicciones.py")],
                                capture_output=True, check=True).stdout.decode("utf-8")
        self.assertEqual(salida, MIGRACION.read_text(encoding="utf-8"))


# Contra la base de pruebas, con la 043 y la semilla de los 51 municipios.
@unittest.skipUnless(tiene_base(), "Requiere la base de pruebas")
class RegionesBdTests(unittest.TestCase):
    def test_cada_clave_de_la_043_es_una_region(self):
        for tabla in ("health_area_municipalities", "census_population"):
            huerfanas = query("SELECT count(*) AS n FROM %s t LEFT JOIN regions r ON r.code = t.region_code "
                              "WHERE r.id IS NULL" % tabla, one=True)["n"]
            self.assertEqual(huerfanas, 0, tabla)

    def test_las_ocho_jurisdicciones_cubren_los_51_municipios(self):
        lista = datos.jurisdicciones()
        self.assertEqual([j["numero"] for j in lista], list(range(1, 9)))
        claves = [m["code"] for j in lista for m in j["municipios"]]
        self.assertEqual(len(set(claves)), 51)
        self.assertEqual([j["numero"] for j in datos.jurisdicciones_de("19039")], [1, 2, 3])
        self.assertTrue(all(j["parcial"] for j in datos.jurisdicciones_de("19039")))
        self.assertTrue(all(m["region_id"] for j in lista for m in j["municipios"]))

    def test_jerarquia_y_busqueda(self):
        estado = query("SELECT id FROM regions WHERE code = '19'", one=True)["id"]
        self.assertEqual(len(datos.hijos(estado)), 51)
        self.assertEqual(datos.region(estado)["nivel"], "estado")
        tipos = {(c["tipo"], c["code"]) for c in datos.busca("monterrey")}
        self.assertIn(("municipio", "19039"), tipos)
        self.assertIn("jurisdiccion", {c["tipo"] for c in datos.busca("MONTERREY")})
        self.assertEqual(datos.busca("nuevo leon")[0]["tipo"], "estado")
        self.assertEqual(datos.busca("ciénega")[0]["code"], "19012")
