import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
DUMP = RAIZ / "datos" / "postgres" / "dump_completo.sql"
MATRICES = RAIZ / "docs" / "arquitectura" / "matrices_v3.md"
COLUMNAS = 7


def tablas_del_esquema():
    sql = DUMP.read_text(encoding="utf-8")
    creadas = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql))
    return creadas - set(re.findall(r"DROP TABLE IF EXISTS (\w+)", sql))


def filas_del_inventario():
    texto = MATRICES.read_text(encoding="utf-8")
    seccion = texto.split("### 2. Inventario de datos", 1)[1].split("\n### ", 1)[0]
    filas = [[c.strip() for c in linea.strip().strip("|").split("|")]
             for linea in seccion.splitlines() if linea.startswith("|")]
    return [f for f in filas if f[0] != "Dato" and not set(f[0]) <= set("-")]


# RNF-K07 y D52: cada tabla del esquema tiene su fila en matrices_v3.md §2, con su vida y su volumen.
class InventarioTests(unittest.TestCase):
    def test_cada_tabla_tiene_su_fila(self):
        nombradas = {t for f in filas_del_inventario() for t in re.findall(r"`(\w+)`", f[0])}
        self.assertEqual(tablas_del_esquema() - nombradas, set())

    def test_cada_fila_dice_su_vida_y_su_volumen(self):
        for fila in filas_del_inventario():
            with self.subTest(dato=fila[0]):
                self.assertEqual(len(fila), COLUMNAS)
                self.assertTrue(fila[5] and fila[6])
                self.assertNotIn("Por definir", " ".join(fila))


if __name__ == "__main__":
    unittest.main()
