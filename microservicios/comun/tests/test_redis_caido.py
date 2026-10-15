import os
import unittest
from unittest import mock

import fakeredis

from epidemia_comun import cache, candados, cola, llaves, redis_compartido, sesiones


class RedisCaido(unittest.TestCase):
    def setUp(self):
        self.servidor = fakeredis.FakeServer()
        self.servidor.connected = False
        redis_compartido.usar(fakeredis.FakeRedis(server=self.servidor, decode_responses=True))
        self.addCleanup(redis_compartido.usar, None)

    def test_lo_protegido_responde_503(self):
        operaciones = {
            "abrir sesión": lambda: sesiones.abrir(7, ["admin"], 3600),
            "leer sesión": lambda: sesiones.obtener("sid"),
            "renovar": lambda: sesiones.renovar("sid.refresh"),
            "cerrar": lambda: sesiones.cerrar("sid"),
            "cerrar todas": lambda: sesiones.cerrar_todas(7),
            "revocar": lambda: sesiones.revocar("jti", 0),
            "verificar token": lambda: sesiones.verificar("sid", "jti"),
            "candado": lambda: candados.candado(llaves.candado_corrida(1), 30).__enter__(),
            "encolar": lambda: cola.encolar(llaves.COLA_SIMULACIONES, 1),
            "tomar": lambda: cola.tomar(llaves.COLA_SIMULACIONES),
        }
        for nombre, operacion in operaciones.items():
            with self.subTest(nombre), self.assertRaises(redis_compartido.RedisNoDisponible):
                operacion()
        self.assertEqual(redis_compartido.RedisNoDisponible.http, 503)

    def test_la_cache_sigue_con_la_base(self):
        self.assertEqual(cache.obtener("zonas", "x", 60, lambda: [1]), [1])

    def test_al_volver_redis_la_cache_se_llena_sola(self):
        cache.obtener("zonas", "x", 60, lambda: [1])
        self.servidor.connected = True
        cache.obtener("zonas", "x", 60, lambda: [2])
        self.assertEqual(cache.obtener("zonas", "x", 60, lambda: [3]), [2])

    def test_al_volver_redis_las_sesiones_funcionan(self):
        self.servidor.connected = True
        s = sesiones.abrir(7, ["admin"], 3600)
        self.assertEqual(sesiones.verificar(s["sid"], "jti"), "vigente")

    def test_salud(self):
        self.assertEqual(redis_compartido.estado()["estado"], "caido")
        self.servidor.connected = True
        self.assertEqual(redis_compartido.estado()["estado"], "ok")


class Cliente(unittest.TestCase):
    def setUp(self):
        redis_compartido.usar(None)
        self.addCleanup(redis_compartido.usar, None)

    def test_timeouts_cortos_y_uno_largo_para_la_cola(self):
        entorno = {"REDIS_URL": "redis://:clave-de-prueba@redis:6379/0", "REDIS_TIMEOUT_SECONDS": "0.5"}
        with mock.patch.dict(os.environ, entorno):
            normal = redis_compartido.cliente().connection_pool.connection_kwargs
            bloqueante = redis_compartido.cliente(5).connection_pool.connection_kwargs
        self.assertEqual((normal["host"], normal["db"], normal["password"]), ("redis", 0, "clave-de-prueba"))
        self.assertEqual((normal["socket_timeout"], normal["socket_connect_timeout"]), (0.5, 0.5))
        self.assertEqual(bloqueante["socket_timeout"], 5.5)
