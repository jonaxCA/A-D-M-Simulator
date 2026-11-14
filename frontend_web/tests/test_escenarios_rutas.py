"""
Pruebas de las rutas de escenarios. Flask test client contra PostgreSQL real;
mismo requisito de base que las demas.

Desde D4 la web consulta escenarios y el EPIDEMIOLOGO dictamina en ella. Crear,
versionar, duplicar, editar intervenciones y enviar a revision es de la app de
escritorio, por medio de los servicios. Por eso los escenarios de estas pruebas
se arman con las mismas funciones de backend_web que usan `escenarios`,
`intervenciones` y `aprobacion`; sus reglas se prueban en
backend_web/tests/test_escenarios.py.

Ejecutar:
    python -m unittest frontend_web.tests.test_escenarios_rutas -v
"""
import unittest

from frontend_web.tests.base import AppTestCase, requiere_base
from backend_web import queries
from backend_web.db import get_conn, query
from backend_web.tests.base import contexto_de_prueba, id_de_usuario


@requiere_base
class _ConEscenario(AppTestCase):
    """Un escenario en borrador de alex.cavazos (ANALISTA) con una
    intervencion, armado como lo arman los servicios."""

    NOMBRE = "ZZZ escenario de prueba de rutas"

    def setUp(self):
        super().setUp()
        if not queries._hay_columnas_de_edad_en_version():
            self.skipTest("falta la migracion 023_escenarios_poblacion_por_edad.sql")
        regiones = queries.get_regiones_para_escenario()
        enfermedades = queries.get_enfermedades_para_escenario()
        mty = next((r for r in regiones if r["code"] == "19039"), None)
        enfermedad = next((e for e in enfermedades if e["simulable"]), None)
        if not mty or not mty["grupos"] or not enfermedad:
            self.skipTest("la base no tiene Monterrey con grupos de edad o una enfermedad simulable")

        self._borra()
        self.addCleanup(self._borra)
        self.autor = contexto_de_prueba(id_de_usuario("alex.cavazos"))
        datos, errores = queries.valida_escenario(
            {"name": self.NOMBRE, "disease_id": str(enfermedad["id"]),
             "region_id": str(mty["id"]), "population_size": str(mty["population"]),
             "estratificar": "on", "age_unknown_policy": "excluir",
             "initial_infected": "500", "horizon_days": "180"},
            regiones, enfermedades)
        self.assertEqual(errores, [])
        ok, error, self.sid = queries.crea_escenario(datos, contexto=self.autor)
        self.assertTrue(ok, error)

        detalle = queries.get_escenario_detalle(self.sid)
        intervencion, errores = queries.valida_intervencion(
            {"code": "CIERRE_ESCUELAS", "start_day": "10", "end_day": "60",
             "p_CIERRE_ESCUELAS_reduccion": "1"},
            queries.get_tipos_intervencion(), detalle["version"], detalle["intervenciones"])
        self.assertEqual(errores, [])
        ok, error = queries.agrega_intervencion(detalle["version"]["id"], intervencion,
                                                contexto=self.autor)
        self.assertTrue(ok, error)
        self.intervencion_id = queries.get_escenario_detalle(self.sid)["intervenciones"][0]["id"]

    def _borra(self):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM scenarios WHERE name = %s", (self.NOMBRE,))
                for (sid,) in cur.fetchall():
                    # audit_log NO se toca: es de solo insercion por diseno
                    # (fn_solo_insercion). Las intervenciones se van en cascada
                    # con la version.
                    cur.execute("DELETE FROM scenario_versions WHERE scenario_id = %s", (sid,))
                    cur.execute("DELETE FROM scenarios WHERE id = %s", (sid,))
            conn.commit()

    def _envia(self):
        ok, error = queries.envia_a_revision(self.sid, contexto=self.autor)
        self.assertTrue(ok, error)

    def _version_nueva(self):
        """La version siguiente, como la crea `escenarios` desde el escritorio."""
        detalle = queries.get_escenario_detalle(self.sid)
        region = next(r for r in queries.get_regiones_para_escenario()
                      if r["id"] == detalle["escenario"]["region_id"])
        datos, errores = queries.valida_version(
            {"estratificar": "on", "age_unknown_policy": "excluir", "initial_infected": "600",
             "horizon_days": "200", "notes": "Ajuste de prueba"},
            region, detalle["escenario"]["default_params"])
        self.assertEqual(errores, [])
        ok, error, numero = queries.crea_version(self.sid, datos, contexto=self.autor)
        self.assertTrue(ok, error)
        return numero

    def _estado(self):
        return queries.get_escenario_detalle(self.sid)["version"]["status"]

    def _html(self, client, ruta):
        resp = client.get(ruta)
        self.assertEqual(resp.status_code, 200, ruta)
        return " ".join(resp.data.decode("utf-8", "replace").split())


