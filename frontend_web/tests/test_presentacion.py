"""
Textos para mostrar (frontend_web/app/presentacion.py).

Ejecutar:
    python -m unittest frontend_web.tests.test_presentacion -v
"""
import re
import unittest
from datetime import date, datetime
from unittest.mock import patch

from frontend_web.tests.base import AppTestCase, ConUsuarioSimulado, requiere_base
from backend_web import queries
from backend_web.db import get_conn
from frontend_web.app.permisos import COOKIE_NAME
from frontend_web.app.presentacion import (actividad_etiqueta, describe_evento_auditoria,
                                           estado_catalogo, estado_usuario, estado_version,
                                           fecha_corta, fecha_hora, filas_bitacora,
                                           fuente_detalle, fuente_etiqueta,
                                           monitoreo_insights, opciones_accion,
                                           tendencia_etiqueta, texto_informativo,
                                           valor_parametro)

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

    def test_un_aumento_lleva_su_signo(self):
        self.assertIn("(+0.5%) se registra en García",
                      _geografica([{"zona": "García", "casos": 3, "variacion": 0.5}]))

    def test_sin_aumento_no_nombra_ninguna_zona(self):
        """Un "mayor cambio (+0.0%)" en una zona solo diria cual quedo primera
        en la lista."""
        for variaciones in ([0.0, 0.0], [0.0, -10.0], [-25.0, -3.0]):
            with self.subTest(variaciones=variaciones):
                zonas = [{"zona": f"Zona {i}", "casos": 3, "variacion": v}
                         for i, v in enumerate(variaciones)]
                self.assertEqual(_geografica(zonas),
                                 "Ninguna zona aumentó sus casos en los últimos 7 días.")

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


class EnfermedadesTextosTests(unittest.TestCase):
    def test_actividad_y_estado(self):
        self.assertEqual([actividad_etiqueta(c) for c in ("con_casos", "historico", "sin_casos")],
                         ["Con casos activos", "Solo histórico", "Sin casos"])
        self.assertEqual((estado_catalogo(True), estado_catalogo(False)), ("Activa", "Inactiva"))

    def test_valor_de_un_parametro_con_su_unidad(self):
        self.assertEqual(valor_parametro({"valor": 2.1, "unidad": "contagios por caso"}),
                         "2.1 contagios por caso")
        self.assertEqual(valor_parametro({"valor": 0.006, "unidad": "%", "porcentaje": True}),
                         "0.6 %")
        self.assertEqual(valor_parametro({"valor": 7, "unidad": ""}), "7")
        self.assertIsNone(valor_parametro({"valor": None, "unidad": "días"}))

    def test_informativo_por_edad_en_orden_de_edad(self):
        tabla = {"80+": 0.00526, "desconocido": "n/d", "5-14": 0.0001, "60-79": 0.00338,
                 "0-4": 3.11e-05}
        self.assertEqual(texto_informativo(tabla),
                         "0-4: 0.00311%, 5-14: 0.01%, 60-79: 0.338%, 80+: 0.526%, "
                         "desconocido: n/d")
        self.assertEqual(texto_informativo(0.35), "0.35")
        self.assertEqual(texto_informativo("texto libre"), "texto libre")


