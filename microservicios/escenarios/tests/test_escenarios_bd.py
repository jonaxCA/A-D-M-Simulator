import unittest
import uuid
from datetime import date

import psycopg2

from epidemia_comun.bd import query
from epidemia_comun.errores import ErrorAPI
from microservicios.escenarios import datos
from microservicios.pruebas_bd import contexto_de_prueba, escribe, tiene_base


# Contra la base de pruebas, con la 064. Usa el escenario de la semilla y deja todo como estaba:
# su estado, su proyecto y su versión. La bitácora se queda: es de solo inserción.
@unittest.skipUnless(tiene_base(), "Requiere la base de pruebas")
class EscenariosBdTests(unittest.TestCase):
    def setUp(self):
        self.escenario = query("""SELECT s.id, s.status, s.is_public, s.project_id, s.disease_id,
                                         s.region_id, v.id AS version_id, v.status AS version_status,
                                         v.submitted_at, v.reviewed_by, v.reviewed_at
                                  FROM scenarios s JOIN scenario_versions v
                                    ON v.scenario_id = s.id AND v.is_current
                                  ORDER BY s.id LIMIT 1""", one=True)
        self.user_id = query("SELECT min(id) AS id FROM users", one=True)["id"]
        self.contexto = contexto_de_prueba(self.user_id)
        self.nombre = "PRUEBA " + uuid.uuid4().hex[:10]
        e = self.escenario
        self.addCleanup(escribe, "DELETE FROM research_projects WHERE name LIKE %s", (self.nombre + "%",))
        self.addCleanup(escribe, "UPDATE scenarios SET status = %s, is_public = %s, project_id = %s WHERE id = %s",
                        (e["status"], e["is_public"], e["project_id"], e["id"]))
        self.addCleanup(self.regresa_version)

    def regresa_version(self):
        e = self.escenario
        escribe("UPDATE scenario_versions SET status = %s, submitted_at = %s, reviewed_by = %s, reviewed_at = %s "
                "WHERE id = %s", (e["version_status"], e["submitted_at"], e["reviewed_by"], e["reviewed_at"],
                                  e["version_id"]))

    def proyecto(self, **cambios):
        valores = dict(name=self.nombre + cambios.pop("sufijo", ""), objective=None,
                       disease_id=self.escenario["disease_id"], region_id=self.escenario["region_id"],
                       period_start=date(2026, 1, 1), period_end=date(2026, 6, 30), engines=["seir-ref"])
        valores.update(cambios)
        return datos.crea_proyecto(valores, contexto=self.contexto)

    def asiento(self, entidad, entity_id):
        return query("""SELECT data_before, data_after FROM audit_log WHERE entity_type = %s
                        AND entity_id = %s ORDER BY id DESC LIMIT 1""", (entidad, str(entity_id)), one=True)

    def test_crear_listar_y_cambiar_un_proyecto(self):
        project_id = self.proyecto()
        fila = datos.proyecto(project_id)
        self.assertEqual((fila["status"], fila["engines"], fila["n_escenarios"]), ("activo", ["seir-ref"], 0))
        self.assertEqual(self.asiento("research_projects", project_id)["data_after"]["name"], self.nombre)
        self.assertIn(project_id, [p["id"] for p in datos.proyectos("activo", self.nombre)])
        self.assertNotIn(project_id, [p["id"] for p in datos.proyectos(regiones=[-1])])
        with self.assertRaises(ErrorAPI) as error:
            self.proyecto()
        self.assertEqual(error.exception.estado, 409)
        datos.cambia_proyecto(project_id, {"period_end": date(2026, 12, 31)}, contexto=self.contexto)
        self.assertEqual(datos.proyecto(project_id)["period_end"], date(2026, 12, 31))
        with self.assertRaises(ErrorAPI) as error:
            datos.cambia_proyecto(project_id, {"period_end": date(2025, 1, 1)}, contexto=self.contexto)
        self.assertEqual(error.exception.estado, 422)
        datos.cambia_estado_proyecto(project_id, "archivado", contexto=self.contexto)
        with self.assertRaises(ErrorAPI) as error:
            datos.cambia_proyecto(project_id, {"objective": "x"}, contexto=self.contexto)
        self.assertEqual(error.exception.estado, 409)

    def test_un_escenario_entra_solo_a_un_proyecto_activo_de_su_enfermedad_y_region(self):
        e = self.escenario
        otra = query("SELECT id FROM diseases WHERE id <> %s ORDER BY id LIMIT 1", (e["disease_id"],), one=True)["id"]
        ajeno = self.proyecto(sufijo=" otra", disease_id=otra)
        with self.assertRaises(ErrorAPI) as error:
            datos.asigna_proyecto(e["id"], ajeno, contexto=self.contexto)
        self.assertEqual(error.exception.estado, 422)
        with self.assertRaises(psycopg2.errors.CheckViolation):   # y la base también lo impide
            escribe("UPDATE scenarios SET project_id = %s WHERE id = %s", (ajeno, e["id"]))
        propio = self.proyecto()
        datos.asigna_proyecto(e["id"], propio, contexto=self.contexto)
        self.assertEqual(datos.escenarios([e["id"]])[e["id"]]["project_id"], propio)
        self.assertEqual(datos.proyecto(propio)["n_escenarios"], 1)
        self.assertEqual([x["id"] for x in datos.escenarios_de(propio)], [e["id"]])
        self.assertEqual(self.asiento("scenarios", e["id"])["data_after"], {"project_id": propio})
        datos.asigna_proyecto(e["id"], None, contexto=self.contexto)
        datos.cambia_estado_proyecto(propio, "archivado", contexto=self.contexto)
        with self.assertRaises(ErrorAPI) as error:
            datos.asigna_proyecto(e["id"], propio, contexto=self.contexto)
        self.assertEqual(error.exception.estado, 409)

    def test_archivar_quita_lo_publico_y_la_base_no_deja_correrlo(self):
        e = self.escenario
        escribe("UPDATE scenario_versions SET status = 'en_revision', submitted_at = coalesce(submitted_at, now()), "
                "reviewed_by = NULL, reviewed_at = NULL WHERE id = %s", (e["version_id"],))
        with self.assertRaises(ErrorAPI) as error:
            datos.archiva(e["id"], True, contexto=self.contexto)
        self.assertEqual(error.exception.estado, 409)
        self.regresa_version()
        datos.archiva(e["id"], True, contexto=self.contexto)
        fila = query("SELECT status, is_public FROM scenarios WHERE id = %s", (e["id"],), one=True)
        self.assertEqual((fila["status"], fila["is_public"]), ("archivado", False))
        self.assertEqual(self.asiento("scenarios", e["id"])["data_after"], {"status": "archivado", "is_public": False})
        if e["version_status"] == "aprobado":
            with self.assertRaises(psycopg2.errors.RestrictViolation) as error:
                escribe("INSERT INTO simulation_runs (scenario_version_id) VALUES (%s)", (e["version_id"],))
            self.assertIn("archivado", str(error.exception))
        with self.assertRaises(ErrorAPI):
            datos.archiva(e["id"], True, contexto=self.contexto)
        datos.archiva(e["id"], False, contexto=self.contexto)
        self.assertEqual(datos.escenarios([e["id"]])[e["id"]]["status"], "borrador")

    def test_el_historial_trae_los_responsables(self):
        (version,) = [v for v in datos.versiones(self.escenario["id"]) if v["id"] == self.escenario["version_id"]]
        self.assertTrue({"created_by", "autor", "revisor", "submitted_at", "reviewed_at", "devuelta",
                         "approval_sha256"} <= set(version))
