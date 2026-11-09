"""
Lotes de vacuna de backend_web/vacunas.py, que escribe el microservicio vacunas.

Ejecutar:
    python -m unittest backend_web.tests.test_vacunas -v
"""
import unittest
import uuid
from datetime import date, timedelta

from backend_web import vacunas
from backend_web.db import query
from backend_web.tests.base import contexto_de_prueba, escribe, id_de_usuario, requiere_base


class ValidaLoteTests(unittest.TestCase):
    def test_uno_valido(self):
        limpios, errores = vacunas.valida_lote(
            {"lot_code": " FL3239-2026 ", "disease_id": "3", "doses_total": 500,
             "manufacturer": "Sanofi", "region_id": "", "expires_on": "2027-03-31"})
        self.assertEqual(errores, [])
        self.assertEqual(limpios, {"lot_code": "FL3239-2026", "manufacturer": "Sanofi", "disease_id": 3,
                                   "region_id": None, "doses_total": 500,
                                   "expires_on": date(2027, 3, 31)})

    def test_errores_de_cada_campo(self):
        _, errores = vacunas.valida_lote(
            {"lot_code": "con espacio", "disease_id": 0, "doses_total": 0, "region_id": "x",
             "expires_on": "31/03/2027", "manufacturer": 5, "qr": "crudo"})
        self.assertEqual(len(errores), 7)

    def test_dosis_no_puede_ser_booleano_ni_enorme(self):
        for dosis in (True, vacunas.DOSIS_MAX + 1, 2.5):
            _, errores = vacunas.valida_lote({"lot_code": "A1", "disease_id": 1, "doses_total": dosis})
            self.assertEqual(len(errores), 1, dosis)


@requiere_base
class LotesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.karla = id_de_usuario("karla.trevino")
        cls.referencias = query("SELECT (SELECT min(id) FROM diseases) AS disease_id, "
                                "(SELECT min(id) FROM regions) AS region_id", one=True)

    def setUp(self):
        self.lotes = []

    def tearDown(self):
        for lote_id in self.lotes:
            escribe("DELETE FROM vaccine_lots WHERE id = %s", (lote_id,))

    def _datos(self, **cambios):
        datos = {"lot_code": "PRUEBA-" + uuid.uuid4().hex[:12], "manufacturer": "Laboratorio X",
                 "disease_id": self.referencias["disease_id"],
                 "region_id": self.referencias["region_id"], "doses_total": 10,
                 "expires_on": date.today() + timedelta(days=90)}
        datos.update(cambios)
        return datos

    def _registra(self, datos):
        lote, creado, conflicto = vacunas.registrar_lote(datos, self.karla,
                                                         contexto=contexto_de_prueba(self.karla))
        if lote and creado:
            self.lotes.append(lote["id"])
        return lote, creado, conflicto

    def _aplica(self, lote_id, dosis):
        return vacunas.aplicar_dosis(lote_id, dosis, contexto=contexto_de_prueba(self.karla))

    def _bitacora(self, lote_id):
        return query("""SELECT action, data_before, data_after FROM audit_log
                        WHERE entity_type = 'vaccine_lots' AND entity_id = %s ORDER BY id""",
                     (str(lote_id),))

    def test_registrar_y_el_reintento_regresa_el_mismo(self):
        datos = self._datos()
        lote, creado, conflicto = self._registra(datos)
        self.assertTrue(creado)
        self.assertIsNone(conflicto)
        self.assertEqual((lote["lot_code"], lote["doses_used"], lote["doses_remaining"], lote["vencido"]),
                         (datos["lot_code"], 0, 10, False))
        self.assertIsNotNone(lote["disease_name"])
        self.assertEqual(lote["scanned_by"], self.karla)
        mismo, creado, _ = self._registra(datos)
        self.assertFalse(creado)
        self.assertEqual(mismo["id"], lote["id"])
        [evento] = self._bitacora(lote["id"])
        self.assertEqual(evento["data_after"]["doses_total"], 10)

    def test_el_mismo_codigo_con_otros_datos_es_conflicto(self):
        datos = self._datos()
        self._registra(datos)
        lote, _, conflicto = self._registra(dict(datos, doses_total=20))
        self.assertIsNone(lote)
        self.assertIn("otros datos", conflicto)

    def test_enfermedad_inexistente(self):
        _, _, conflicto = self._registra(self._datos(disease_id=32000))
        self.assertIn("no existen", conflicto)

    def test_aplicar_descuenta_y_nunca_pasa_del_total(self):
        lote, _, _ = self._registra(self._datos())
        aplicado, error = self._aplica(lote["id"], 3)
        self.assertIsNone(error)
        self.assertEqual((aplicado["doses_used"], aplicado["doses_remaining"]), (3, 7))
        evento = self._bitacora(lote["id"])[-1]
        self.assertEqual((evento["data_before"], evento["data_after"]),
                         ({"doses_used": 0}, {"doses_used": 3}))
        _, error = self._aplica(lote["id"], 8)
        self.assertEqual(error, "Al lote le quedan 7 dosis.")
        self.assertEqual(vacunas.get_lote(lote["id"])["doses_used"], 3)
        self.assertIsNone(self._aplica(lote["id"], 7)[1])
        self.assertEqual(vacunas.get_lote(lote["id"])["doses_remaining"], 0)

    def test_un_lote_caducado_se_registra_pero_no_se_aplica(self):
        ayer = date.today() - timedelta(days=2)
        lote, creado, _ = self._registra(self._datos(expires_on=ayer))
        self.assertTrue(creado)
        self.assertTrue(lote["vencido"])
        _, error = self._aplica(lote["id"], 1)
        self.assertIn("caducó", error)
        self.assertEqual(vacunas.get_lote(lote["id"])["doses_used"], 0)

    def test_sin_caducidad_nunca_vence(self):
        lote, _, _ = self._registra(self._datos(expires_on=None, region_id=None))
        self.assertFalse(lote["vencido"])
        self.assertIsNone(lote["region_name"])
        self.assertIsNone(self._aplica(lote["id"], 1)[1])

    def test_aplicar_a_uno_que_no_existe(self):
        self.assertEqual(self._aplica(-1, 1), (None, "No existe el lote."))

    def test_listar_con_filtros(self):
        lote, _, _ = self._registra(self._datos())
        self.assertEqual([l["id"] for l in vacunas.listar_lotes(lot_code=lote["lot_code"])], [lote["id"]])
        por_enfermedad = {l["id"] for l in vacunas.listar_lotes(disease_id=lote["disease_id"], limite=200)}
        self.assertIn(lote["id"], por_enfermedad)
        self.assertEqual(vacunas.listar_lotes(lot_code="NO-EXISTE-" + uuid.uuid4().hex), [])


if __name__ == "__main__":
    unittest.main()
