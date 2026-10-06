"""
Textos para mostrar (frontend_web/app/presentacion.py).

Ejecutar:
    python -m unittest frontend_web.tests.test_presentacion -v
"""
import unittest
from datetime import date, datetime
from unittest.mock import patch

from frontend_web.tests.base import AppTestCase, ConUsuarioSimulado, requiere_base
from backend_web.db import get_conn
from frontend_web.app.permisos import COOKIE_NAME
from frontend_web.app.presentacion import (fecha_corta, fuente_detalle, fuente_etiqueta,
                                           monitoreo_insights)

TOTALES = {"casos_pct": 15.2}


def _geografica(zonas):
    return monitoreo_insights(zonas, [], TOTALES, 30)["geografica"]


class MonitoreoInsightsTests(unittest.TestCase):
    def test_la_zona_con_mayor_cambio_entre_las_que_tienen_casos(self):
        zonas = [{"zona": "Apodaca", "casos": 5, "variacion": 12.5},
                 {"zona": "Monterrey", "casos": 9, "variacion": 40.0},
                 {"zona": "Juárez", "casos": 0, "variacion": 300.0}]
        self.assertEqual(_geografica(zonas), "El mayor cambio (+40.0%) se registra en "
                                             "Monterrey durante los últimos 7 días.")

    def test_el_signo_del_cambio(self):
        self.assertIn("(-25.0%)", _geografica([{"zona": "García", "casos": 3,
                                                "variacion": -25.0}]))
        self.assertIn("(+0.0%)", _geografica([{"zona": "García", "casos": 3,
                                               "variacion": 0.0}]))

    def test_en_empate_gana_la_primera_zona(self):
        zonas = [{"zona": "Apodaca", "casos": 1, "variacion": 10.0},
                 {"zona": "Escobedo", "casos": 1, "variacion": 10.0}]
        self.assertIn("en Apodaca durante", _geografica(zonas))

    def test_sin_casos_en_ninguna_zona(self):
        self.assertEqual(_geografica([{"zona": "Apodaca", "casos": 0, "variacion": 0.0}]),
                         "Todavía no hay casos capturados en el periodo seleccionado.")

    def test_la_incidencia_general_sube_baja_o_se_mantiene(self):
        casos = [(15.2, 30, "La incidencia general aumentó un 15.2% respecto al periodo "
                            "anterior de 30 días."),
                 (-7.5, 7, "La incidencia general disminuyó un 7.5% respecto al periodo "
                           "anterior de 7 días."),
                 (0.0, 90, "La incidencia general se mantuvo un 0.0% respecto al periodo "
                           "anterior de 90 días.")]
        for pct, dias, esperado in casos:
            with self.subTest(pct=pct):
                self.assertEqual(monitoreo_insights([], [], {"casos_pct": pct}, dias)["global"],
                                 esperado)

    def test_el_grupo_de_edad_con_mas_casos(self):
        edades = [{"grupo": "0-19", "casos": 10}, {"grupo": "20-39", "casos": 1234},
                  {"grupo": "60+", "casos": 0}]
        self.assertEqual(monitoreo_insights([], edades, TOTALES, 30)["critica"],
                         "El grupo con más casos es el de 20-39 años (1,234 casos).")
        self.assertEqual(monitoreo_insights([], [{"grupo": "0-19", "casos": 0}],
                                            TOTALES, 30)["critica"],
                         "Sin casos con edad registrada en el periodo.")


class FechaCortaTests(unittest.TestCase):
    def test_los_doce_meses_en_espanol_sin_depender_del_locale(self):
        meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                 "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        for numero, mes in enumerate(meses, 1):
            with self.subTest(mes=mes):
                self.assertEqual(fecha_corta(date(2026, numero, 5)), f"05 {mes} 2026")

    def test_acepta_fecha_y_hora_y_respeta_el_vacio(self):
        self.assertEqual(fecha_corta(datetime(2026, 10, 12, 23, 59)), "12 Oct 2026")
        self.assertIsNone(fecha_corta(None))


class FuenteDePoblacionTests(unittest.TestCase):
    def test_censal_y_derivado_muestran_su_fuente(self):
        censal = {"tipo": "censal", "fuente": "INEGI, Censo 2020"}
        self.assertEqual(fuente_etiqueta(censal), "INEGI, Censo 2020")
        self.assertIsNone(fuente_detalle(censal))
        derivado = {"tipo": "derivado", "fuente": "Grupos 60-79 y 80+ del Censo 2020"}
        self.assertEqual(fuente_etiqueta(derivado), "Grupos 60-79 y 80+ del Censo 2020")
        self.assertEqual(fuente_detalle(derivado),
                         "Se calcula a partir de las bandas de edad; no se captura aparte.")

    def test_el_agregado_del_estado(self):
        self.assertEqual(fuente_etiqueta({"tipo": "agregado"}), "Suma de los 51 municipios")
        self.assertIsNone(fuente_detalle({"tipo": "agregado"}))

    def test_una_correccion_manual_no_se_atribuye_a_inegi(self):
        manual = {"tipo": "manual", "motivo": "Conteo municipal 2025",
                  "fecha": datetime(2026, 10, 6, 9, 30), "por": "Ana Pérez"}
        self.assertEqual(fuente_etiqueta(manual), "Corrección manual")
        self.assertEqual(fuente_detalle(manual),
                         "Corregido por Ana Pérez el 06 Oct 2026: Conteo municipal 2025")
        self.assertIn("Corregido por un administrador el",
                      fuente_detalle({**manual, "por": None}))


