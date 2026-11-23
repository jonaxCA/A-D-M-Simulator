"""Aceptación C3: la web abre fotos y reportes con URL firmada y recibe el reporte de una comparación.

Se intercepta la petición HTTP que sale de la web hacia evidencias (D36): ni la base ni el bucket
corren aquí.
"""
import hashlib
import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from backend_web import archivos, servicios
from frontend_web.app.permisos import COOKIE_NAME
from frontend_web.tests.base import ConUsuarioSimulado

URL_FIRMADA = ("https://storage.googleapis.com/epidemia-archivos/evidencias/418/a1.jpg"
               "?X-Goog-Expires=900&X-Goog-Signature=5d1c")
PDF = b"%PDF-1.7\n" + b"reporte de la comparacion" * 40
REPORTE = {"id": 3, "run_ids": [12, 15], "title": "Cierre contra cuarentena",
           "mime_type": "application/pdf", "size_bytes": len(PDF),
           "sha256": hashlib.sha256(PDF).hexdigest(), "privacy": "privado", "uploaded_by": 5,
           "uploaded_at": "2026-11-01T17:45:00+00:00"}
EVIDENCIAS = {"case_id": 418, "total": 2, "evidencias": [
    {"id": 12, "case_id": 418, "mime_type": "image/jpeg", "size_bytes": 1843200,
     "uploaded_at": "2026-11-01T17:42:00+00:00"},
    {"id": 13, "case_id": 418, "mime_type": "application/pdf", "size_bytes": 254310,
     "uploaded_at": "2026-11-01T17:45:00+00:00"}]}


class Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class ConEvidencias(ConUsuarioSimulado):
    puente_servicios = False

    def setUp(self):
        super().setUp()
        self.peticiones = []
        self.estado = {}
        self.caido = False

        def urlopen(peticion, timeout):
            self.peticiones.append(peticion)
            if self.caido:
                raise urllib.error.URLError("evidencias apagado")
            ruta = peticion.full_url.split("?")[0]
            error = self.estado.get(ruta)
            if error:
                raise urllib.error.HTTPError(peticion.full_url, error, "error", {},
                                             io.BytesIO(json.dumps(
                                                 {"codigo": "X", "detail": "No."}).encode()))
            if ruta.endswith("/url"):
                cuerpo = {"id": 1, "url": URL_FIRMADA, "minutes": 15}
            elif ruta.endswith("/attachments"):
                cuerpo = EVIDENCIAS
            elif peticion.get_method() == "POST":
                cuerpo = REPORTE
            else:
                cuerpo = {"total": 1, "reportes": [REPORTE]}
            return Respuesta(json.dumps(cuerpo).encode("utf-8"))
        simulado = patch("backend_web.servicios.urllib.request.urlopen", side_effect=urlopen)
        simulado.start()
        self.addCleanup(simulado.stop)

    def _cliente(self, rol):
        cliente = self.app.test_client()
        cliente.set_cookie(COOKIE_NAME, self._token(rol))
        return cliente

    def _evidencias(self):
        # La campana de avisos y el 403 también llaman a otros servicios.
        base = servicios.url_base("evidencias")
        return [p for p in self.peticiones if p.full_url.startswith(base)]

    def _rutas(self):
        return [(p.get_method(), p.full_url.split("?")[0].split("/api/v1")[-1])
                for p in self._evidencias()]


class FotoDeUnCaso(ConEvidencias):
    @patch("backend_web.servicios.historial_caso", return_value=[])
    @patch("backend_web.servicios.caso")
    def test_el_caso_muestra_su_foto_sin_dejar_escrita_la_url_firmada(self, caso, _):
        caso.return_value = {"id": 418, "status": "pendiente", "version": 1, "enfermedad": "Influenza",
                             "municipio": "Monterrey", "report_date": "2026-11-01"}
        resp = self._cliente("EPIDEMIOLOGO").get("/vigilancia/casos/418")
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('<img src="/vigilancia/evidencias/12"', html)
        self.assertIn('href="/vigilancia/evidencias/13"', html)
        self.assertNotIn("X-Goog", html)
        self.assertEqual(self._rutas(), [("GET", "/cases/418/attachments")])

    def test_abrir_la_foto_pide_una_url_firmada_nueva_y_redirige(self):
        resp = self._cliente("ANALISTA").get("/vigilancia/evidencias/12")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], URL_FIRMADA)
        self.assertEqual(resp.headers["Cache-Control"], "private, no-store")
        peticion = self._evidencias()[-1]
        self.assertIn("/api/v1/attachments/12/url", peticion.full_url)
        self.assertEqual(peticion.get_header("Authorization"), "Bearer " + self._token("ANALISTA"))

    def test_una_foto_que_no_existe_es_404(self):
        self.estado[servicios.url_base("evidencias") + "/api/v1/attachments/99/url"] = 404
        resp = self._cliente("ANALISTA").get("/vigilancia/evidencias/99")
        self.assertEqual(resp.status_code, 404)

    def test_sin_sesion_manda_al_login_y_no_llama_al_servicio(self):
        resp = self.app.test_client().get("/vigilancia/evidencias/12")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])
        self.assertEqual(self._evidencias(), [])

    def test_si_evidencias_no_responde_el_caso_se_ve_sin_fotos(self):
        self.caido = True
        with patch("backend_web.servicios.caso", return_value={
                "id": 418, "status": "pendiente", "version": 1, "enfermedad": "Influenza",
                "municipio": "Monterrey", "report_date": "2026-11-01"}), \
                patch("backend_web.servicios.historial_caso", return_value=[]):
            resp = self._cliente("EPIDEMIOLOGO").get("/vigilancia/casos/418")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("evidencias".encode(), resp.data)


