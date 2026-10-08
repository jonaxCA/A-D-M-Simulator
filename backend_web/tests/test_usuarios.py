"""
Consultas de la pantalla de Usuarios que no necesitan la base: se simula lo
que regresa el SQL.

Ejecutar:
    python -m unittest backend_web.tests.test_usuarios -v
"""
import unittest
from datetime import datetime
from unittest.mock import patch

from backend_web import queries


class UsuariosDatosCrudosTests(unittest.TestCase):
    """get_usuarios_lista regresa claves y datos; el texto que ve la persona
    lo arma frontend_web/app/presentacion.py. Una API recibe lo mismo."""

    ACCESO = datetime(2026, 10, 6, 14, 5, 33)

    def _fila(self, uid, activo, acceso, roles):
        return {"id": uid, "full_name": f"Persona {uid}", "email": f"p{uid}@x.mx",
                "is_active": activo, "last_login_at": acceso, "roles": roles}

    def _lista(self, filas):
        with patch.object(queries, "query", return_value=filas):
            return queries.get_usuarios_lista()

    def test_el_estado_es_una_clave(self):
        lista = self._lista([self._fila(1, True, self.ACCESO, "Analista"),
                             self._fila(2, True, None, "Analista"),
                             self._fila(3, False, self.ACCESO, "Analista"),
                             self._fila(4, False, None, "Analista")])
        self.assertEqual([u["estado"] for u in lista],
                         ["activo", "pendiente", "inactivo", "inactivo"])

    def test_sin_rol_y_sin_acceso_viajan_vacios(self):
        usuario, = self._lista([self._fila(2, True, None, None)])
        self.assertEqual(usuario, {"id": 2, "nombre": "Persona 2", "correo": "p2@x.mx",
                                   "roles": None, "estado": "pendiente",
                                   "ultimo_acceso": None})

    def test_el_ultimo_acceso_es_la_fecha(self):
        usuario, = self._lista([self._fila(1, True, self.ACCESO, "Analista, Epidemiologo")])
        self.assertEqual(usuario["ultimo_acceso"], self.ACCESO)
        self.assertEqual(usuario["roles"], "Analista, Epidemiologo")


if __name__ == "__main__":
    unittest.main()
