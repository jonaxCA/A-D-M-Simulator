"""
Exportaciones CSV: catalogo de enfermedades, resumen de situacion y zonas de
monitoreo. Las tres pasan por routes._csv, asi que estas pruebas fijan el
formato del archivo en un solo lugar: estado, encabezados HTTP, fila de
encabezados y que cada fila corresponda a lo que devuelve la consulta.

Leen el archivo con `utf-8-sig`, que acepta el CSV con o sin BOM.

Ejecutar:
    python -m unittest frontend_web.tests.test_exportaciones -v
"""
import csv
import io
import unittest
from decimal import Decimal

from frontend_web.tests.base import AppTestCase, requiere_base
from backend_web import queries
from backend_web.db import query
from backend_web.tests.base import escribe, id_de_usuario, token_de
from frontend_web.app.permisos import COOKIE_NAME
from frontend_web.app.routes import EXPORT_MAX_FILAS, _celda_csv

CODIGO_FORMULA = "ZZZ_NOMBRE_CON_FORMULA"


class CeldaCsvTests(unittest.TestCase):
    """Neutralizacion de formulas, sin base de datos."""

    def test_el_texto_que_empieza_como_formula_lleva_apostrofo(self):
        for peligroso in ("=1+1", "+1", "-1", "@SUMA(A1)", "\t=1", "\r=1",
                          '=HYPERLINK("http://x","clic")'):
            with self.subTest(valor=peligroso):
                self.assertEqual(_celda_csv(peligroso), "'" + peligroso)

    def test_los_numeros_no_se_tocan(self):
        for numero in (-12.5, -3, 0, 7, Decimal("-0.25")):
            with self.subTest(valor=numero):
                self.assertEqual(_celda_csv(numero), numero)

    def test_el_resto_queda_igual(self):
        for valor in ("Monterrey", "COVID-19", "Sí", "", None, "a=b", "'=ya escapado"):
            with self.subTest(valor=valor):
                self.assertEqual(_celda_csv(valor), valor)


@requiere_base
class ExportacionesCsvTests(AppTestCase):

    def _descarga(self, url):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, token_de("admin"))
            resp = client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        self.assertEqual(resp.headers["Content-Type"], "text/csv; charset=utf-8")
        filas = list(csv.reader(io.StringIO(resp.data.decode("utf-8-sig"))))
        return resp, filas[0], filas[1:]

    def test_catalogo_de_enfermedades(self):
        resp, encabezados, filas = self._descarga("/export/enfermedades.csv")
        self.assertEqual(resp.headers["Content-Disposition"],
                         "attachment; filename=catalogo_enfermedades.csv")
        self.assertEqual(encabezados, [
            "Código", "Enfermedad", "Estado", "Actividad", "Alta en catálogo",
            "Casos NL (total)", "Casos NL (30 días)",
            "Simulable", "Parámetros faltantes", "Parámetros supuestos"])
        esperadas = queries.get_enfermedades(pagina=1, por_pagina=EXPORT_MAX_FILAS)
        self.assertEqual([f[0] for f in filas],
                         [e["code"] for e in esperadas["enfermedades"]])

    def test_el_catalogo_respeta_los_filtros_de_la_pantalla(self):
        _, _, filas = self._descarga("/export/enfermedades.csv?estado=activa&q=a")
        esperadas = queries.get_enfermedades(pagina=1, por_pagina=EXPORT_MAX_FILAS,
                                             busqueda="a", estado="activa")
        self.assertEqual([f[0] for f in filas],
                         [e["code"] for e in esperadas["enfermedades"]])

    def test_resumen_de_situacion(self):
        resp, encabezados, filas = self._descarga("/export/resumen.csv")
        self.assertEqual(resp.headers["Content-Disposition"],
                         "attachment; filename=resumen_situacion.csv")
        self.assertEqual(encabezados, ["Enfermedad", "Estado", "Casos (7 dias)"])
        self.assertEqual(len(filas), len(queries.get_resumen_situacion(limit=20)))

    def test_zonas_de_monitoreo_con_el_periodo_en_el_encabezado(self):
        resp, encabezados, filas = self._descarga("/export/monitoreo.csv?dias=7")
        self.assertEqual(resp.headers["Content-Disposition"],
                         "attachment; filename=monitoreo_zonas.csv")
        self.assertEqual(encabezados, ["Zona", "Casos (7 días)", "Incidencia / 100k",
                                       "Variación 7d (%)", "Graves", "Estado"])
        zonas = queries.get_monitoreo_zonas(dias=7, orden="incidencia", pagina=1,
                                            por_pagina=EXPORT_MAX_FILAS)
        self.assertEqual([f[0] for f in filas], [z["zona"] for z in zonas["zonas"]])

    def test_cada_exportacion_deja_un_export_en_la_bitacora(self):
        admin = id_de_usuario("admin")
        for url, entidad in (("/export/enfermedades.csv", "catalogo_enfermedades"),
                             ("/export/resumen.csv", "resumen_situacion"),
                             ("/export/monitoreo.csv", "monitoreo_zonas")):
            with self.subTest(url=url):
                contar = lambda: query(
                    """SELECT count(*) AS n FROM audit_log
                       WHERE user_id = %s AND action = 'EXPORT'
                         AND entity_type = 'reports' AND entity_id = %s""",
                    (admin, entidad), one=True)["n"]
                antes = contar()
                self._descarga(url)
                self.assertEqual(contar() - antes, 1)

    def test_cada_exportacion_empieza_con_el_bom_de_utf8(self):
        """Sin BOM, Excel en Windows abre el CSV con la codificacion local y
        estropea los acentos de los encabezados."""
        for url in ("/export/enfermedades.csv", "/export/resumen.csv",
                    "/export/monitoreo.csv"):
            with self.subTest(url=url):
                resp, _, _ = self._descarga(url)
                self.assertTrue(resp.data.startswith(b"\xef\xbb\xbf"))
                # Una sola vez: el BOM no se cuela en la primera celda.
                self.assertFalse(resp.data[3:].startswith(b"\xef\xbb\xbf"))

    def test_un_nombre_con_formula_sale_como_texto(self):
        """Cualquier usuario autenticado puede dar de alta una enfermedad, y su
        nombre llega tal cual al export del catalogo."""
        escribe("""INSERT INTO diseases (code, name, default_params)
                   VALUES (%s, %s, '{}'::jsonb)""", (CODIGO_FORMULA, "=1+1"))
        self.addCleanup(escribe, "DELETE FROM diseases WHERE code = %s", (CODIGO_FORMULA,))
        _, _, filas = self._descarga("/export/enfermedades.csv")
        fila = next(f for f in filas if f[0] == CODIGO_FORMULA)
        self.assertEqual(fila[1], "'=1+1")

    def test_sin_sesion_no_se_descarga_nada(self):
        with self.app.test_client() as client:
            for url in ("/export/enfermedades.csv", "/export/resumen.csv",
                        "/export/monitoreo.csv"):
                resp = client.get(url, follow_redirects=False)
                self.assertEqual(resp.status_code, 302, url)
                self.assertIn("/login", resp.headers["Location"], url)
