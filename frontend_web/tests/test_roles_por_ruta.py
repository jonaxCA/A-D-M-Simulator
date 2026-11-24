"""Cada ruta de la web contra cada rol de la matriz de permisos (C1, RF-A05, RF-G11), sin base.

Los servicios están simulados (D36): sesiones y roles contestan por el token de la prueba y todo lo
demás está caído. La prueba solo mira el candado: con un rol que no debe entrar la ruta responde
403 y deja su PERMISSION_DENIED en roles; con uno que debe entrar no responde 403 ni manda al login,
aunque la pantalla después diga que su servicio no responde. La tabla sale de
docs/requerimientos/matriz-permisos.md, no de los permisos que usa el código.
"""
import re
from unittest.mock import patch

from backend_web.servicios import ServicioNoDisponible
from frontend_web.app.permisos import COOKIE_NAME
from frontend_web.tests.base import ConUsuarioSimulado

ADM, EPI, ANA, CAP = "ADMINISTRADOR", "EPIDEMIOLOGO", "ANALISTA", "CAPTURISTA"
ROLES = (ADM, EPI, ANA, CAP)
TODOS = {ADM, EPI, ANA, CAP}
OFICINA = {ADM, EPI, ANA}
ADM_EPI = {ADM, EPI}
SOLO_ADM = {ADM}

# (método, regla) -> roles que entran. El CAPTURISTA solo ve el tablero y el mapa (RF-G11).
# /campanas no tiene fila en la matriz: se toma de D49 (alta y baja con catalogs.update).
ENTRAN = {
    ("GET", "/dashboard"): TODOS,
    ("GET", "/mapa"): TODOS,
    ("GET", "/api/mapa"): TODOS,
    ("GET", "/avisos"): OFICINA,
    ("POST", "/avisos/<int:aviso_id>/leido"): OFICINA,
    ("GET", "/enfermedades"): OFICINA,
    ("GET", "/enfermedades/nueva"): ADM_EPI,
    ("POST", "/enfermedades/nueva"): ADM_EPI,
    ("GET", "/enfermedades/<int:disease_id>/editar"): ADM_EPI,
    ("POST", "/enfermedades/<int:disease_id>/editar"): ADM_EPI,
    ("POST", "/enfermedades/<int:disease_id>/estado"): ADM_EPI,
    ("GET", "/export/enfermedades.csv"): OFICINA,
    ("GET", "/export/resumen.csv"): OFICINA,
    ("GET", "/export/monitoreo.csv"): OFICINA,
    ("GET", "/monitoreo"): OFICINA,
    ("GET", "/regiones"): OFICINA,
    ("GET", "/regiones/<int:region_id>/editar"): SOLO_ADM,
    ("POST", "/regiones/<int:region_id>/editar"): SOLO_ADM,
    ("GET", "/regiones/<int:region_id>/edades"): SOLO_ADM,
    ("POST", "/regiones/<int:region_id>/edades"): SOLO_ADM,
    ("GET", "/escenarios"): OFICINA,
    ("GET", "/escenarios/<int:scenario_id>"): OFICINA,
    ("POST", "/escenarios/<int:scenario_id>/revisar"): ADM_EPI,
    ("GET", "/revisiones"): ADM_EPI,
    ("GET", "/intervenciones"): OFICINA,
    ("GET", "/simulaciones"): OFICINA,
    ("GET", "/simulaciones/corridas/<int:run_id>"): OFICINA,
    ("GET", "/simulaciones/corridas/<int:run_id>/estado"): OFICINA,
    ("GET", "/comparacion"): OFICINA,
    ("POST", "/comparacion/reportes"): {ADM, ANA},
    ("GET", "/comparacion/reportes/<int:reporte_id>"): OFICINA,
    ("GET", "/comparacion/costos"): ADM_EPI,
    ("POST", "/comparacion/costos"): ADM_EPI,
    ("GET", "/reportes"): OFICINA,
    ("GET", "/vigilancia"): OFICINA,
    ("GET", "/vigilancia/casos/<int:case_id>"): OFICINA,
    ("POST", "/vigilancia/casos/<int:case_id>"): {EPI},
    ("GET", "/vigilancia/evidencias/<int:evidencia_id>"): OFICINA,
    ("GET", "/campanas"): OFICINA,
    ("POST", "/campanas"): ADM_EPI,
    ("GET", "/usuarios"): SOLO_ADM,
    ("GET", "/usuarios/nuevo"): SOLO_ADM,
    ("POST", "/usuarios/nuevo"): SOLO_ADM,
    ("GET", "/usuarios/<int:user_id>/editar"): SOLO_ADM,
    ("POST", "/usuarios/<int:user_id>/editar"): SOLO_ADM,
    ("POST", "/usuarios/<int:user_id>/estado"): SOLO_ADM,
    ("POST", "/usuarios/<int:user_id>/eliminar"): SOLO_ADM,
    ("GET", "/auditoria"): SOLO_ADM,
}