class EnfermedadesMuestraCadaFilaTests(ConUsuarioSimulado):
    """Pantalla y CSV con datos simulados, para cubrir lo que la base de
    demostracion no tiene: casos recientes y enfermedades inactivas."""

    STATS = {"registradas": 2, "altas_30d": 0, "activas": 1, "activas_pct": 50,
             "inactivas": 1, "detectadas_30d": 1}

    def _fila(self, code, nombre, activa, actividad, params):
        return {"id": len(code), "code": code, "nombre": nombre, "descripcion": "",
                "activa": activa, "actividad": actividad, "alta": date(2026, 9, 22),
                "casos_total": 5, "casos_30d": 1, "ultimo_caso": None,
                "parametros": queries.estado_parametros(params)}

    def _listado(self):
        alfa = self._fila("ALFA", "Alfa", True, "con_casos", {
            "r0": {"valor": 2.1, "fuente": "F", "supuesto": False},
            "letalidad": {"valor": 0.006, "fuente": None, "supuesto": True},
            "letalidad_por_edad": {"80+": 0.00526, "0-19": 3.11e-05}})
        beta = self._fila("BETA", "Beta", False, "sin_casos", {})
        return {"enfermedades": [alfa, beta], "total": 2, "pagina": 1, "por_pagina": 10,
                "paginas": 1, "desde": 1, "hasta": 2}

    @patch("frontend_web.app.routes.log_audit")
    @patch("frontend_web.app.routes.queries.get_enfermedades")
    @patch("frontend_web.app.routes.queries.get_enfermedades_stats")
    def test_pantalla_y_csv(self, mock_stats, mock_listado, _mock_bitacora):
        mock_stats.return_value = self.STATS
        mock_listado.return_value = self._listado()
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            html = client.get("/enfermedades").get_data(as_text=True)
            csv_texto = client.get("/export/enfermedades.csv").get_data(as_text=True)
        alfa, beta = html.split(">Alfa<")[1].split(">Beta<")
        self.assertIn('estado-dot"></span>Activa', alfa)
        self.assertIn('actividad-con_casos">Con casos activos<', alfa)
        self.assertIn("2.1 contagios por caso", alfa)
        self.assertIn("0.6 %", alfa)
        self.assertIn("<span>0-19: 0.00311%, 80+: 0.526%</span>", alfa)
        self.assertIn('estado-dot"></span>Inactiva', beta)
        self.assertIn('actividad-sin_casos">Sin casos<', beta)
        filas = csv_texto.splitlines()
        self.assertTrue(filas[1].startswith("ALFA,Alfa,Activa,Con casos activos,22 Sep 2026,"))
        self.assertTrue(filas[2].startswith("BETA,Beta,Inactiva,Sin casos,22 Sep 2026,"))


class TendenciaYVersionTests(unittest.TestCase):
    def test_tendencia(self):
        self.assertEqual([tendencia_etiqueta(c) for c in ("critico", "alerta", "estable")],
                         ["Critico", "Alerta", "Estable"])

    def test_estado_de_version(self):
        self.assertEqual([estado_version(s) for s in
                          ("borrador", "en_revision", "aprobado", "rechazado", None)],
                         ["Borrador", "En revisión", "Aprobado", "Rechazado", "—"])


class SemaforoDeTendenciaEnPantallaTests(ConUsuarioSimulado):
    SITUACION = [{"enfermedad": "Alfa", "estado": "critico", "incidencia": 1200},
                 {"enfermedad": "Beta", "estado": "alerta", "incidencia": 30},
                 {"enfermedad": "Gama", "estado": "estable", "incidencia": 2}]

    @patch("frontend_web.app.routes.queries.get_curva_epidemica", return_value=[])
    @patch("frontend_web.app.routes.queries.get_resumen_situacion")
    @patch("frontend_web.app.routes.queries.get_resumen_indicadores")
    def test_el_panorama_publico(self, mock_indicadores, mock_situacion, _curva):
        mock_indicadores.return_value = {"casos_activos": 0, "casos_pct": 0, "tasa_incidencia": 0,
                                         "tasa_pct": 0, "zonas_en_riesgo": 0,
                                         "simulaciones_activas": 0}
        mock_situacion.return_value = self.SITUACION
        with self.app.test_client() as client:
            html = client.get("/").get_data(as_text=True)
        for clave, texto in (("critico", "Critico"), ("alerta", "Alerta"), ("estable", "Estable")):
            self.assertIn(f'<span class="badge badge-{clave}">{texto}</span>', html)

    @patch("frontend_web.app.routes.log_audit")
    @patch("frontend_web.app.routes.queries.get_monitoreo_zonas")
    def test_el_csv_de_monitoreo(self, mock_zonas, _bitacora):
        mock_zonas.return_value = {"zonas": [
            {"zona": z, "casos": 1, "incidencia": 1.0, "variacion": 0.0, "graves": 0, "estado": e}
            for z, e in (("Alfa", "critico"), ("Beta", "alerta"), ("Gama", "estable"))]}
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            filas = client.get("/export/monitoreo.csv").get_data(as_text=True).splitlines()
        self.assertEqual([f.rsplit(",", 1)[1] for f in filas[1:]], ["Critico", "Alerta", "Estable"])

    @patch("frontend_web.app.routes.log_audit")
    @patch("frontend_web.app.routes.queries.get_resumen_situacion")
    def test_el_csv_del_resumen(self, mock_situacion, _bitacora):
        mock_situacion.return_value = self.SITUACION
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            filas = client.get("/export/resumen.csv").get_data(as_text=True).splitlines()
        self.assertEqual(filas[1:], ["Alfa,Critico,1200", "Beta,Alerta,30", "Gama,Estable,2"])

    @patch("frontend_web.app.routes.queries.get_escenarios")
    def test_el_estado_de_cada_version_en_escenarios(self, mock_escenarios):
        estados = ["borrador", "en_revision", "aprobado", "rechazado", None]
        mock_escenarios.return_value = [
            {"id": i, "name": f"Esc{i}", "description": None, "enfermedad": "X", "region": "Y",
             "version_number": None if s is None else 1, "version_status": s,
             "population_size": None, "por_edad": False, "autor": "Z", "horizon_days": 30,
             "age_unknown_policy": None, "population_age_unknown": 0}
            for i, s in enumerate(estados, 1)]
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            html = client.get("/escenarios").get_data(as_text=True)
        filas = [html.split(f">Esc{i}<", 1)[1].split("</tr>")[0] for i in range(1, 6)]
        for fila, texto in zip(filas, ["Borrador", "En revisión", "Aprobado", "Rechazado", "—"]):
            self.assertIn(f'">{texto}</span>', fila)


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
        # Cada distintivo de tendencia: su clase CSS es su etiqueta en minusculas.
        distintivos = re.findall(r'badge badge-(\w+)">(\w+)<', html)
        self.assertTrue(distintivos)
        self.assertEqual([c for c, _ in distintivos], [t.lower() for _, t in distintivos])


