import unittest

from epidemia_comun.bd import query
from microservicios.poblacion import datos
from microservicios.pruebas_bd import contexto_de_prueba, escribe, tiene_base

CODIGO = "19001"   # Abasolo


# Contra la base de pruebas, con la 043. Ajusta Abasolo y lo deja como estaba: cifras, ajustes y
# versiones. La bitácora se queda: es de solo inserción.
@unittest.skipUnless(tiene_base(), "Requiere la base de pruebas")
class PoblacionBdTests(unittest.TestCase):
    def setUp(self):
        fila = query("SELECT r.id, r.population, r.parent_region_id FROM regions r WHERE r.code = %s",
                     (CODIGO,), one=True)
        self.region_id, self.poblacion, self.estado_id = fila["id"], fila["population"], fila["parent_region_id"]
        self.estado = query("SELECT population FROM regions WHERE id = %s", (self.estado_id,), one=True)["population"]
        self.bandas = {f["age_group"]: f["population"] for f in query(
            "SELECT age_group, population FROM region_age_groups WHERE region_id IN (%s)", (self.region_id,))}
        self.bandas_estado = {f["age_group"]: f["population"] for f in query(
            "SELECT age_group, population FROM region_age_groups WHERE region_id = %s", (self.estado_id,))}
        self.contexto = contexto_de_prueba(query("SELECT min(id) AS id FROM users", one=True)["id"])
        # Las versiones no se borran (D52): otras pruebas que corrigen población (la web) pueden dejar
        # las del estado. Se empieza sin ninguna de estas dos regiones.
        escribe("DELETE FROM population_versions WHERE region_id IN (%s, %s)", (self.region_id, self.estado_id))
        self.addCleanup(self.regresa)

    def regresa(self):
        escribe("DELETE FROM population_versions WHERE region_id IN (%s, %s)", (self.region_id, self.estado_id))
        escribe("DELETE FROM region_population_adjustments WHERE region_id = %s", (self.region_id,))
        escribe("UPDATE regions SET population = %s WHERE id = %s", (self.poblacion, self.region_id))
        escribe("UPDATE regions SET population = %s WHERE id = %s", (self.estado, self.estado_id))
        for region, bandas in ((self.region_id, self.bandas), (self.estado_id, self.bandas_estado)):
            for grupo, n in bandas.items():
                escribe("UPDATE region_age_groups SET population = %s WHERE region_id = %s AND age_group = %s",
                        (n, region, grupo))

    def test_sin_ajustes_la_version_1_es_el_censo(self):
        (v1,) = datos.versiones(self.region_id)
        self.assertEqual((v1["version"], v1["population"], v1["reference_year"]), (1, self.poblacion, 2020))
        self.assertTrue(v1["source"].startswith("INEGI"))

    def test_un_ajuste_guarda_la_version_1_y_la_2_del_municipio_y_del_estado(self):
        ok, error, resultado = datos.actualiza_poblacion_municipio(
            self.region_id, self.poblacion + 100, "Prueba de versiones", self.poblacion, contexto=self.contexto)
        self.assertTrue(ok, error)
        self.assertEqual(resultado["version"], 2)
        dos, uno = datos.versiones(self.region_id)
        self.assertEqual((uno["population"], uno["reason"]), (self.poblacion, None))
        self.assertEqual((dos["population"], dos["reason"]), (self.poblacion + 100, "Prueba de versiones"))
        self.assertEqual(dos["age_groups"].keys(), uno["age_groups"].keys())
        estado = datos.versiones(self.estado_id)
        self.assertEqual([v["population"] for v in estado], [self.estado + 100, self.estado])
        ok, error, _ = datos.actualiza_poblacion_municipio(
            self.region_id, self.poblacion + 200, "Otra", self.poblacion, contexto=self.contexto)
        self.assertFalse(ok)
        self.assertIn("mientras editabas", error)

    def test_corregir_bandas_tambien_versiona(self):
        grupos = dict(self.bandas)
        sin_edad = grupos.pop("edad_no_especificada")
        nuevos = dict(grupos, **{"0-19": grupos["0-19"] - 1, "20-39": grupos["20-39"] + 1})
        ok, error, resultado = datos.actualiza_grupos_edad_municipio(
            self.region_id, nuevos, dict(grupos, edad_no_especificada=sin_edad), "Reclasificación",
            contexto=self.contexto)
        self.assertTrue(ok, error)
        dos = datos.versiones(self.region_id)[0]
        self.assertEqual((dos["version"], dos["age_groups"]["0-19"]), (2, grupos["0-19"] - 1))
        self.assertEqual(datos.versiones(self.estado_id)[0]["version"], 2)

    def test_los_periodos_de_referencia(self):
        periodos = datos.periodos(CODIGO)
        self.assertEqual([p["anio"] for p in periodos], [1990, 1995, 2000, 2005, 2010, 2015, 2020])
        self.assertEqual(periodos[-1]["poblacion"], self.poblacion)
        self.assertEqual(len(datos.periodos("19")), 7)