# Roles que hoy entran aunque la matriz (y D47) digan que no. Se dejan aquí, a la vista, y no en ENTRAN:
# la prueba falla cuando se corrige, para que esta línea se borre.
# - Validar un caso: D47 dice que el ADMINISTRADOR no valida, pero la migración 010 le dio todos los
#   permisos y la web solo pide `cases.approve`. Lo frena el servicio `casos` (ROLES_REVISAN).
DIVERGENCIAS = {("POST", "/vigilancia/casos/<int:case_id>"): {ADM}}

# Sin candado a propósito: las ve cualquiera, con o sin sesión.
PUBLICAS = {("GET", "/"), ("GET", "/health"), ("GET", "/login"), ("POST", "/login"), ("GET", "/login/mfa"),
            ("POST", "/login/mfa"), ("GET", "/logout"), ("GET", "/static/<path:filename>")}


def con_numeros(regla):
    return re.sub(r"<int:\w+>", "1", regla).replace("<path:filename>", "css/styles.css")


class RolesPorRuta(ConUsuarioSimulado):
    puente_servicios = False

    def setUp(self):
        super().setUp()
        self.llamadas = []

        def servicio_caido(servicio, metodo, ruta, **datos):
            self.llamadas.append((servicio, metodo, ruta, datos))
            raise ServicioNoDisponible(servicio)

        for objetivo in ("backend_web.servicios.llamar", "frontend_web.app.sesion_servicios.llamar"):
            simulado = patch(objetivo, side_effect=servicio_caido)
            simulado.start()
            self.addCleanup(simulado.stop)
        self.base = []
        for objetivo in ("backend_web.db.get_conn", "backend_web.db.query", "backend_web.db.execute"):
            simulado = patch(objetivo, side_effect=lambda *a, **k: self.base.append(a) or 1 / 0)
            simulado.start()
            self.addCleanup(simulado.stop)

    def _reglas(self):
        for regla in self.app.url_map.iter_rules():
            for metodo in sorted(regla.methods - {"HEAD", "OPTIONS"}):
                yield metodo, regla.rule

    def test_la_tabla_cubre_todas_las_rutas_y_ninguna_sin_candado_sobra(self):
        reales = set(self._reglas())
        self.assertEqual(reales - set(ENTRAN) - PUBLICAS, set(),
                         "Ruta nueva sin fila en ENTRAN: agrégala con los roles de la matriz.")
        self.assertEqual((set(ENTRAN) | PUBLICAS) - reales, set(), "Fila de una ruta que ya no existe.")

    def _pide(self, rol, metodo, regla):
        client = self.app.test_client()
        client.set_cookie(COOKIE_NAME, self._token(rol))
        return client.open(con_numeros(regla), method=metodo, follow_redirects=False)

    def test_cada_rol_entra_o_recibe_403_segun_la_matriz(self):
        for (metodo, regla), entran in sorted(ENTRAN.items()):
            entran = entran | DIVERGENCIAS.get((metodo, regla), set())
            for rol in ROLES:
                with self.subTest(ruta=regla, metodo=metodo, rol=rol):
                    self.llamadas.clear()
                    resp = self._pide(rol, metodo, regla)
                    if rol in entran:
                        self.assertNotEqual(resp.status_code, 403, "debía entrar")
                        self.assertNotIn("/login", resp.headers.get("Location", ""), "lo mandó al login")
                    else:
                        self.assertEqual(resp.status_code, 403, "debía responder 403")
                        negados = [d for s, m, r, d in self.llamadas
                                   if (s, m, r) == ("roles", "POST", "/api/v1/audit/denied")]
                        self.assertEqual([d["cuerpo"]["ruta"] for d in negados], [con_numeros(regla)[:64]],
                                         "el 403 no dejó su PERMISSION_DENIED")

    def test_sin_sesion_toda_ruta_protegida_manda_al_login(self):
        for (metodo, regla) in sorted(ENTRAN):
            with self.subTest(ruta=regla, metodo=metodo):
                resp = self.app.test_client().open(con_numeros(regla), method=metodo, follow_redirects=False)
                self.assertEqual(resp.status_code, 302)
                self.assertIn("/login", resp.headers["Location"])

    def test_un_token_sin_roles_de_oficina_no_entra_a_nada_protegido(self):
        # Un rol que la matriz no conoce no hereda permisos: falla cerrada.
        for (metodo, regla) in sorted(ENTRAN):
            # El tablero y el mapa son de todos; los avisos no piden permiso, solo no ser CAPTURISTA.
            if regla in ("/dashboard", "/mapa", "/api/mapa", "/avisos", "/avisos/<int:aviso_id>/leido"):
                continue
            with self.subTest(ruta=regla, metodo=metodo):
                self.assertEqual(self._pide("ROL_QUE_NO_EXISTE", metodo, regla).status_code, 403)

    def test_ninguna_pantalla_toca_la_base(self):
        for (metodo, regla) in sorted(ENTRAN):
            self._pide(ADM, metodo, regla)
        self.assertEqual(self.base, [])