def _tarjeta_geografica(html):
    return re.search(r"<h3>Tendencia geográfica</h3>\s*<p>([^<]*)</p>", html).group(1)


@requiere_base
class MonitoreoTarjetaGeograficaTests(ConUsuarioSimulado):
    """La tarjeta geografica compara todas las zonas del ambito, en el orden fijo
    de la consulta: no cambia con la pagina, la busqueda ni el orden de la tabla."""

    # Santa Catarina y Zuazua empatan en el mayor aumento y quedan fuera de la
    # primera pagina: en el orden de la consulta gana Santa Catarina, en el
    # inverso Zuazua, y entre las 10 primeras, Monterrey.
    TODAS = [{"id": i, "zona": nombre, "casos": casos, "incidencia": 1.0, "variacion": var,
              "graves": 0, "estado": "estable"}
             for i, (nombre, casos, var) in enumerate([
                 ("Apodaca", 9, 10.0), ("Escobedo", 8, 8.0), ("García", 7, 5.0),
                 ("Guadalupe", 6, 0.0), ("Juárez", 5, -4.0), ("Monterrey", 4, 12.0),
                 ("Pesquería", 3, 1.0), ("Salinas Victoria", 3, 2.0), ("San Nicolás", 2, 3.0),
                 ("San Pedro", 2, 4.0), ("Santa Catarina", 1, 80.0), ("Zuazua", 1, 80.0)], 1)]

    def _zonas(self, busqueda=None, orden="casos", pagina=1, por_pagina=10, **_ambito):
        zonas = [z for z in self.TODAS if not busqueda or busqueda.lower() in z["zona"].lower()]
        if orden != "casos":
            zonas = zonas[::-1]
        return {"zonas": zonas[(pagina - 1) * por_pagina:pagina * por_pagina],
                "total": len(zonas), "pagina": pagina,
                "paginas": max(1, -(-len(zonas) // por_pagina)),
                "desde": (pagina - 1) * por_pagina + 1, "hasta": min(pagina * por_pagina, len(zonas))}

    def test_el_mismo_texto_en_cualquier_pagina_busqueda_u_orden(self):
        with patch("frontend_web.app.routes.queries.get_monitoreo_zonas", side_effect=self._zonas):
            with self.app.test_client() as client:
                client.set_cookie(COOKIE_NAME, self._token())
                for consulta in ("", "pagina=2", "q=Apo", "indicador=casos",
                                 "indicador=incidencia&pagina=2"):
                    with self.subTest(consulta=consulta):
                        html = client.get(f"/monitoreo?{consulta}").get_data(as_text=True)
                        self.assertEqual(_tarjeta_geografica(html),
                                         "El mayor cambio (+80.0%) se registra en Santa "
                                         "Catarina durante los últimos 7 días.")

    def test_con_los_datos_de_la_base(self):
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token())
            textos = {consulta: _tarjeta_geografica(
                          client.get(f"/monitoreo?dias=90&{consulta}").get_data(as_text=True))
                      for consulta in ("pagina=1", "pagina=2", "pagina=6", "indicador=casos",
                                       "indicador=incidencia&pagina=3", "q=San")}
        self.assertEqual(len(set(textos.values())), 1, textos)


class UsuariosTextosTests(unittest.TestCase):
    def test_estado_de_la_cuenta(self):
        self.assertEqual([estado_usuario(c) for c in ("activo", "pendiente", "inactivo")],
                         ["Activo", "Pendiente", "Inactivo"])

    def test_fecha_y_hora(self):
        momento = datetime(2026, 10, 6, 14, 5, 33)
        self.assertEqual(fecha_hora(momento), "2026-10-06 14:05")
        self.assertEqual(fecha_hora(momento, segundos=True), "2026-10-06 14:05:33")
        self.assertIsNone(fecha_hora(None))


class UsuariosMuestraCadaEstadoTests(ConUsuarioSimulado):
    """Los tres estados, una cuenta sin rol y la propia, con datos simulados:
    la base de demostracion no tiene cuentas sin rol."""

    def _usuario(self, uid, nombre, estado, roles, acceso):
        return {"id": uid, "nombre": nombre, "correo": f"{uid}@x.mx", "roles": roles,
                "estado": estado, "ultimo_acceso": acceso}

    @patch("frontend_web.app.routes.queries.get_roles_catalogo", return_value=[])
    @patch("frontend_web.app.routes.queries.get_usuarios_resumen")
    @patch("frontend_web.app.routes.queries.get_usuarios_lista")
    def test_cada_fila(self, mock_lista, mock_resumen, _roles):
        mock_resumen.return_value = {"total": 3, "activos": 1, "pendientes": 1, "inactivos": 1}
        mock_lista.return_value = [
            self._usuario(999, "Alfa", "activo", "Administrador",
                          datetime(2026, 10, 6, 14, 5, 33)),
            self._usuario(2, "Beta", "pendiente", None, None),
            self._usuario(3, "Gama", "inactivo", "Analista", datetime(2026, 9, 1, 8, 0)),
        ]
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token("ADMINISTRADOR"))
            html = client.get("/usuarios").get_data(as_text=True)
        alfa, resto = html.split(">Alfa<")[1].split(">Beta<")
        beta, gama = resto.split(">Gama<")

        self.assertIn("<td>Administrador</td>", alfa)
        self.assertIn('badge badge-activo">Activo<', alfa)
        self.assertIn("<td>2026-10-06 14:05</td>", alfa)
        self.assertIn('name="activar" value="0"', alfa)
        self.assertIn("disabled title=No-puedes-desactivarte-a-ti-mismo", alfa)

        self.assertIn("<td>Sin rol asignado</td>", beta)
        self.assertIn('badge badge-pendiente">Pendiente<', beta)
        self.assertIn("<td>Nunca</td>", beta)
        self.assertIn('name="activar" value="0"', beta)
        self.assertNotIn("No-puedes-desactivarte", beta)
        self.assertIn("Desactivar", beta)

        self.assertIn('badge badge-inactivo">Inactivo<', gama)
        self.assertIn("<td>2026-09-01 08:00</td>", gama)
        self.assertIn('name="activar" value="1"', gama)
        self.assertIn("Reactivar", gama)
        self.assertNotIn("Desactivar", gama)


