"""
Captura de casos por HTTP: un id que no esta en el catalogo del formulario se
rechaza con un mensaje, no con un 500 al insertar.

Ejecutar:
    python -m unittest frontend_web.tests.test_reportes_rutas -v
"""
import unittest

from frontend_web.tests.base import AppTestCase, requiere_base
from backend_web.db import get_conn, query


@requiere_base
class CapturaFueraDeCatalogoTests(AppTestCase):
    def setUp(self):
        self.municipio = query("SELECT id FROM regions WHERE code = '19039'", one=True)["id"]
        self.estado = query("SELECT id FROM regions WHERE level = 'estado' LIMIT 1",
                            one=True)["id"]
        self.enfermedad = query("SELECT min(id) AS v FROM diseases WHERE is_active",
                                one=True)["v"]
        self.ultimo = query("SELECT coalesce(max(id), 0) AS v FROM cases", one=True)["v"]
        self.addCleanup(self._borra_lo_capturado)

    def _borra_lo_capturado(self):
        """Solo actua si una prueba falla y el caso se llego a guardar."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cases WHERE id > %s", (self.ultimo,))
            conn.commit()

    def _envia(self, **cambios):
        datos = {"disease_id": str(self.enfermedad), "region_id": str(self.municipio),
                 "report_date": "2026-09-02"}
        datos.update(cambios)
        with self.app.test_client() as client:
            self._login(client, "admin", "Admin2026!")
            resp = client.post("/reportes/nuevo", data=datos)
        self.assertEqual(query("SELECT coalesce(max(id), 0) AS v FROM cases", one=True)["v"],
                         self.ultimo, "no debio guardarse ningun caso")
        return resp.status_code, resp.get_data(as_text=True)

    def test_una_enfermedad_que_no_cabe_en_la_columna_da_400(self):
        """diseases.id es smallint: 2147483648 pasaba la validacion y el INSERT
        respondia 500."""
        status, html = self._envia(disease_id="2147483648")
        self.assertEqual(status, 400)
        self.assertIn("Esa enfermedad no está activa en el catálogo.", html)

    def test_el_estado_no_es_un_municipio(self):
        """El selector solo ofrece municipios, pero la llave foranea acepta el
        estado: un POST armado a mano capturaba casos a nivel estatal."""
        status, html = self._envia(region_id=str(self.estado))
        self.assertEqual(status, 400)
        self.assertIn("Ese municipio no está en el catálogo de Nuevo León.", html)


if __name__ == "__main__":
    unittest.main()
