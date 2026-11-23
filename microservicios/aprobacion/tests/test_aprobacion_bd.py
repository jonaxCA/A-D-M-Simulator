import unittest
import uuid

import psycopg2

from epidemia_comun.bd import get_conn, query
from epidemia_comun.errores import ErrorAPI
from microservicios.aprobacion import datos
from microservicios.pruebas_bd import contexto_de_prueba, escribe, tiene_base

HUELLA = "9c56cc51b374c3ba189210d5b6d4bf57790d351c96c47c02190ecf1e430635ab"


# Contra la base de pruebas, con la 064. Cada prueba arma su propio escenario con una versión en
# borrador y lo borra al terminar (el rol de la app puede; svc_aprobacion no). La bitácora se queda.
@unittest.skipUnless(tiene_base(), "Requiere la base de pruebas")
class AprobacionBdTests(unittest.TestCase):
    def setUp(self):
        usuarios = [u["id"] for u in query("SELECT id FROM users ORDER BY id LIMIT 3")]
        self.autor, self.revisor = contexto_de_prueba(usuarios[1]), contexto_de_prueba(usuarios[2])
        base = query("SELECT disease_id, region_id FROM scenarios ORDER BY id LIMIT 1", one=True)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO scenarios (name, disease_id, region_id, owner_id)
                               VALUES (%s, %s, %s, %s) RETURNING id""",
                            ("PRUEBA " + uuid.uuid4().hex[:10], base["disease_id"], base["region_id"],
                             self.autor.user_id))
                self.scenario_id = cur.fetchone()[0]
            conn.commit()
        self.addCleanup(escribe, "DELETE FROM scenarios WHERE id = %s", (self.scenario_id,))
        self.addCleanup(escribe, "DELETE FROM scenario_versions WHERE scenario_id = %s", (self.scenario_id,))
        escribe("""INSERT INTO scenario_versions (scenario_id, version_number, is_current, population_size,
                                                  horizon_days, initial_infected, created_by)
                   VALUES (%s, 1, true, 100000, 90, 10, %s)""", (self.scenario_id, self.autor.user_id))
        _, version = datos.escenario_y_version(self.scenario_id)
        self.version_id = version["id"]

    def version(self):
        return query("""SELECT status, submitted_at, reviewed_by, reviewed_at, review_comment, disease_params,
                               approval_sha256 FROM scenario_versions WHERE id = %s""", (self.version_id,), one=True)

    def asiento(self):
        return query("""SELECT data_before, data_after FROM audit_log WHERE entity_type = 'scenario_versions'
                        AND entity_id = %s ORDER BY id DESC LIMIT 1""", (str(self.version_id),), one=True)

    def test_enviar_congela_los_parametros_y_entra_a_la_bandeja(self):
        datos.envia(self.version_id, contexto=self.autor)
        v = self.version()
        self.assertEqual(v["status"], "en_revision")
        self.assertIsNotNone(v["submitted_at"])
        self.assertEqual(v["disease_params"], query(
            "SELECT d.default_params FROM diseases d JOIN scenarios s ON s.disease_id = d.id WHERE s.id = %s",
            (self.scenario_id,), one=True)["default_params"])
        self.assertEqual(self.asiento()["data_after"]["status"], "en_revision")
        self.assertIn(self.scenario_id, [p["scenario_id"] for p in datos.pendientes()])
        with self.assertRaises(ErrorAPI) as error:
            datos.envia(self.version_id, contexto=self.autor)
        self.assertEqual(error.exception.estado, 409)

    def test_enviar_congela_el_catalogo_con_los_ajustes_encima(self):
        # 044, D59: la foto es el catálogo con los ajustes de la versión; la bandeja los cuenta.
        escribe("UPDATE scenario_versions SET param_overrides = %s::jsonb WHERE id = %s",
                ('{"r0": {"valor": 3.2, "fuente": null, "supuesto": true}}', self.version_id))
        datos.envia(self.version_id, contexto=self.autor)
        catalogo = query("SELECT d.default_params FROM diseases d JOIN scenarios s ON s.disease_id = d.id "
                         "WHERE s.id = %s", (self.scenario_id,), one=True)["default_params"]
        foto = self.version()["disease_params"]
        self.assertEqual(foto["r0"], {"valor": 3.2, "fuente": None, "supuesto": True})
        self.assertEqual({k: v for k, v in foto.items() if k != "r0"},
                         {k: v for k, v in catalogo.items() if k != "r0"})
        pendiente = next(p for p in datos.pendientes() if p["scenario_id"] == self.scenario_id)
        self.assertEqual(pendiente["n_ajustes"], 1)

    def test_devolver_la_regresa_a_borrador_editable_con_el_motivo(self):
        datos.envia(self.version_id, contexto=self.autor)
        self.assertEqual(datos.resuelve(self.version_id, "devolver", "Falta la fuente", contexto=self.revisor),
                         "borrador")
        v = self.version()
        self.assertEqual((v["status"], v["submitted_at"], v["reviewed_by"], v["reviewed_at"], v["disease_params"],
                          v["review_comment"]), ("borrador", None, None, None, None, "Falta la fuente"))
        despues = self.asiento()["data_after"]
        self.assertEqual((despues["decision"], despues["status"]), ("devolver", "borrador"))
        self.assertNotIn(self.scenario_id, [p["scenario_id"] for p in datos.pendientes()])
        datos.envia(self.version_id, contexto=self.autor)        # se corrige y se reenvía
        self.assertEqual(self.version()["status"], "en_revision")

    def test_aprobar_guarda_la_firma(self):
        datos.envia(self.version_id, contexto=self.autor)
        self.assertEqual(datos.resuelve(self.version_id, "aprobar", "", contexto=self.revisor, huella=HUELLA),
                         "aprobado")
        v = self.version()
        self.assertEqual((v["status"], v["reviewed_by"], v["approval_sha256"]),
                         ("aprobado", self.revisor.user_id, HUELLA))
        self.assertEqual(self.asiento()["data_after"]["approval_sha256"], HUELLA)
        firma = datos.firma(self.version_id)
        self.assertEqual((firma["approval_sha256"], firma["corridas"]),
                         (HUELLA, {"coinciden": 0, "distintas": 0, "sin_huella": 0}))
        self.assertIsNone(datos.firma(-1))

    def test_nadie_resuelve_lo_que_creo_y_un_rechazo_exige_motivo_en_la_base(self):
        datos.envia(self.version_id, contexto=self.autor)
        with self.assertRaises(ErrorAPI) as error:
            datos.resuelve(self.version_id, "devolver", "x", contexto=self.autor)
        self.assertEqual(error.exception.estado, 409)
        with self.assertRaises(ErrorAPI) as error:
            datos.resuelve(self.version_id, "rechazar", "", contexto=self.revisor)
        self.assertEqual(error.exception.estado, 409)           # ck_scenario_versions_revision
        self.assertEqual(self.version()["status"], "en_revision")

    def test_la_firma_solo_cabe_en_una_aprobada(self):
        with self.assertRaises(psycopg2.errors.CheckViolation):
            escribe("UPDATE scenario_versions SET approval_sha256 = %s WHERE id = %s", (HUELLA, self.version_id))

    def test_un_escenario_archivado_no_se_envia(self):
        escribe("UPDATE scenarios SET status = 'archivado' WHERE id = %s", (self.scenario_id,))
        with self.assertRaises(ErrorAPI) as error:
            datos.envia(self.version_id, contexto=self.autor)
        self.assertEqual(error.exception.estado, 409)
        self.assertEqual(self.version()["status"], "borrador")
