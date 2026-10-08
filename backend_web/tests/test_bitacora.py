"""
Una sola escritura a audit_log: backend_web.audit.log_audit.

Con `cur=` escribe en la transaccion del cambio que describe, y se confirma o
se deshace con el. Antes habia siete INSERT escritos a mano en queries.py,
mas _auditar() y log_audit(): nueve copias de la misma sentencia.

Ejecutar:
    python -m unittest backend_web.tests.test_bitacora -v
"""
import ast
import pathlib
import unittest
import uuid
from datetime import date
from decimal import Decimal

from backend_web.tests.base import contexto_de_prueba, requiere_base, usuario_con_rol
from backend_web.audit import _serializa, log_audit
from backend_web.db import a_jsonb, get_conn, query

RAIZ = pathlib.Path(__file__).resolve().parents[2]


class UnaSolaEscrituraTests(unittest.TestCase):

    def test_insert_into_audit_log_aparece_una_sola_vez(self):
        lugares = []
        for carpeta in ("backend_web", "frontend_web"):
            for ruta in sorted((RAIZ / carpeta).rglob("*.py")):
                if "tests" in ruta.parts or "__pycache__" in ruta.parts:
                    continue
                for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
                    if "INSERT INTO audit_log" in linea:
                        lugares.append(f"{ruta.relative_to(RAIZ).as_posix()}:{n}")
        self.assertEqual(len(lugares), 1, lugares)
        self.assertTrue(lugares[0].startswith("backend_web/audit.py:"), lugares)

    def test_en_queries_toda_auditoria_va_dentro_de_su_transaccion(self):
        """queries.py solo audita cambios que hace en la base: el registro tiene
        que ir con `cur=` para confirmarse junto con el cambio."""
        ruta = RAIZ / "backend_web" / "queries.py"
        sin_cur = []
        for n in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == "log_audit"
                    and not any(k.arg == "cur" for k in n.keywords)):
                sin_cur.append(f"queries.py:{n.lineno}")
        self.assertEqual(sin_cur, [])


class SerializacionTests(unittest.TestCase):
    """Lo que se guarda en las columnas jsonb, sin base."""

    def test_a_jsonb_escribe_fechas_y_decimales_como_texto_y_los_acentos_tal_cual(self):
        self.assertIsNone(a_jsonb(None))
        self.assertEqual(
            a_jsonb({"fecha": date(2026, 10, 8), "monto": Decimal("12.50"),
                     "municipio": "Anáhuac", "bandas": {"0-19": 3}}),
            '{"fecha": "2026-10-08", "monto": "12.50", "municipio": "Anáhuac", '
            '"bandas": {"0-19": 3}}')

    def test_la_bitacora_no_guarda_contrasenas(self):
        datos = {"id": 7, "username": "ana", "password_hash": "x", "password": "y",
                 "token_hash": "z"}
        self.assertEqual(_serializa(datos), '{"id": 7, "username": "ana"}')
        self.assertIsNone(_serializa(None))


@requiere_base
class AtomicidadTests(unittest.TestCase):

    def setUp(self):
        self.contexto = contexto_de_prueba(usuario_con_rol("ADMINISTRADOR"))
        self.marca = f"atomicidad-{uuid.uuid4().hex[:12]}"

    def _filas(self):
        return query("SELECT count(*) AS n FROM audit_log WHERE entity_id = %s",
                     (self.marca,), one=True)["n"]

    def test_con_cur_se_deshace_junto_con_la_transaccion(self):
        with get_conn() as conn:
            with conn.cursor() as cur:
                log_audit(self.contexto, "UPDATE", "regions", self.marca,
                          data_after={"prueba": "rollback"}, cur=cur)
            conn.rollback()
        self.assertEqual(self._filas(), 0)

    def test_con_cur_se_confirma_junto_con_la_transaccion(self):
        with get_conn() as conn:
            with conn.cursor() as cur:
                log_audit(self.contexto, "UPDATE", "regions", self.marca,
                          data_after={"prueba": "commit"}, cur=cur)
                self.assertEqual(self._filas(), 0, "otra conexion no la ve antes del commit")
            conn.commit()
        self.assertEqual(self._filas(), 1)

    def test_sin_cur_se_confirma_sola(self):
        log_audit(self.contexto, "EXPORT", "reports", self.marca)
        self.assertEqual(self._filas(), 1)

    def test_un_id_numerico_se_guarda_como_texto_y_sin_datos_queda_null(self):
        """_auditar() convertia el id con str(); log_audit lo hace por todos."""
        numero = uuid.uuid4().int % 10**15
        log_audit(self.contexto, "EXPORT", "reports", numero)
        fila = query("SELECT entity_id, data_before, data_after FROM audit_log "
                     "WHERE entity_id = %s", (str(numero),), one=True)
        self.assertEqual(fila["entity_id"], str(numero))
        self.assertIsNone(fila["data_before"])
        self.assertIsNone(fila["data_after"])
