"""
Consultas de la pantalla de Monitoreo que no necesitan la base: se simula
lo que regresa el SQL.

Ejecutar:
    python -m unittest backend_web.tests.test_monitoreo -v
"""
import unittest
from unittest.mock import patch

from backend_web import queries


class SexoMonitoreoTests(unittest.TestCase):
    def _sexo(self, filas):
        with patch.object(queries, "query", return_value=filas):
            return queries.get_monitoreo_sexo()

    def test_las_etiquetas_salen_del_catalogo_de_la_captura(self):
        """La grafica y el formulario de captura usan el mismo catalogo
        (SEXOS): una etiqueta corregida en uno no puede quedar vieja en el
        otro."""
        filas = [{"sex": clave, "casos": 1} for clave in queries.SEXOS]
        self.assertEqual([s["label"] for s in self._sexo(filas)],
                         list(queries.SEXOS.values()))

    def test_sin_sexo_o_fuera_de_catalogo(self):
        filas = [{"sex": None, "casos": 2}, {"sex": "X", "casos": 1}]
        self.assertEqual([s["label"] for s in self._sexo(filas)],
                         ["No especificado", "No especificado"])

    def test_porcentajes_y_orden_de_la_consulta(self):
        filas = [{"sex": "F", "casos": 6}, {"sex": "M", "casos": 3}, {"sex": "O", "casos": 1}]
        self.assertEqual(self._sexo(filas), [
            {"label": "Femenino", "casos": 6, "pct": 60.0},
            {"label": "Masculino", "casos": 3, "pct": 30.0},
            {"label": "Otro", "casos": 1, "pct": 10.0},
        ])

    def test_sin_casos(self):
        self.assertEqual(self._sexo([]), [])


if __name__ == "__main__":
    unittest.main()
