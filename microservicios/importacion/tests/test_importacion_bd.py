import unittest
import uuid
from datetime import date

from epidemia_comun.bd import query
from microservicios.importacion import datos
from microservicios.pruebas_bd import contexto_de_prueba, escribe, tiene_base

SEMANAS = [(date(2020, 3, 1), 7), (date(2020, 3, 8), 38), (date(2020, 3, 15), 40), (date(2020, 3, 22), 18)]


def meta(code):
    return {"code": code, "name": "Serie de prueba", "metric": "casos_confirmados", "period": "semana",
            "source": "DGE", "license": "Datos abiertos", "url": None, "cutoff": date(2021, 10, 31)}


# Contra la base de pruebas. Cada prueba usa su propia clave y borra sus conjuntos al terminar
# (el rol de la app puede; svc_importacion no). La bitácora se queda: es de solo inserción.
@unittest.skipUnless(tiene_base(), "Requiere la base de pruebas")
class ImportacionBdTests(unittest.TestCase):
    def setUp(self):
        self.code = "PRUEBA_" + uuid.uuid4().hex[:12].upper()
        self.addCleanup(escribe, "DELETE FROM observed_datasets WHERE code = %s", (self.code,))
        self.user_id = query("SELECT min(id) AS id FROM users", one=True)["id"]
        self.ids = datos.ids_de("SARS_COV_2_ANCESTRAL", "19")

    def guarda(self, huella, puntos=SEMANAS):
        return datos.guardar(meta(self.code), self.ids, puntos, huella, self.user_id,
                             contexto=contexto_de_prueba(self.user_id))

    def test_la_061_trae_la_serie_de_d50(self):
        (fila,) = [c for c in datos.listar("SARS_COV_2_ANCESTRAL", "19") if c["code"] == "COVID19_NL_2020_SINTOMAS"]
        self.assertEqual((fila["version"], fila["period"], fila["cutoff_date"], fila["imported_by"]),
                         (1, "semana", date(2021, 10, 31), None))
        self.assertEqual(fila["sha256"], "64c90685b68a1164bfa093eeef8c8d33d35d93d9d8b8f3d2d6315359a18dab90")
        resumen = datos.get(fila["id"])["resumen"]
        self.assertEqual((resumen["puntos"], resumen["inicio"], resumen["fin"], resumen["total"]),
                         (22, date(2020, 3, 1), date(2020, 7, 26), 22259))

    def test_importa_versiona_y_no_duplica(self):
        primero, creado = self.guarda("a" * 64)
        self.assertTrue(creado)
        self.assertEqual((primero["version"], primero["disease"], primero["region"]), (1, "SARS_COV_2_ANCESTRAL", "19"))
        self.assertEqual(primero["resumen"]["total"], 103)
        mismo, creado = self.guarda("a" * 64)
        self.assertFalse(creado)
        self.assertEqual(mismo["id"], primero["id"])
        segundo, creado = self.guarda("b" * 64, SEMANAS[:3] + [(date(2020, 3, 22), 20)])
        self.assertTrue(creado)
        self.assertEqual(segundo["version"], 2)
        self.assertEqual(datos.puntos(segundo["id"])[-1], {"periodo_inicio": date(2020, 3, 22), "valor": 20})

    def test_deja_su_asiento_en_la_bitacora(self):
        fila, _ = self.guarda("c" * 64)
        asiento = query("""SELECT user_id, data_after FROM audit_log WHERE action = 'CREATE'
                           AND entity_type = 'observed_datasets' AND entity_id = %s""", (str(fila["id"]),), one=True)
        self.assertEqual(asiento["user_id"], self.user_id)
        self.assertEqual((asiento["data_after"]["code"], asiento["data_after"]["resumen"]["puntos"]), (self.code, 4))

    def test_el_alcance_filtra_la_lista(self):
        fila, _ = self.guarda("d" * 64)
        self.assertIn(fila["id"], [c["id"] for c in datos.listar(regiones={self.ids[1]})])
        self.assertNotIn(fila["id"], [c["id"] for c in datos.listar(regiones={-1})])
        self.assertEqual(datos.ids_de("NO_EXISTE", "99"), (None, None))
        self.assertIsNone(datos.get(-1))


if __name__ == "__main__":
    unittest.main()