class FiltrosDePlantillaTests(AppTestCase):
    def test_las_plantillas_tienen_los_filtros_de_presentacion(self):
        plantilla = self.app.jinja_env.from_string(
            "{{ f | fecha_corta }}|{{ fuente | fuente_etiqueta }}|{{ fuente | fuente_detalle }}")
        self.assertEqual(
            plantilla.render(f=date(2026, 9, 3),
                             fuente={"tipo": "derivado", "fuente": "Censo"}),
            "03 Sep 2026|Censo|Se calcula a partir de las bandas de edad; no se captura aparte.")


class RegionesMuestraCadaFuenteTests(ConUsuarioSimulado):
    """Cada distintivo en su fila, con datos simulados: no depende de que la
    base tenga (o no) correcciones de otras pruebas."""

    def _municipio(self, mid, nombre, fuente, fuente_60):
        return {"id": mid, "code": f"19{mid:03d}", "nombre": nombre, "poblacion": 1000,
                "poblacion_60": 100, "fuente_poblacion": fuente, "fuente_poblacion_60": fuente_60}

    @patch("frontend_web.app.routes.queries.get_estado_nl")
    @patch("frontend_web.app.routes.queries.get_regiones_catalogo")
    def test_cada_fila_muestra_su_fuente(self, mock_catalogo, mock_estado):
        censal = {"tipo": "censal", "fuente": "INEGI, Censo 2020"}
        derivado = {"tipo": "derivado", "fuente": "Grupos 60-79 y 80+ del Censo 2020"}
        manual = {"tipo": "manual", "motivo": "Conteo 2025", "fecha": date(2026, 10, 6),
                  "por": "Ana"}
        mock_catalogo.return_value = {
            "municipios": [self._municipio(1, "Alfa", manual, derivado),
                           self._municipio(2, "Beta", censal, manual)],
            "total": 2, "busqueda": "", "orden": "nombre", "direccion": "asc"}
        mock_estado.return_value = {"id": 9, "code": "19", "nombre": "Nuevo León",
                                    "poblacion": 2000, "poblacion_60": 200,
                                    "fuente_poblacion": {"tipo": "agregado"},
                                    "fuente_poblacion_60": derivado}
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            html = client.get("/regiones").get_data(as_text=True)
        alfa, beta = html.split(">Alfa<")[1].split(">Beta<")
        detalle_manual = 'title="Corregido por Ana el 06 Oct 2026: Conteo 2025"'
        explicacion = 'title="Se calcula a partir de las bandas de edad; no se captura aparte."'
        self.assertIn(f"{detalle_manual}>Población: Corrección manual<", alfa)
        self.assertIn(f"{explicacion}>60+: Grupos 60-79 y 80+ del Censo 2020<", alfa)
        self.assertIn('title="">Población: INEGI, Censo 2020<', beta)
        self.assertIn(f"{detalle_manual}>60+: Corrección manual<", beta)
        self.assertIn("Suma de los 51 municipios", html)


@requiere_base
class EnfermedadesMuestraFechasTests(AppTestCase):
    """La fecha de alta y el ultimo reporte llegan crudos de la base y se
    formatean en la plantilla y en el CSV."""

    CODIGO = "ZZZ_FECHAS_PRUEBA"
    MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    def setUp(self):
        self._borra()
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO diseases (code, name, default_params)
                               VALUES (%s, 'ZZZ Enfermedad de fechas', '{}'::jsonb)
                               RETURNING created_at""", (self.CODIGO,))
                alta = cur.fetchone()[0]
            conn.commit()
        self.addCleanup(self._borra)
        self.alta = f"{alta.day:02d} {self.MESES[alta.month - 1]} {alta.year}"

    def _borra(self):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM diseases WHERE code = %s", (self.CODIGO,))
            conn.commit()

    def test_pantalla_y_csv(self):
        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")
            html = client.get(f"/enfermedades?q={self.CODIGO}").get_data(as_text=True)
            csv_texto = client.get(f"/export/enfermedades.csv?q={self.CODIGO}").get_data(
                as_text=True)
        self.assertIn(f'<td class="celda-fecha">{self.alta}</td>', html)
        self.assertIn("<span>Último reporte</span><span>Sin casos registrados</span>", html)
        fila = next(f for f in csv_texto.splitlines() if f.startswith(self.CODIGO))
        self.assertIn(f",{self.alta},", fila)


@requiere_base
class MonitoreoMuestraLosTextosTests(AppTestCase):
    @patch("frontend_web.app.routes.presentacion.monitoreo_insights")
    def test_la_pantalla_muestra_lo_que_arma_presentacion(self, mock_insights):
        mock_insights.return_value = {"geografica": "TEXTO-GEO", "global": "TEXTO-GLOBAL",
                                      "critica": "TEXTO-CRITICA"}
        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")
            resp = client.get("/monitoreo?dias=7")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        for texto in ("TEXTO-GEO", "TEXTO-GLOBAL", "TEXTO-CRITICA"):
            self.assertIn(texto, html)
        mock_insights.assert_called_once()
        zonas, edades, totales, dias = mock_insights.call_args.args
        self.assertTrue(zonas)
        self.assertTrue(all({"zona", "casos", "variacion"} <= set(z) for z in zonas))
        self.assertTrue(all({"grupo", "casos"} <= set(e) for e in edades))
        self.assertIn("casos_pct", totales)
        self.assertEqual(dias, 7)


if __name__ == "__main__":
    unittest.main()