class ConsultaRutasTests(_ConEscenario):
    def test_anonimo_no_ve_escenarios(self):
        with self.app.test_client() as client:
            for ruta in ("/escenarios", f"/escenarios/{self.sid}"):
                resp = client.get(ruta, follow_redirects=False)
                self.assertEqual(resp.status_code, 302, ruta)
                self.assertIn("/login", resp.headers["Location"], ruta)

    def test_la_lista_no_ofrece_crear(self):
        with self.app.test_client() as client:
            self._login(client, "diana.flores", "Epidemia2026!")
            html = self._html(client, "/escenarios")
            self.assertIn(self.NOMBRE, html)
            self.assertIn("se crean y se editan en la app de escritorio", html)
            self.assertNotIn("Nuevo escenario", html)

    def test_el_detalle_es_de_solo_lectura_incluso_para_el_dueno(self):
        for usuario, clave in (("alex.cavazos", "Epidemia2026!"), ("admin", "Admin2026!")):
            with self.app.test_client() as client:
                self._login(client, usuario, clave)
                html = self._html(client, f"/escenarios/{self.sid}")
            self.assertIn("lt-barra", html, "no se dibujo la linea de tiempo")
            self.assertIn("Cierre de escuelas", html)
            self.assertIn("Historial de versiones (1)", html)
            self.assertIn("la envía a revisión desde la app de escritorio", html)
            for boton in ("Agregar intervención", "Enviar a revisión", "Nueva versión",
                          "Duplicar", "Quitar", 'method="post"'):
                self.assertNotIn(boton, html, f"{usuario}: {boton}")

    def test_el_detalle_dice_cuantos_habitantes_representa_cada_agente(self):
        """D6: population_size son agentes. Estratificada, la versión toma el censo completo
        (uno por habitante); la de la demo simula 500 000 agentes para Nuevo León."""
        demo = query("""SELECT s.id FROM scenarios s JOIN scenario_versions v
                        ON v.scenario_id = s.id AND v.is_current
                        WHERE s.name = 'Ola Influenza ZMM - otono 2026'""", one=True)
        with self.app.test_client() as client:
            self._login(client, "diana.flores", "Epidemia2026!")
            propio = self._html(client, f"/escenarios/{self.sid}")
            self.assertIn("agentes simulados", propio)
            self.assertIn("Uno por habitante de Monterrey", propio)
            if demo:
                html = self._html(client, f"/escenarios/{demo['id']}")
                self.assertIn("Cada agente representa 11.57 habitantes de Nuevo Leon", html)

    def test_una_version_anterior_se_abre_de_solo_lectura(self):
        self.assertEqual(self._version_nueva(), 2)
        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")
            self.assertIn("Historial de versiones (2)", self._html(client, f"/escenarios/{self.sid}"))
            html = self._html(client, f"/escenarios/{self.sid}?version=1")
            self.assertIn("Estás viendo la", html)
            self.assertIn("Es solo de lectura", html)

    def test_una_version_inexistente_da_404_amable(self):
        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")
            resp = client.get(f"/escenarios/{self.sid}?version=99", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("no existe", resp.data.decode("utf-8", "replace"))

    def test_las_rutas_de_edicion_ya_no_existen(self):
        """D4: ni el ADMINISTRADOR, que tiene todos los permisos, crea o edita
        escenarios desde la web."""
        base = f"/escenarios/{self.sid}"
        quitadas = (
            ("GET", "/escenarios/nuevo"), ("POST", "/escenarios/nuevo"),
            ("GET", f"{base}/versiones/nueva"), ("POST", f"{base}/versiones/nueva"),
            ("POST", f"{base}/duplicar"), ("POST", f"{base}/intervenciones"),
            ("POST", f"{base}/intervenciones/{self.intervencion_id}/quitar"),
            ("POST", f"{base}/intervenciones/{self.intervencion_id}/mover"),
            ("POST", f"{base}/enviar"),
        )
        with self.app.test_client() as client:
            self._login(client, "admin", "Admin2026!")
            for metodo, ruta in quitadas:
                resp = client.open(ruta, method=metodo, data={"name": self.NOMBRE + " (copia)"})
                self.assertEqual(resp.status_code, 404, f"{metodo} {ruta}")
        detalle = queries.get_escenario_detalle(self.sid)
        self.assertEqual(detalle["version"]["status"], "borrador")
        self.assertEqual(len(detalle["intervenciones"]), 1)
        self.assertEqual(len(queries.get_versiones(self.sid)), 1)
        self.assertIsNone(query("SELECT id FROM scenarios WHERE name = %s",
                                (self.NOMBRE + " (copia)",), one=True))


class AprobacionRutasTests(_ConEscenario):
    """El escritorio envia; dictaminar es del EPIDEMIOLOGO, en la web."""

    NOMBRE = "ZZZ escenario de rutas para aprobar"

    def test_el_analista_no_entra_a_la_bandeja(self):
        with self.app.test_client() as client:
            self._login(client, "alex.cavazos", "Epidemia2026!")
            resp = client.get("/revisiones", follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/dashboard", resp.headers["Location"])

    def test_el_epidemiologo_ve_la_bandeja_con_lo_enviado(self):
        self._envia()
        with self.app.test_client() as revisor:
            self._login(revisor, "diana.flores", "Epidemia2026!")
            html = self._html(revisor, "/revisiones")
            self.assertIn(self.NOMBRE, html)
            self.assertIn("Pendientes de revisión", html)

    def test_el_analista_no_dictamina(self):
        self._envia()
        cuenta = """SELECT count(*) n FROM audit_log
                    WHERE action = 'PERMISSION_DENIED' AND entity_type = 'scenario_versions'"""
        antes = query(cuenta, one=True)["n"]
        with self.app.test_client() as autor:
            self._login(autor, "alex.cavazos", "Epidemia2026!")
            autor.post(f"/escenarios/{self.sid}/revisar", data={"decision": "aprobar"},
                       follow_redirects=True)
        self.assertEqual(self._estado(), "en_revision", "un ANALISTA no puede aprobar")
        self.assertGreater(query(cuenta, one=True)["n"], antes,
                           "el intento debe quedar en la bitácora")

    def test_ciclo_completo(self):
        self._envia()
        with self.app.test_client() as revisor:
            self._login(revisor, "diana.flores", "Epidemia2026!")
            # El panel de dictamen aparece para quien puede decidir.
            self.assertIn("Dictamen", self._html(revisor, f"/escenarios/{self.sid}"))
            resp = revisor.post(f"/escenarios/{self.sid}/revisar",
                                data={"decision": "rechazar",
                                      "comentario": "Falta la capa trabajo."},
                                follow_redirects=True)
            self.assertIn("Versión rechazada", resp.data.decode("utf-8", "replace"))
        self.assertEqual(self._estado(), "rechazado")

        # Quien la armo atiende el rechazo desde el escritorio.
        self._version_nueva()
        self.assertEqual(self._estado(), "borrador")
        self._envia()
        with self.app.test_client() as revisor:
            self._login(revisor, "diana.flores", "Epidemia2026!")
            resp = revisor.post(f"/escenarios/{self.sid}/revisar",
                                data={"decision": "aprobar", "comentario": "Va."},
                                follow_redirects=True)
            html = resp.data.decode("utf-8", "replace")
            self.assertIn("Versión aprobada", html)
            self.assertIn("Ya se puede simular", html)
        self.assertEqual(self._estado(), "aprobado")
        self.assertFalse(queries.get_escenario_detalle(self.sid)["editable"])

    def test_el_administrador_ve_la_bandeja_pero_no_dictamina(self):
        self._envia()
        with self.app.test_client() as admin:
            self._login(admin, "admin", "Admin2026!")
            self.assertEqual(admin.get("/revisiones").status_code, 200)
            html = self._html(admin, f"/escenarios/{self.sid}")
            self.assertNotIn("Dictamen", html,
                             "quien opera el sistema no valida la epidemiología")
            admin.post(f"/escenarios/{self.sid}/revisar", data={"decision": "aprobar"},
                       follow_redirects=True)
        self.assertEqual(self._estado(), "en_revision")


if __name__ == "__main__":
    unittest.main()