class BitacoraTextosTests(unittest.TestCase):
    """Las etapas de RUN y de las versiones en describe_evento_auditoria las
    cubre backend_web/tests/test_auditoria.py."""

    def test_opciones_del_filtro_con_las_etapas_en_el_orden_de_la_corrida(self):
        valores = ["DELETE", "LOGIN", "OTRA", "RUN::abortado_antes_de_ejecutar",
                   "RUN::completado", "RUN::encolado", "RUN::zzz"]
        self.assertEqual(opciones_accion(valores), [
            {"valor": "DELETE", "etiqueta": "Baja de registro"},
            {"valor": "LOGIN", "etiqueta": "Inicio de sesion exitoso"},
            {"valor": "OTRA", "etiqueta": "OTRA"},
            {"valor": "RUN::encolado", "etiqueta": "Simulacion solicitada"},
            {"valor": "RUN::completado", "etiqueta": "Simulacion completada"},
            {"valor": "RUN::abortado_antes_de_ejecutar",
             "etiqueta": "Simulacion no iniciada (ya tomada por otro proceso)"},
            {"valor": "RUN::zzz", "etiqueta": "Ejecucion de simulacion (zzz)"},
        ])

    def test_cada_evento_con_su_descripcion_y_su_estado(self):
        corrida = {"id": 1, "fecha": None, "usuario": None, "modulo": "simulation_run",
                   "accion": "RUN", "entidad_id": "42", "datos": {"estado": "fallido",
                                                                 "error": "boom"}, "ip": None}
        version = {**corrida, "id": 2, "modulo": "scenario_versions", "accion": "UPDATE",
                   "entidad_id": "7", "datos": {"status": "aprobado", "version_number": 2}}
        self.assertEqual(filas_bitacora([corrida, version]), [
            {**corrida, "descripcion": "Simulacion fallida SIM-00042: boom", "estado": "Fallido"},
            {**version, "descripcion": "Version aprobada (v2)", "estado": "Correcto"}])

    def test_acceso_denegado_se_ve_fallido(self):
        self.assertEqual(describe_evento_auditoria("PERMISSION_DENIED", None, None, "users"),
                         ("Acceso denegado por permisos", "Fallido"))


