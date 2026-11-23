"""Evidencias (datos.py) y reportes (reportes.py) contra la base de pruebas, con los archivos
en disco (epidemia_comun.archivos). Antes vivían en backend_web/tests/test_evidencias.py (E8)."""
import hashlib
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

import psycopg2.errors

from epidemia_comun import archivos
from epidemia_comun.bd import get_conn, query
from microservicios.evidencias import datos as evidencias
from microservicios.evidencias import reportes
from microservicios.pruebas_bd import contexto_de_prueba, escribe, id_de_usuario, tiene_base

requiere_base = unittest.skipUnless(tiene_base(), "Requiere la base de pruebas")

JPEG = b"\xff\xd8\xff\xe0" + os.urandom(64)
PNG = b"\x89PNG\r\n\x1a\n" + os.urandom(64)
PDF = b"%PDF-1.7\n" + os.urandom(64)


class EnDisco(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory(prefix="archivos-")
        self.addCleanup(temporal.cleanup)
        self.carpeta = Path(temporal.name)
        entorno = mock.patch.dict(os.environ, {"ARCHIVOS": "disco", "ARCHIVOS_DIR": temporal.name})
        entorno.start()
        self.addCleanup(entorno.stop)

    def objetos(self, patron="*"):
        return [p for p in self.carpeta.rglob(patron) if p.is_file()]


class TipoYValidacionTests(unittest.TestCase):
    def test_el_tipo_sale_del_contenido(self):
        self.assertEqual(evidencias.tipo_por_contenido(JPEG), "image/jpeg")
        self.assertEqual(evidencias.tipo_por_contenido(PNG), "image/png")
        self.assertEqual(evidencias.tipo_por_contenido(b"RIFF\x00\x00\x00\x00WEBPVP8 "), "image/webp")
        self.assertEqual(evidencias.tipo_por_contenido(b"%PDF-1.7\n"), "application/pdf")
        self.assertIsNone(evidencias.tipo_por_contenido(b"GIF89a"))
        self.assertIsNone(evidencias.tipo_por_contenido(b"--frontera\r\nContent-Disposition: form-data"))

    def test_validacion(self):
        self.assertEqual(evidencias.valida_archivo(JPEG), [])
        self.assertEqual(len(evidencias.valida_archivo(b"")), 1)
        self.assertEqual(len(evidencias.valida_archivo(b"MZ ejecutable")), 1)
        self.assertEqual(len(evidencias.valida_archivo(JPEG + b"0" * evidencias.MAXIMO)), 1)
        self.assertEqual(len(evidencias.valida_archivo(JPEG, tipos=reportes.TIPOS)), 1)

    def test_huella(self):
        huella = hashlib.sha256(JPEG).hexdigest()
        self.assertEqual(evidencias.valida_archivo(JPEG, huella), [])
        self.assertEqual(evidencias.valida_archivo(JPEG, " %s " % huella.upper()), [])
        self.assertEqual(len(evidencias.valida_archivo(JPEG, hashlib.sha256(PNG).hexdigest())), 1)
        self.assertEqual(len(evidencias.valida_archivo(JPEG, "abc")), 1)

    def test_corridas_y_titulo(self):
        self.assertEqual(reportes.valida_corridas("12, 15,12"), ([12, 15], []))
        for texto in (None, "", "a", "0", "1,-2", ",".join(map(str, range(1, 102)))):
            self.assertEqual(len(reportes.valida_corridas(texto)[1]), 1, texto)
        self.assertEqual(reportes.valida_titulo("  "), (None, []))
        self.assertEqual(len(reportes.valida_titulo("x" * 201)[1]), 1)


@requiere_base
class EvidenciasTests(EnDisco):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.karla = id_de_usuario("karla.trevino")
        cls.admin = id_de_usuario("admin")
        cls.catalogo = query("SELECT (SELECT min(id) FROM diseases) AS disease_id, "
                             "(SELECT min(id) FROM regions) AS region_id", one=True)

    def setUp(self):
        super().setUp()
        self.casos = []

    def tearDown(self):
        # Borrar el caso arrastra sus evidencias (ON DELETE CASCADE).
        for case_id in self.casos:
            escribe("DELETE FROM cases WHERE id = %s", (case_id,))

    def _caso(self):
        local_uuid = str(uuid.uuid4())
        escribe("""INSERT INTO cases (local_uuid, reported_by, disease_id, region_id, report_date)
                   VALUES (%s, %s, %s, %s, current_date)""",
                (local_uuid, self.karla, self.catalogo["disease_id"], self.catalogo["region_id"]))
        case_id = query("SELECT id FROM cases WHERE local_uuid = %s", (local_uuid,), one=True)["id"]
        self.casos.append(case_id)
        return case_id

    def _guarda(self, case_id, datos=JPEG):
        return evidencias.guardar_evidencia(case_id, datos, self.karla,
                                            contexto=contexto_de_prueba(self.karla))

    def _bitacora(self, evidencia_id):
        return query("""SELECT action, data_before, data_after FROM audit_log
                        WHERE entity_type = 'case_attachments' AND entity_id = %s ORDER BY id""",
                     (str(evidencia_id),))

    def test_get_caso_con_quien_lo_reporto(self):
        case_id = self._caso()
        self.assertEqual(evidencias.get_caso(case_id), {"id": case_id, "reported_by": self.karla})
        self.assertIsNone(evidencias.get_caso(-1))

    def test_guardar_sube_el_objeto_y_escribe_su_registro(self):
        case_id = self._caso()
        fila, creada = self._guarda(case_id)
        self.assertTrue(creada)
        self.assertEqual((fila["case_id"], fila["mime_type"], fila["size_bytes"], fila["privacy"]),
                         (case_id, "image/jpeg", len(JPEG), "privado"))
        self.assertEqual(fila["sha256"], hashlib.sha256(JPEG).hexdigest())
        self.assertNotIn("storage_path", fila)
        _, objeto = evidencias.objeto_de_evidencia(fila["id"])
        self.assertTrue(objeto.startswith("evidencias/%d/" % case_id) and objeto.endswith(".jpg"))
        self.assertEqual(archivos.leer(objeto), JPEG)
        [evento] = self._bitacora(fila["id"])
        self.assertEqual(evento["action"], "CREATE")
        self.assertEqual(evento["data_after"]["sha256"], fila["sha256"])

    def test_la_misma_foto_en_el_mismo_caso_no_se_duplica(self):
        case_id, otro = self._caso(), self._caso()
        primera, _ = self._guarda(case_id)
        repetida, creada = self._guarda(case_id)
        self.assertFalse(creada)
        self.assertEqual(repetida["id"], primera["id"])
        self.assertEqual(len(self.objetos("*.jpg")), 1)
        # En otro caso sí es otra evidencia.
        _, creada = self._guarda(otro)
        self.assertTrue(creada)
        self.assertEqual([e["id"] for e in evidencias.listar_evidencias(case_id)], [primera["id"]])

    def test_si_el_registro_falla_el_objeto_no_se_queda(self):
        with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
            self._guarda(-1, PNG)
        self.assertEqual(self.objetos(), [])

    def test_si_el_bucket_falla_no_queda_registro(self):
        case_id = self._caso()
        with mock.patch.object(archivos, "guardar", side_effect=archivos.BucketNoDisponible("x")):
            with self.assertRaises(archivos.BucketNoDisponible):
                self._guarda(case_id)
        self.assertEqual(evidencias.listar_evidencias(case_id), [])

    def test_borrar_quita_registro_y_objeto(self):
        case_id = self._caso()
        fila, _ = self._guarda(case_id, PNG)
        _, objeto = evidencias.objeto_de_evidencia(fila["id"])
        borrada = evidencias.borrar_evidencia(fila["id"], contexto=contexto_de_prueba(self.admin))
        self.assertEqual(borrada["id"], fila["id"])
        with self.assertRaises(FileNotFoundError):
            archivos.leer(objeto)
        self.assertIsNone(evidencias.get_evidencia(fila["id"]))
        evento = self._bitacora(fila["id"])[-1]
        self.assertEqual(evento["action"], "DELETE")
        self.assertEqual(evento["data_before"]["sha256"], fila["sha256"])
        self.assertIsNone(evidencias.borrar_evidencia(fila["id"], contexto=contexto_de_prueba(self.admin)))
        self.assertEqual(evidencias.objeto_de_evidencia(fila["id"]), (None, None))


@requiere_base
class ReportesTests(EnDisco):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.analista = id_de_usuario("admin")
        version = query("SELECT min(id) AS id FROM scenario_versions", one=True)["id"]
        if version is None:
            raise unittest.SkipTest("La base de pruebas no tiene versiones de escenario")
        # Dos corridas encoladas que solo sirven para que el reporte las cite.
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO simulation_runs (scenario_version_id, seed, requested_by)
                               VALUES (%s, 901, %s), (%s, 902, %s) RETURNING id""",
                            (version, cls.analista, version, cls.analista))
                cls.corridas = [f[0] for f in cur.fetchall()]
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        for run_id in getattr(cls, "corridas", []):
            escribe("DELETE FROM simulation_runs WHERE id = %s", (run_id,))
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.reportes = []

    def tearDown(self):
        for reporte_id in self.reportes:
            escribe("DELETE FROM comparison_reports WHERE id = %s", (reporte_id,))

    def _guarda(self, datos=PDF, corridas=None, titulo="Comparación"):
        fila, creado = reportes.guardar_reporte(corridas or self.corridas, datos, titulo, self.analista,
                                                contexto=contexto_de_prueba(self.analista))
        self.reportes.append(fila["id"])
        return fila, creado

    def _bitacora(self, reporte_id):
        return query("""SELECT action, data_before, data_after FROM audit_log
                        WHERE entity_type = 'comparison_reports' AND entity_id = %s ORDER BY id""",
                     (str(reporte_id),))

    def test_corridas_que_faltan(self):
        self.assertEqual(reportes.corridas_que_faltan(self.corridas + [-5]), [-5])

    def test_guardar_sube_el_pdf_y_escribe_su_registro(self):
        fila, creado = self._guarda()
        self.assertTrue(creado)
        self.assertEqual((fila["run_ids"], fila["title"], fila["mime_type"], fila["privacy"]),
                         (self.corridas, "Comparación", "application/pdf", "privado"))
        _, objeto = reportes.objeto_de_reporte(fila["id"])
        self.assertTrue(objeto.startswith("reportes/%d/" % self.corridas[0]))
        self.assertEqual(archivos.leer(objeto), PDF)
        [evento] = self._bitacora(fila["id"])
        self.assertEqual(evento["action"], "CREATE")
        self.assertEqual(evento["data_after"]["run_ids"], self.corridas)

    def test_el_mismo_pdf_con_las_mismas_corridas_no_se_duplica(self):
        primero, _ = self._guarda()
        repetido, creado = self._guarda()
        self.assertFalse(creado)
        self.assertEqual(repetido["id"], primero["id"])
        otro, creado = self._guarda(corridas=self.corridas[:1])
        self.assertTrue(creado)
        self.assertEqual([f["id"] for f in reportes.listar_reportes(self.corridas)], [primero["id"]])
        self.assertEqual({f["id"] for f in reportes.listar_reportes(self.corridas[:1])},
                         {primero["id"], otro["id"]})

    def test_borrar_quita_registro_y_objeto(self):
        fila, _ = self._guarda()
        _, objeto = reportes.objeto_de_reporte(fila["id"])
        borrado = reportes.borrar_reporte(fila["id"], contexto=contexto_de_prueba(self.analista))
        self.assertEqual(borrado["id"], fila["id"])
        with self.assertRaises(FileNotFoundError):
            archivos.leer(objeto)
        self.assertIsNone(reportes.get_reporte(fila["id"]))
        self.assertEqual(self._bitacora(fila["id"])[-1]["action"], "DELETE")
        self.assertIsNone(reportes.borrar_reporte(fila["id"], contexto=contexto_de_prueba(self.analista)))


if __name__ == "__main__":
    unittest.main()
