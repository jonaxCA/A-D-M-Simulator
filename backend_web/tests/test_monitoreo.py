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


class SemaforosTests(unittest.TestCase):
    """Los dos semaforos regresan una clave, no el texto que se muestra."""

    def test_tendencia_y_sus_cortes(self):
        casos = [(-100.0, "estable"), (14.9, "estable"), (15, "alerta"), (49.9, "alerta"),
                 (50, "critico"), (300.0, "critico")]
        self.assertEqual([queries._clasifica_tendencia(p) for p, _ in casos],
                         [c for _, c in casos])

    def test_nivel_del_mapa_y_sus_cortes(self):
        casos = [(0, "baja"), (14.9, "baja"), (15, "moderada"), (30, "alta"), (45, "muy_alta"),
                 (59.9, "muy_alta"), (60, "critica"), (1e9, "critica")]
        self.assertEqual([queries._bucket(i) for i, _ in casos], [n for _, n in casos])


if __name__ == "__main__":
    unittest.main()
