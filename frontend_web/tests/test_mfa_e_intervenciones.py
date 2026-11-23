"""El segundo paso del MFA en el login (D40) y el seguimiento de intervenciones (D51).

Los servicios se simulan en la frontera de backend_web (D36): ni base ni contenedores.
"""
import os
from unittest.mock import patch

from backend_web.auth import create_token
from backend_web.servicios import ErrorServicio, ServicioNoDisponible
from frontend_web.app import sesion_servicios

from .base import AppTestCase

TOKENS = {"access_token": "acceso", "refresh_token": "renovar",
          "usuario": {"id": 1, "username": "admin", "full_name": "Admin", "roles": ["ADMINISTRADOR"]}}


class MfaLoginTests(AppTestCase):
    puente_servicios = False

    def _pide_mfa(self, client, enrolado=True):
        reto = {"mfa_requerido": True, "mfa_token": "reto", "mfa_enrolado": enrolado, "mfa_expira": 1}
        with patch.object(sesion_servicios, "iniciar", return_value=reto), \
                patch.object(sesion_servicios, "captcha", return_value=None):
            r = client.post("/login?next=/mapa", data={"usuario": "admin", "password": "x"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/login/mfa"))

    def test_sin_reto_pendiente_regresa_al_login(self):
        with self.app.test_client() as client:
            r = client.get("/login/mfa")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/login"))

    def test_el_codigo_correcto_abre_la_sesion_y_va_a_next(self):
        with self.app.test_client() as client:
            self._pide_mfa(client)
            self.assertIn("Código de tu app", client.get("/login/mfa").get_data(as_text=True))
            with patch.object(sesion_servicios, "mfa", return_value=TOKENS) as mfa:
                r = client.post("/login/mfa", data={"accion": "verificar", "codigo": "123456"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/mapa"))
        mfa.assert_called_once_with("verify", "reto", codigo="123456")
        self.assertIn("access_token=acceso", " ".join(r.headers.getlist("Set-Cookie")))

    def test_el_codigo_incorrecto_lo_explica_sin_abrir_sesion(self):
        with self.app.test_client() as client:
            self._pide_mfa(client)
            with patch.object(sesion_servicios, "mfa",
                              side_effect=ErrorServicio("auth", 401, "MFA_CODIGO_INVALIDO", "no")):
                r = client.post("/login/mfa", data={"accion": "verificar", "codigo": "000000"})
        self.assertEqual(r.status_code, 401)
        self.assertIn("El código no es correcto", r.get_data(as_text=True))
        self.assertNotIn("access_token=", " ".join(r.headers.getlist("Set-Cookie")))

    def test_el_reto_vencido_manda_al_login(self):
        with self.app.test_client() as client:
            self._pide_mfa(client)
            with patch.object(sesion_servicios, "mfa",
                              side_effect=ErrorServicio("auth", 401, "MFA_TOKEN_INVALIDO", "vencio")):
                r = client.post("/login/mfa", data={"accion": "verificar", "codigo": "123456"})
            self.assertEqual(r.status_code, 302)
            self.assertEqual(client.get("/login/mfa").status_code, 302)

    def test_enrolarse_muestra_la_clave_y_confirmar_los_codigos_de_respaldo(self):
        alta = {"secreto": "ABCDEF", "uri": "otpauth://totp/x", "algoritmo": "SHA1", "digitos": 6, "periodo": 30}
        with self.app.test_client() as client:
            self._pide_mfa(client, enrolado=False)
            self.assertIn("código de alta", client.get("/login/mfa").get_data(as_text=True))
            with patch.object(sesion_servicios, "mfa", return_value=alta) as mfa:
                r = client.post("/login/mfa", data={"accion": "enrolar", "codigo_alta": "abc"})
            mfa.assert_called_once_with("enroll", "reto", codigo_alta="abc")
            self.assertIn("ABCDEF", r.get_data(as_text=True))
            with patch.object(sesion_servicios, "mfa",
                              return_value=dict(TOKENS, codigos_respaldo=["R1", "R2"])):
                r = client.post("/login/mfa", data={"accion": "confirmar", "codigo": "123456"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("R1", r.get_data(as_text=True))
        self.assertIn("access_token=acceso", " ".join(r.headers.getlist("Set-Cookie")))

    def test_auth_caido_lo_dice(self):
        with self.app.test_client() as client:
            self._pide_mfa(client)
            with patch.object(sesion_servicios, "mfa", side_effect=ServicioNoDisponible("auth")):
                r = client.post("/login/mfa", data={"accion": "verificar", "codigo": "123456"})
        self.assertEqual(r.status_code, 503)


class DispositivoTests(AppTestCase):
    puente_servicios = False

    def _cuerpo(self, entorno):
        with patch.dict(os.environ, entorno, clear=False), \
                patch.object(sesion_servicios, "llamar", return_value=TOKENS) as llamar, \
                self.app.test_request_context():
            sesion_servicios.iniciar("admin", "x", "c", "1", "navegador-12345")
        return llamar.call_args.kwargs["cuerpo"]

    def test_sin_mfa_no_manda_el_dispositivo(self):
        cuerpo = self._cuerpo({"MFA_PERFILES": "", "DISPOSITIVO_OBLIGATORIO": "0"})
        self.assertNotIn("dispositivo_id", cuerpo)

    def test_con_mfa_manda_el_dispositivo_del_navegador(self):
        cuerpo = self._cuerpo({"MFA_PERFILES": "ADMINISTRADOR"})
        self.assertEqual(cuerpo["dispositivo_id"], "navegador-12345")


VERSION = {"id": 11, "scenario_id": 3, "version_number": 2, "status": "aprobado",
           "scenario_name": "Ola Influenza", "disease_name": "Influenza", "region_name": "Monterrey",
           "revisado_por": "Diana"}
VACUNA = {"id": 5, "code": "VACUNACION", "name": "Vacunación", "target_layer": "todas", "start_day": 30,
          "end_day": None, "coverage": 0.6, "compliance": None, "params": {}, "order_index": 0}
TIPO = {"code": "VACUNACION", "unit_cost": 400, "cost_unit": "por_dosis", "cost_source": None,
        "cost_is_assumption": True, "person_days_per_unit": 0.5, "person_days_source": None,
        "person_days_is_assumption": True}
CAMPANA = {"id": 1, "name": "Vacunación invierno", "enfermedad": "Influenza", "municipio": None,
           "starts_on": "2026-12-01", "ends_on": "2026-12-15", "target_population": 1000,
           "status": "programada"}


class SeguimientoIntervencionesTests(AppTestCase):
    puente_servicios = False

    def _get(self, rol, permisos, intervenciones=(VACUNA,)):
        token = create_token({"id": 999, "username": "prueba", "full_name": "Prueba", "roles": [rol]})
        caidas = intervenciones is None
        with patch("frontend_web.app.permisos.permisos_de_la_sesion", return_value=set(permisos)), \
                patch("frontend_web.app.permisos._audita_negado"), \
                patch("backend_web.servicios.avisos", return_value=([], 0)), \
                patch("backend_web.servicios.todas_las_versiones", return_value=[VERSION]), \
                patch("backend_web.servicios.tipos_intervencion", return_value=[TIPO]), \
                patch("backend_web.servicios.corridas",
                      return_value=[{"id": 40, "scenario_version_id": 11, "status": "completado"},
                                    {"id": 41, "scenario_version_id": 11, "status": "completado"}]), \
                patch("backend_web.servicios.campanas", return_value=[CAMPANA]), \
                patch("backend_web.servicios.intervenciones_version",
                      side_effect=ServicioNoDisponible("intervenciones") if caidas else None,
                      return_value=list(intervenciones or [])), \
                self.app.test_client() as client:
            client.set_cookie("access_token", token)
            return client.get("/intervenciones")

    def test_el_analista_ve_lo_programado_su_costo_sus_corridas_y_la_campana(self):
        r = self._get("ANALISTA", {"scenarios.read"})
        texto = r.get_data(as_text=True)
        self.assertEqual(r.status_code, 200)
        for esperado in ("Ola Influenza", "Vacunación", "$ 400.00", "0.5", "SIM-00040",
                         "Comparar las completadas", "Vacunación invierno"):
            self.assertIn(esperado, texto)

    def test_el_capturista_recibe_403(self):
        self.assertEqual(self._get("CAPTURISTA", {"cases.read"}).status_code, 403)

    def test_sin_el_servicio_intervenciones_lo_explica_y_lo_demas_sigue(self):
        r = self._get("ANALISTA", {"scenarios.read"}, intervenciones=None)
        texto = r.get_data(as_text=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("servicio «intervenciones»", texto)
        self.assertIn("SIM-00040", texto)
