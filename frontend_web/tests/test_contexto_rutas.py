"""
Del lado del sitio: contexto_de_peticion() lleva a la bitacora el usuario, la
IP y el navegador de la peticion real, igual que cuando la capa de datos los
leia de flask.request.

Ejecutar:
    python -m unittest frontend_web.tests.test_contexto_rutas -v
"""
from frontend_web.tests.base import AppTestCase, requiere_base
from backend_web import queries
from backend_web.db import query
from backend_web.tests.base import contexto_de_prueba, escribe, id_de_usuario, token_de
from frontend_web.app.permisos import COOKIE_NAME

NOMBRE = "ZZZ escenario de la prueba de contexto en rutas"
NAVEGADOR = "navegador-de-prueba-rutas/2.0"


@requiere_base
class ContextoDePeticionTests(AppTestCase):

    def setUp(self):
        super().setUp()
        self._borra()
        self.addCleanup(self._borra)

    def _borra(self):
        escribe("""DELETE FROM scenario_versions WHERE scenario_id IN
                   (SELECT id FROM scenarios WHERE name = %s)""", (NOMBRE,))
        escribe("DELETE FROM scenarios WHERE name = %s", (NOMBRE,))

    def _ultima(self, action, entity_type, entity_id):
        return query(
            """SELECT user_id, host(ip_address) AS ip, user_agent FROM audit_log
               WHERE action = %s AND entity_type = %s AND entity_id = %s
               ORDER BY id DESC LIMIT 1""", (action, entity_type, str(entity_id)), one=True)

    def test_el_dictamen_de_una_version_audita_al_usuario_y_su_navegador(self):
        """Desde D4 el escenario se crea y se envia desde la app de escritorio;
        la escritura que queda en la web es el dictamen."""
        regiones = queries.get_regiones_para_escenario()
        mty = next(r for r in regiones if r["code"] == "19039")
        enfermedad = next(e for e in queries.get_enfermedades_para_escenario() if e["simulable"])
        datos, errores = queries.valida_escenario(
            {"name": NOMBRE, "disease_id": str(enfermedad["id"]), "region_id": str(mty["id"]),
             "population_size": "1000", "initial_infected": "5", "horizon_days": "90"},
            regiones, queries.get_enfermedades_para_escenario())
        self.assertEqual(errores, [])
        autor = contexto_de_prueba(id_de_usuario("alex.cavazos"))
        ok, error, sid = queries.crea_escenario(datos, contexto=autor)
        self.assertTrue(ok, error)
        ok, error = queries.envia_a_revision(sid, contexto=autor)
        self.assertTrue(ok, error)
        version_id = queries.get_escenario_detalle(sid)["version"]["id"]

        with self.app.test_client() as client:
            client.set_cookie(COOKIE_NAME, token_de("diana.flores"))
            resp = client.post(f"/escenarios/{sid}/revisar", headers={"User-Agent": NAVEGADOR},
                               data={"decision": "rechazar", "comentario": "Prueba de contexto."})
        self.assertEqual(resp.status_code, 302, resp.data[:300])
        fila = self._ultima("UPDATE", "scenario_versions", version_id)
        self.assertEqual((fila["user_id"], fila["ip"], fila["user_agent"]),
                         (id_de_usuario("diana.flores"), "127.0.0.1", NAVEGADOR))

    def test_un_login_fallido_se_audita_sin_usuario_pero_con_su_navegador(self):
        usuario = "nadie.de.la.prueba.de.contexto"
        with self.app.test_client() as client:
            resp = client.post("/login", headers={"User-Agent": NAVEGADOR},
                               data={"usuario": usuario, "password": "x"})
        self.assertEqual(resp.status_code, 401)
        fila = self._ultima("LOGIN_FAILED", "users", usuario)
        self.assertEqual((fila["user_id"], fila["ip"], fila["user_agent"]),
                         (None, "127.0.0.1", NAVEGADOR))

    def test_el_navegador_se_recorta_a_255(self):
        largo = "x" * 400
        usuario = "nadie.de.la.prueba.de.recorte"
        with self.app.test_client() as client:
            client.post("/login", headers={"User-Agent": largo},
                        data={"usuario": usuario, "password": "x"})
        self.assertEqual(self._ultima("LOGIN_FAILED", "users", usuario)["user_agent"],
                         "x" * 255)
