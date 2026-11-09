"""
Evidencias de backend_web/evidencias.py, que escribe el microservicio evidencias.

Ejecutar:
    python -m unittest backend_web.tests.test_evidencias -v
"""
import hashlib
import os
import tempfile
import unittest
import uuid
from pathlib import Path

import psycopg2.errors

from backend_web import evidencias
from backend_web.db import query
from backend_web.tests.base import contexto_de_prueba, escribe, id_de_usuario, requiere_base

JPEG = b"\xff\xd8\xff\xe0" + os.urandom(64)
PNG = b"\x89PNG\r\n\x1a\n" + os.urandom(64)


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


@requiere_base
class EvidenciasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.karla = id_de_usuario("karla.trevino")
        cls.admin = id_de_usuario("admin")
        cls.catalogo = query("SELECT (SELECT min(id) FROM diseases) AS disease_id, "
                             "(SELECT min(id) FROM regions) AS region_id", one=True)

    def setUp(self):
        self.casos = []
        temporal = tempfile.TemporaryDirectory(prefix="evidencias-")
        self.addCleanup(temporal.cleanup)
        self.carpeta = Path(temporal.name)

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
        return evidencias.guardar_evidencia(case_id, datos, self.karla, self.carpeta,
                                            contexto=contexto_de_prueba(self.karla))

    def _bitacora(self, evidencia_id):
        return query("""SELECT action, data_before, data_after FROM audit_log
                        WHERE entity_type = 'case_attachments' AND entity_id = %s ORDER BY id""",
                     (str(evidencia_id),))

    def test_get_caso_con_quien_lo_reporto(self):
        case_id = self._caso()
        self.assertEqual(evidencias.get_caso(case_id), {"id": case_id, "reported_by": self.karla})
        self.assertIsNone(evidencias.get_caso(-1))

    def test_guardar_escribe_el_archivo_y_su_registro(self):
        case_id = self._caso()
        fila, creada = self._guarda(case_id)
        self.assertTrue(creada)
        self.assertEqual((fila["case_id"], fila["mime_type"], fila["size_bytes"], fila["privacy"]),
                         (case_id, "image/jpeg", len(JPEG), "privado"))
        self.assertEqual(fila["sha256"], hashlib.sha256(JPEG).hexdigest())
        self.assertNotIn("storage_path", fila)
        _, ruta = evidencias.archivo_de_evidencia(fila["id"], self.carpeta)
        self.assertEqual(ruta.read_bytes(), JPEG)
        self.assertEqual(ruta.suffix, ".jpg")
        [evento] = self._bitacora(fila["id"])
        self.assertEqual(evento["action"], "CREATE")
        self.assertEqual(evento["data_after"]["sha256"], fila["sha256"])

    def test_la_misma_foto_en_el_mismo_caso_no_se_duplica(self):
        case_id, otro = self._caso(), self._caso()
        primera, _ = self._guarda(case_id)
        repetida, creada = self._guarda(case_id)
        self.assertFalse(creada)
        self.assertEqual(repetida["id"], primera["id"])
        self.assertEqual(len(list(self.carpeta.rglob("*.jpg"))), 1)
        # En otro caso sí es otra evidencia.
        _, creada = self._guarda(otro)
        self.assertTrue(creada)
        self.assertEqual([e["id"] for e in evidencias.listar_evidencias(case_id)], [primera["id"]])

    def test_si_el_registro_falla_el_archivo_no_se_queda(self):
        with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
            self._guarda(-1, PNG)
        self.assertEqual(list(self.carpeta.rglob("*.png")), [])

    def test_borrar_quita_registro_y_archivo(self):
        case_id = self._caso()
        fila, _ = self._guarda(case_id, PNG)
        _, ruta = evidencias.archivo_de_evidencia(fila["id"], self.carpeta)
        borrada = evidencias.borrar_evidencia(fila["id"], self.carpeta,
                                              contexto=contexto_de_prueba(self.admin))
        self.assertEqual(borrada["id"], fila["id"])
        self.assertFalse(ruta.exists())
        self.assertIsNone(evidencias.get_evidencia(fila["id"]))
        evento = self._bitacora(fila["id"])[-1]
        self.assertEqual(evento["action"], "DELETE")
        self.assertEqual(evento["data_before"]["sha256"], fila["sha256"])
        self.assertIsNone(evidencias.borrar_evidencia(fila["id"], self.carpeta,
                                                      contexto=contexto_de_prueba(self.admin)))
        self.assertEqual(evidencias.archivo_de_evidencia(fila["id"], self.carpeta), (None, None))


if __name__ == "__main__":
    unittest.main()
