from unittest import mock

from epidemia_comun import candados, cola, llaves

from .base import ConRedis


class Candados(ConRedis):
    LLAVE = llaves.candado_corrida(12)

    def test_no_se_toma_dos_veces(self):
        with candados.candado(self.LLAVE, 30):
            self.assertTrue(0 < self.r.ttl(self.LLAVE) <= 30)
            with self.assertRaises(candados.CandadoOcupado):
                with candados.candado(self.LLAVE, 30):
                    pass
        self.assertEqual(self.r.exists(self.LLAVE), 0)
        with candados.candado(self.LLAVE, 30):
            pass

    def test_se_suelta_aunque_falle_el_trabajo(self):
        with self.assertRaises(ZeroDivisionError):
            with candados.candado(self.LLAVE, 30):
                1 / 0
        self.assertEqual(self.r.exists(self.LLAVE), 0)

    def test_no_suelta_el_candado_de_otra_peticion(self):
        with candados.candado(self.LLAVE, 30):
            # El candado venció y otra petición lo tomó.
            self.r.set(self.LLAVE, "de-otra-peticion", ex=30)
        self.assertEqual(self.r.get(self.LLAVE), "de-otra-peticion")


class Cola(ConRedis):
    LLAVE = llaves.cola_simulaciones("python-ref")

    def test_sale_en_el_orden_en_que_entro(self):
        cola.encolar(self.LLAVE, 1)
        cola.encolar(self.LLAVE, 2)
        self.assertEqual(cola.pendientes(self.LLAVE), 2)
        self.assertEqual(cola.tomar(self.LLAVE), "1")
        self.assertEqual(cola.tomar(self.LLAVE), "2")
        self.assertEqual(cola.pendientes(self.LLAVE), 0)

    def test_vacia_regresa_none_al_terminar_la_espera(self):
        with mock.patch.object(cola, "ESPERA", 1):
            self.assertIsNone(cola.tomar(self.LLAVE))

    def test_la_cola_no_vence(self):
        cola.encolar(self.LLAVE, 1)
        self.assertEqual(self.r.ttl(self.LLAVE), -1)
