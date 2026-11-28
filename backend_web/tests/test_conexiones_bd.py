"""Con la base de pruebas real: backend_web.db reutiliza la conexión (epidemia_comun/conexiones.py,
F4) y descarta lo que no se confirmó, como antes al cerrarla."""
import unittest

from backend_web.tests.base import requiere_base  # noqa: F401  (fija la base de pruebas)
from backend_web import db


class ConexionReutilizadaTests(unittest.TestCase):
    @requiere_base
    def test_la_misma_conexion_vuelve_sin_lo_que_no_se_confirmo(self):
        if db._prestada is None:
            self.skipTest("Sin epidemia_comun no hay préstamo de conexiones.")
        with db.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_backend_pid()")
                pid = cur.fetchone()[0]
                cur.execute("CREATE TEMP TABLE prueba_conexiones (x int)")
        with db.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_backend_pid(), to_regclass('pg_temp.prueba_conexiones')")
                pid_despues, tabla = cur.fetchone()
        self.assertEqual(pid, pid_despues)
        self.assertIsNone(tabla)


if __name__ == "__main__":
    unittest.main()