class BitacoraMuestraCadaEventoTests(ConUsuarioSimulado):
    """Fecha, usuario, IP y estado de cada fila, y las opciones del filtro, con
    datos simulados."""

    def _evento(self, eid, accion, modulo, datos, usuario, ip):
        return {"id": eid, "fecha": datetime(2026, 10, 6, 14, 5, eid), "usuario": usuario,
                "modulo": modulo, "accion": accion, "entidad_id": str(eid), "datos": datos,
                "ip": ip}

    @patch("frontend_web.app.routes.queries.get_acciones_auditoria")
    @patch("frontend_web.app.routes.queries.get_modulos_auditoria", return_value=[])
    @patch("frontend_web.app.routes.queries.get_usuarios_para_filtro", return_value=[])
    @patch("frontend_web.app.routes.queries.get_auditoria_resumen")
    @patch("frontend_web.app.routes.queries.get_auditoria_lista")
    def test_cada_fila_y_el_filtro(self, mock_lista, mock_resumen, _usuarios, _modulos,
                                   mock_acciones):
        mock_resumen.return_value = {"eventos_totales": 2, "criticas": 0, "fallidos": 1,
                                     "activos_24h": 0}
        mock_lista.return_value = [
            self._evento(7, "RUN", "simulation_run", {"estado": "fallido", "error": "boom"},
                         "Ana", "10.9.8.7"),
            self._evento(9, "LOGIN_FAILED", "users", None, None, None),
        ]
        mock_acciones.return_value = ["LOGIN_FAILED", "RUN::fallido", "RUN::encolado"]
        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, self._token("ADMINISTRADOR"))
            html = client.get("/auditoria").get_data(as_text=True)
        corrida, login = html.split("<tbody>")[1].split("</tbody>")[0].split("</tr>")[:2]

        self.assertIn('<td class="suave">2026-10-06 14:05:07</td>', corrida)
        self.assertIn('<td class="fuerte">Ana</td>', corrida)
        self.assertIn("Simulacion fallida SIM-00007: boom", corrida)
        self.assertIn('<td class="suave">10.9.8.7</td>', corrida)
        self.assertIn('badge badge-fallido">Fallido<', corrida)

        self.assertIn('<td class="suave">2026-10-06 14:05:09</td>', login)
        self.assertIn('<td class="fuerte">Anonimo</td>', login)
        self.assertIn("Intento de inicio de sesion fallido", login)
        self.assertIn('<td class="suave">-</td>', login)

        opciones = re.findall(r'<option value="(RUN::\w+|LOGIN_FAILED)" >([^<]+)<', html)
        self.assertEqual(opciones, [("LOGIN_FAILED", "Intento de inicio de sesion fallido"),
                                    ("RUN::encolado", "Simulacion solicitada"),
                                    ("RUN::fallido", "Simulacion fallida")])


if __name__ == "__main__":
    unittest.main()
