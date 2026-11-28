"""Aceptación «Integración del portal web»: una operación de la web consume realmente una API (D36).

Se intercepta la petición HTTP que sale de la web: ni la base ni el servicio corren aquí.
"""
import io
import json
import urllib.error
from unittest.mock import patch

from frontend_web.tests.base import ConUsuarioSimulado


class Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class AprobacionPorServicio(ConUsuarioSimulado):
    # Aquí se intercepta la petición HTTP misma, no se usa el puente de servicios.
    puente_servicios = False

    def setUp(self):
        super().setUp()
        self.peticiones = []

        def urlopen(peticion, timeout):
            self.peticiones.append(peticion)
            if self.caido:
                raise urllib.error.URLError("aprobacion apagado")
            return Respuesta(json.dumps(self.respuesta).encode("utf-8"))
        simulado = patch("backend_web.servicios.urllib.request.urlopen", side_effect=urlopen)
        simulado.start()
        self.addCleanup(simulado.stop)
        self.caido = False
        self.respuesta = {"scenario_id": 3, "version_id": 11, "version_number": 2,
                          "status": "aprobado", "decision": "aprobar"}

    def _aprobar(self):
        with self.app.test_client() as client:
            client.set_cookie("access_token", self.token)
            return client.post("/escenarios/3/revisar", data={"decision": "aprobar", "comentario": "ok"})

    def test_aprobar_en_la_web_llama_al_servicio_aprobacion_con_el_jwt(self):
        self.token = self._token("EPIDEMIOLOGO")
        resp = self._aprobar()
        self.assertEqual(resp.status_code, 302)
        peticion = self.peticiones[-1]
        self.assertEqual(peticion.get_method(), "POST")
        self.assertIn("/api/v1/scenarios/3/review?format=json", peticion.full_url)
        self.assertEqual(peticion.get_header("Authorization"), "Bearer " + self.token)
        self.assertEqual(json.loads(peticion.data), {"decision": "aprobar", "comentario": "ok"})

    def test_si_aprobacion_no_responde_la_pantalla_lo_explica(self):
        self.token = self._token("EPIDEMIOLOGO")
        self.caido = True
        resp = self._aprobar()
        self.assertEqual(resp.status_code, 503)
        texto = resp.get_data(as_text=True)
        self.assertIn("aprobacion", texto)
        self.assertIn("El cambio no se guardó", texto)

    def test_un_analista_no_llega_a_llamar_al_servicio(self):
        self.token = self._token("ANALISTA")
        resp = self._aprobar()
        # C1: sin scenarios.approve, 403 y el PERMISSION_DENIED a roles; aprobacion ni se entera.
        self.assertEqual(resp.status_code, 403)
        rutas = [p.full_url.split("?")[0].rsplit("/api/v1", 1)[1] for p in self.peticiones]
        self.assertIn("/audit/denied", rutas)
        self.assertNotIn("/scenarios/3/review", rutas)
