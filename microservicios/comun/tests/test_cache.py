from datetime import date, datetime, timezone
from decimal import Decimal

from epidemia_comun import cache, llaves

from .base import ConRedis


class Cache(ConRedis):
    def setUp(self):
        super().setUp()
        self.llamadas = 0

    def _calcula(self, datos):
        def calcular():
            self.llamadas += 1
            return datos
        return calcular

    def test_la_segunda_vez_no_calcula(self):
        datos = [{"municipio": "Monterrey", "casos": 3}]
        self.assertEqual(cache.obtener("zonas", "pagina=1", 60, self._calcula(datos)), datos)
        self.assertEqual(cache.obtener("zonas", "pagina=1", 60, self._calcula(None)), datos)
        self.assertEqual(self.llamadas, 1)
        self.assertTrue(0 < self.r.ttl(llaves.cache("zonas", "pagina=1")) <= 60)

    def test_otra_clave_calcula_aparte(self):
        cache.obtener("zonas", "pagina=1", 60, self._calcula([1]))
        self.assertEqual(cache.obtener("zonas", "pagina=2", 60, self._calcula([2])), [2])
        self.assertEqual(cache.obtener("series", "pagina=1", 60, self._calcula([3])), [3])
        self.assertEqual(self.llamadas, 3)

    def test_regresa_los_mismos_tipos_que_la_base(self):
        datos = {
            "tasa": Decimal("0.125"),
            "dia": date(2026, 10, 12),
            "corrida": datetime(2026, 10, 12, 8, 30, tzinfo=timezone.utc),
            "serie": [{"casos": 4, "fecha": date(2026, 10, 1), "r0": 1.5}],
            "municipio": "Agualeguas, Doctor González",
            "vacio": None,
        }
        cache.obtener("resultados", "7", 60, self._calcula(datos))
        leido = cache.obtener("resultados", "7", 60, self._calcula(None))
        self.assertEqual(leido, datos)
        self.assertIs(type(leido["tasa"]), Decimal)
        self.assertIs(type(leido["dia"]), date)
        self.assertIs(type(leido["corrida"]), datetime)
        self.assertEqual(leido["corrida"].tzinfo, timezone.utc)
        self.assertIs(type(leido["serie"][0]["r0"]), float)
        self.assertEqual(self.llamadas, 1)

    def test_tambien_guarda_un_none(self):
        cache.obtener("resultados", "8", 60, self._calcula(None))
        self.assertIsNone(cache.obtener("resultados", "8", 60, self._calcula("otro")))
        self.assertEqual(self.llamadas, 1)

    def test_lo_corrupto_se_vuelve_a_calcular(self):
        self.r.set(llaves.cache("zonas", "x"), "no es json")
        self.assertEqual(cache.obtener("zonas", "x", 60, self._calcula([1])), [1])
        self.assertEqual(cache.obtener("zonas", "x", 60, self._calcula([2])), [1])

    def test_un_tipo_que_no_sabe_guardar_es_error(self):
        with self.assertRaises(TypeError):
            cache.obtener("zonas", "x", 60, self._calcula({"ids": {1, 2}}))
