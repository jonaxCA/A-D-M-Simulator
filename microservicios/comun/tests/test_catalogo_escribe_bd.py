import re
import unittest
from pathlib import Path

from epidemia_comun.bd import query
from microservicios.pruebas_bd import tiene_base

CATALOGO = Path(__file__).resolve().parents[3] / "docs" / "arquitectura" / "microservicios.md"
SERVICIO = re.compile(r"`([a-z-]+)`")
TABLA = re.compile(r"`([a-z_]+)(?:\.[a-z_0-9]+)?`")

# De pg_class y pg_attribute y no de information_schema, que solo muestra los permisos que ve el
# usuario conectado, y las pruebas no entran como superusuario.
ESCRITURAS = """
SELECT r.rolname AS rol, c.relname AS tabla
  FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a JOIN pg_roles r ON r.oid = a.grantee
 WHERE c.relnamespace = 'public'::regnamespace AND a.privilege_type IN ('INSERT', 'UPDATE', 'DELETE')
UNION
SELECT r.rolname, c.relname
  FROM pg_attribute t JOIN pg_class c ON c.oid = t.attrelid
       CROSS JOIN LATERAL aclexplode(t.attacl) a JOIN pg_roles r ON r.oid = a.grantee
 WHERE c.relnamespace = 'public'::regnamespace AND a.privilege_type IN ('INSERT', 'UPDATE')
"""


def _celdas(linea):
    return [c.strip() for c in linea.strip().strip("|").split("|")]


def escribe_segun_el_catalogo():
    # {servicio: celda «Escribe»} de las tablas de servicios del catálogo.
    filas, columna = {}, None
    for linea in CATALOGO.read_text(encoding="utf-8").splitlines():
        if not linea.startswith("|"):
            columna = None
            continue
        celdas = _celdas(linea)
        if celdas[0] == "#" and "Escribe" in celdas:
            columna = celdas.index("Escribe")
        elif columna is not None and celdas[0].isdigit():
            filas[SERVICIO.match(celdas[1]).group(1)] = celdas[columna]
    return filas


# La columna «Escribe» de microservicios.md contra los permisos de cada rol svc_* (RNF-K16).
# audit_log no cuenta: es de todos, solo para insertar.
@unittest.skipUnless(tiene_base(), "Requiere la base de pruebas")
class EscribeTests(unittest.TestCase):
    def test_cada_servicio_escribe_lo_que_dice_el_catalogo(self):
        tablas = {f["tablename"] for f in query("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
        permisos = {}
        for f in query(ESCRITURAS):
            if f["rol"].startswith("svc_") and f["tabla"] != "audit_log":
                permisos.setdefault(f["rol"], set()).add(f["tabla"])

        catalogo = escribe_segun_el_catalogo()
        self.assertGreaterEqual(len(catalogo), 29)
        for servicio, celda in catalogo.items():
            with self.subTest(servicio=servicio):
                dice = set(TABLA.findall(celda)) & tablas - {"audit_log"}
                puede = permisos.pop("svc_" + servicio.replace("-", "_"), set())
                self.assertEqual(dice, puede, "sobra en el catálogo: %s; falta en el catálogo: %s"
                                 % (sorted(dice - puede), sorted(puede - dice)))
        self.assertEqual(permisos, {}, "roles que escriben y no están en el catálogo")


if __name__ == "__main__":
    unittest.main()
