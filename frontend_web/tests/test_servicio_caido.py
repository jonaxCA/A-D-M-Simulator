"""Cuando un servicio no responde (D36, C6): la sección lo explica y lo demás sigue; sin sesiones
la web no deja pasar; una escritura dice que no se guardó; nunca se muestra la traza (RNF-E06).

La web ya no tiene base: lo que antes probaba la base caída ahora es el servicio caído.
"""
import unittest
from unittest.mock import patch

from backend_web.servicios import ServicioNoDisponible
from frontend_web.app.permisos import COOKIE_NAME
from frontend_web.tests.base import ConUsuarioSimulado


class ServicioCaido(ConUsuarioSimulado):
    puente_servicios = False

    def test_sin_indicadores_el_tablero_publico_lo_explica_y_lo_demas_se_ve(self):
        with patch("backend_web.servicios.indicadores_tablero", side_effect=ServicioNoDisponible("indicadores")), \
                patch("backend_web.servicios.resumen_situacion", side_effect=ServicioNoDisponible("indicadores")), \
                patch("backend_web.servicios.curva_tablero", side_effect=ServicioNoDisponible("indicadores")):
            resp = self.app.test_client().get("/")
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Este dato no está disponible por ahora (servicio «indicadores»)", html)
        self.assertIn("CASOS ACTIVOS", html)

    def test_sin_sesiones_una_pantalla_protegida_da_503_amable(self):
        with patch("frontend_web.app.sesion_servicios._actual", side_effect=ServicioNoDisponible("sesiones")):
            client = self.app.test_client()
            client.set_cookie(COOKIE_NAME, self._token())
            resp = client.get("/enfermedades")
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 503)
        self.assertIn("El servicio «sesiones» no respondió", html)
        self.assertNotIn("Traceback", html)

    def test_una_escritura_con_el_servicio_caido_dice_que_no_se_guardo(self):
        with patch("backend_web.servicios.enfermedad", side_effect=ServicioNoDisponible("enfermedades")):
            client = self.app.test_client()
            client.set_cookie(COOKIE_NAME, self._token("EPIDEMIOLOGO"))
            resp = client.post("/enfermedades/1/estado", data={"activa": "0"})
        self.assertEqual(resp.status_code, 503)
        self.assertIn("El cambio no se guardó", resp.get_data(as_text=True))

    def test_un_error_inesperado_da_500_sin_traza(self):
        with patch("backend_web.servicios.enfermedades_stats", side_effect=RuntimeError("password=secreta")), \
                patch("backend_web.servicios.enfermedades", return_value={"enfermedades": []}):
            client = self.app.test_client()
            client.set_cookie(COOKIE_NAME, self._token())
            resp = client.get("/enfermedades")
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 500)
        self.assertIn("Algo salió mal", html)
        self.assertNotIn("secreta", html)
        self.assertNotIn("Traceback", html)


if __name__ == "__main__":
    unittest.main()
