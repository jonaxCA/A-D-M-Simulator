"""
Prueba PURA (sin PostgreSQL) de que las 6 enfermedades del catalogo quedan
simulables despues de las migraciones 017 y 023.

No corre SQL contra ninguna base: parsea el JSON que cada migracion inserta
con el operador `||` directamente del archivo .sql (con una expresion
regular + json.loads, no un parser de SQL) y lo fusiona en Python sobre la
base que tenia cada enfermedad ANTES de esa migracion -- el mismo escenario
que resuelve el `WHERE code = '...' AND NOT (default_params ? 'r0')` de cada
UPDATE. El resultado se valida con `backend_web.queries.estado_parametros()`,
la misma funcion que usa la pantalla del catalogo para decidir si una
enfermedad es simulable, asi que esta prueba corre en cualquier maquina sin
levantar PostgreSQL.

Ejecutar:
    python -m unittest backend_web.tests.test_parametros_enfermedades -v
"""
import json
import pathlib
import re
import unittest

from backend_web.queries import PARAMETROS_SIMULACION, estado_parametros

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MIGRACIONES = RAIZ / "datos" / "postgres" / "migraciones"

RANGOS = {p["clave"]: (p["min"], p["max"]) for p in PARAMETROS_SIMULACION}
CLAVES_SIMULACION = set(RANGOS)

# Un UPDATE ... default_params || '{...}'::jsonb ... WHERE code = 'CODIGO'
# por enfermedad, en el mismo orden en que aparece en el archivo.
_PATRON_BLOQUE = re.compile(
    r"default_params\s*=\s*default_params\s*\|\|\s*'(\{.*?\})'::jsonb"
    r".*?WHERE\s+code\s*=\s*'([A-Z0-9_]+)'",
    re.S,
)


def _bloques_jsonb(archivo):
    """{codigo_enfermedad: dict} para cada bloque que agrega esa migracion."""
    texto = (MIGRACIONES / archivo).read_text(encoding="utf-8")
    bloques = {}
    for crudo, codigo in _PATRON_BLOQUE.findall(texto):
        bloques[codigo] = json.loads(crudo)
    return bloques


# Lo que ya tenia cada enfermedad ANTES de la migracion 023, tal como lo
# dejaron 010_datos_iniciales.sql (PATOGENO_X, vacio) y el
# demo_datos_nl.sql anterior a este cambio (dengue/zika/malaria, en el
# formato "dist" que el motor lee pero que no cuenta como fuente -- ver
# backend_web/queries.py:_desarma_param). Sirve para probar el caso real
# que 023 tiene que resolver: una base que ya tenia la fila creada por una
# instalacion anterior.
BASES_ANTERIORES_A_023 = {
    "PATOGENO_X": {},
    "DENGUE_DEMO": {
        "incubacion_dias": {"dist": "lognormal", "media": 5.5, "desv": 1.5},
        "infeccioso_dias": {"dist": "lognormal", "media": 5.0, "desv": 1.0},
        "prob_asintomatico": 0.60, "transmisibilidad_base": 0.015,
    },
    "ZIKA_DEMO": {
        "incubacion_dias": {"dist": "lognormal", "media": 6.0, "desv": 2.0},
        "infeccioso_dias": {"dist": "lognormal", "media": 5.0, "desv": 1.5},
        "prob_asintomatico": 0.80, "transmisibilidad_base": 0.010,
    },
    "MALARIA_DEMO": {
        "incubacion_dias": {"dist": "lognormal", "media": 12.0, "desv": 3.0},
        "infeccioso_dias": {"dist": "lognormal", "media": 14.0, "desv": 4.0},
        "prob_asintomatico": 0.20, "transmisibilidad_base": 0.008,
    },
}

# Migracion 017 ya deja INFLUENZA_ESTACIONAL y SARS_COV_2_ANCESTRAL con sus
# seis parametros dentro del mismo bloque (010 no les cargaba ninguno), asi
# que su "base anterior" es simplemente vacia.
BASES_ANTERIORES_A_017 = {
    "INFLUENZA_ESTACIONAL": {},
    "SARS_COV_2_ANCESTRAL": {},
}


