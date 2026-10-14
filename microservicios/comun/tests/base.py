import os
import unittest

import fakeredis

from epidemia_comun import redis_compartido


class ConRedis(unittest.TestCase):
    # Con REDIS_URL_PRUEBAS corre contra ese Redis, que tiene que estar vacío porque
    # cada prueba lo borra al terminar. Sin ella, contra fakeredis.
    def setUp(self):
        url = os.environ.get("REDIS_URL_PRUEBAS")
        if url:
            os.environ["REDIS_URL"] = url
            redis_compartido.usar(None)
            self.r = redis_compartido.cliente()
            if self.r.dbsize():
                self.skipTest("La base de REDIS_URL_PRUEBAS no está vacía; no la borro")
        else:
            self.r = fakeredis.FakeRedis(decode_responses=True)
            redis_compartido.usar(self.r)
        self.addCleanup(redis_compartido.usar, None)
        self.addCleanup(self.r.flushdb)