class AbrirReporte(ConEvidencias):
    def test_un_rol_con_reports_read_lo_abre_con_su_url_firmada(self):
        resp = self._cliente("EPIDEMIOLOGO").get("/comparacion/reportes/3")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], URL_FIRMADA)
        self.assertEqual(resp.headers["Cache-Control"], "private, no-store")
        self.assertIn("/api/v1/reports/3/url", self._evidencias()[-1].full_url)

    def test_el_capturista_recibe_403_y_no_se_llama_al_servicio(self):
        resp = self._cliente("CAPTURISTA").get("/comparacion/reportes/3")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._evidencias(), [])

    @patch("backend_web.servicios.corridas", return_value=[])
    @patch("backend_web.servicios.pareto", return_value=None)
    @patch("backend_web.servicios.comparacion")
    def test_la_comparacion_lista_los_reportes_de_sus_corridas(self, comparacion, *_):
        comparacion.return_value = [
            {"id": i, "scenario_id": 3, "scenario_name": "Escenario", "version_number": 1, "serie": [],
             "fallecimientos": 1, "pico_casos_activos": 2, "dia_pico": 3, "tasa_ataque": 0.1}
            for i in (12, 15)]
        resp = self._cliente("EPIDEMIOLOGO").get("/comparacion?run_id=12&run_id=15")
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Cierre contra cuarentena", html)
        self.assertIn('href="/comparacion/reportes/3"', html)
        self.assertIn(("GET", "/reports"), self._rutas())
        self.assertIn("runs=12%2C15", self._evidencias()[-1].full_url)
        # El EPIDEMIOLOGO lee pero no sube (D35).
        self.assertNotIn('name="archivo"', html)

    def test_reportes_muestra_los_guardados(self):
        resp = self._cliente("ANALISTA").get("/reportes")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Cierre contra cuarentena".encode(), resp.data)
        self.assertNotIn("Pendiente: falta el almacenamiento".encode(), resp.data)


class SubirReporte(ConEvidencias):
    def _sube(self, rol="ANALISTA", pdf=PDF, titulo="Cierre contra cuarentena", corridas=("12", "15"),
              nombre="reporte.pdf"):
        datos = {"run_id": list(corridas), "titulo": titulo, "archivo": (io.BytesIO(pdf), nombre)}
        with self._cliente(rol) as cliente:
            resp = cliente.post("/comparacion/reportes", data=datos,
                                content_type="multipart/form-data")
            with cliente.session_transaction() as sesion:
                self.mensajes = [m for _, m in sesion.get("_flashes", [])]
        return resp

    def test_el_analista_sube_el_pdf_tal_cual_con_su_huella(self):
        resp = self._sube()
        self.assertEqual(resp.status_code, 302)
        self.assertIn("run_id=12", resp.headers["Location"])
        peticion = self._evidencias()[-1]
        self.assertEqual(peticion.get_method(), "POST")
        self.assertIn("/api/v1/reports?", peticion.full_url)
        self.assertIn("runs=12%2C15", peticion.full_url)
        self.assertIn("title=Cierre+contra+cuarentena", peticion.full_url)
        self.assertEqual(peticion.data, PDF)
        self.assertEqual(peticion.get_header("Content-type"), "application/pdf")
        self.assertEqual(peticion.get_header("X-content-sha256"), hashlib.sha256(PDF).hexdigest())
        self.assertEqual(peticion.get_header("Authorization"), "Bearer " + self._token("ANALISTA"))
        self.assertTrue(any("Reporte 3 guardado" in m for m in self.mensajes), self.mensajes)

    def test_el_epidemiologo_recibe_403_y_no_se_manda_nada(self):
        resp = self._sube("EPIDEMIOLOGO")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._evidencias(), [])

    def test_un_archivo_que_no_es_pdf_se_rechaza_en_la_web(self):
        resp = self._sube(pdf=b"\x89PNG\r\n\x1a\n" + b"x" * 50, nombre="reporte.pdf")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("El archivo no es un PDF.", self.mensajes)
        self.assertEqual(self._evidencias(), [])

    def test_un_pdf_de_mas_de_20_mb_se_rechaza_en_la_web(self):
        grande = b"%PDF-" + b"0" * archivos.MAXIMO
        resp = self._sube(pdf=grande)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._evidencias(), [])

    def test_sin_corridas_no_se_manda_nada(self):
        resp = self._sube(corridas=())
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._evidencias(), [])

    def test_si_evidencias_rechaza_el_reporte_se_explica_y_no_cae(self):
        self.estado[servicios.url_base("evidencias") + "/api/v1/reports"] = 422
        resp = self._sube()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(self._evidencias()), 1)
        self.assertEqual(self.mensajes, ["No."])

    def test_si_evidencias_no_responde_dice_que_no_se_guardo(self):
        self.caido = True
        resp = self._sube()
        self.assertEqual(resp.status_code, 503)
        self.assertIn("El cambio no se guardó".encode(), resp.data)


class ValidaPdf(unittest.TestCase):
    def test_un_pdf_valido_regresa_su_huella(self):
        huella, errores = archivos.valida_pdf(PDF)
        self.assertEqual((huella, errores), (hashlib.sha256(PDF).hexdigest(), []))

    def test_vacio_png_y_grande_no_pasan(self):
        for datos in (b"", b"\x89PNG\r\n\x1a\n", b"%PDF-" + b"0" * archivos.MAXIMO):
            huella, errores = archivos.valida_pdf(datos)
            self.assertIsNone(huella)
            self.assertTrue(errores)