class Migracion023Tests(unittest.TestCase):
    """Lo que agrega 023_parametros_enfermedades_restantes.sql."""

    @classmethod
    def setUpClass(cls):
        cls.bloques = _bloques_jsonb("023_parametros_enfermedades_restantes.sql")

    def test_trae_las_cuatro_enfermedades_pendientes(self):
        self.assertEqual(set(self.bloques), set(BASES_ANTERIORES_A_023))

    def test_cada_bloque_solo_agrega_claves_que_el_motor_reconoce(self):
        for codigo, bloque in self.bloques.items():
            self.assertTrue(set(bloque) <= CLAVES_SIMULACION,
                             f"{codigo} agrega claves fuera de PARAMETROS_SIMULACION: {set(bloque)}")

    def test_patogeno_x_trae_los_seis_de_una_vez(self):
        # Es el unico de los cuatro que partia de '{}': todo lo demas ya
        # tenia incubacion/infeccioso desde el demo.
        self.assertEqual(set(self.bloques["PATOGENO_X"]), CLAVES_SIMULACION)

    def test_cada_parametro_trae_fuente_o_supuesto_explicito(self):
        # La regla dura del proyecto (backend_web/queries.py:parametros_desde_form):
        # nunca un valor sin fuente y sin marca de supuesto.
        for codigo, bloque in self.bloques.items():
            for clave, entrada in bloque.items():
                self.assertIsInstance(entrada, dict, f"{codigo}.{clave}")
                self.assertIn("valor", entrada, f"{codigo}.{clave} sin 'valor'")
                self.assertIn("supuesto", entrada, f"{codigo}.{clave} sin marca de supuesto")
                if not entrada["supuesto"]:
                    self.assertTrue(entrada.get("fuente"),
                                     f"{codigo}.{clave}: no es supuesto y no tiene fuente")
                else:
                    self.assertTrue(entrada.get("fuente"),
                                     f"{codigo}.{clave}: supuesto sin explicacion en 'fuente'")

    def test_valores_dentro_del_rango_del_formulario(self):
        for codigo, bloque in self.bloques.items():
            for clave, entrada in bloque.items():
                minimo, maximo = RANGOS[clave]
                valor = entrada["valor"]
                self.assertTrue(minimo <= valor <= maximo,
                                 f"{codigo}.{clave}={valor} fuera de [{minimo}, {maximo}]")

    def test_tasas_y_letalidad_son_probabilidades_validas(self):
        # r0 puede superar 1; tasa_hospitalizacion y letalidad no (son
        # fracciones de infectados, ver motor/parametros.py:tasa_por_grupo).
        for codigo, bloque in self.bloques.items():
            for clave in ("tasa_hospitalizacion", "letalidad"):
                if clave in bloque:
                    self.assertTrue(0 <= bloque[clave]["valor"] <= 1, f"{codigo}.{clave}")

    def test_fusion_sobre_una_base_existente_deja_simulable(self):
        """El caso real: una base que instalo dengue/zika/malaria/patogeno x
        antes de que existiera esta migracion. `||` fusiona (las claves del
        bloque nuevo ganan) y el resultado tiene que quedar simulable."""
        for codigo, base in BASES_ANTERIORES_A_023.items():
            fusionado = {**base, **self.bloques[codigo]}
            estado = estado_parametros(fusionado)
            self.assertEqual(estado["faltan"], [], f"{codigo}: {estado['faltan']}")
            self.assertTrue(estado["simulable"], codigo)

    def test_no_se_pisa_un_r0_ya_capturado_desde_la_pantalla(self):
        """Replica en Python la guarda SQL `NOT (default_params ? 'r0')`:
        si la enfermedad ya tiene r0 (lo capturo alguien desde la pantalla),
        el bloque de la migracion no debe aplicarse."""
        capturado = dict(BASES_ANTERIORES_A_023["DENGUE_DEMO"])
        capturado["r0"] = {"valor": 9.99, "fuente": "Capturado a mano desde /enfermedades", "supuesto": False}

        # Misma condicion que el WHERE de la migracion.
        aplica_migracion = "r0" not in capturado
        resultado = ({**capturado, **self.bloques["DENGUE_DEMO"]} if aplica_migracion
                     else capturado)

        self.assertFalse(aplica_migracion)
        self.assertEqual(resultado["r0"]["valor"], 9.99)
        self.assertEqual(resultado["r0"]["fuente"], "Capturado a mano desde /enfermedades")


class SeisEnfermedadesSimulablesTests(unittest.TestCase):
    """Con 017 + 023, las 6 enfermedades del catalogo quedan simulables --
    el objetivo final del pendiente de la checklist (Bloque E)."""

    CODIGOS_ESPERADOS = {
        "INFLUENZA_ESTACIONAL", "SARS_COV_2_ANCESTRAL",
        "DENGUE_DEMO", "ZIKA_DEMO", "MALARIA_DEMO", "PATOGENO_X",
    }

    @classmethod
    def setUpClass(cls):
        cls.bloques_017 = _bloques_jsonb("017_parametros_enfermedades.sql")
        cls.bloques_023 = _bloques_jsonb("023_parametros_enfermedades_restantes.sql")

    def test_017_mas_023_cubren_las_seis_enfermedades_del_catalogo(self):
        codigos = set(self.bloques_017) | set(self.bloques_023)
        self.assertEqual(codigos, self.CODIGOS_ESPERADOS)

    def test_las_seis_quedan_simulables(self):
        bases = {**BASES_ANTERIORES_A_017, **BASES_ANTERIORES_A_023}
        bloques = {**self.bloques_017, **self.bloques_023}
        for codigo in self.CODIGOS_ESPERADOS:
            fusionado = {**bases[codigo], **bloques[codigo]}
            estado = estado_parametros(fusionado)
            with self.subTest(enfermedad=codigo):
                self.assertEqual(estado["faltan"], [])
                self.assertTrue(estado["simulable"])

    def test_dengue_zika_malaria_quedan_marcadas_como_transmision_por_vector_supuesta(self):
        # No es solo que simulen: r0 en las tres tiene que seguir marcado
        # como supuesto (el motor es de persona a persona, ver el header de
        # 023_parametros_enfermedades_restantes.sql), para que la pantalla lo
        # muestre y nadie confunda el R0 de vector con un dato validado.
        for codigo in ("DENGUE_DEMO", "ZIKA_DEMO", "MALARIA_DEMO"):
            self.assertTrue(self.bloques_023[codigo]["r0"]["supuesto"], codigo)


if __name__ == "__main__":
    unittest.main()
