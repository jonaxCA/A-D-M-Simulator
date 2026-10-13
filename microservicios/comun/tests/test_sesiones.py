import time
from unittest import mock

from epidemia_comun import llaves, sesiones

from .base import ConRedis

HORA = 3600


class Sesiones(ConRedis):
    def _todo_redis(self):
        leer = {"string": self.r.get, "hash": self.r.hgetall, "set": self.r.smembers}
        return " ".join(f"{llave}={leer[self.r.type(llave)](llave)}" for llave in self.r.keys("*"))

    def test_en_redis_solo_hay_huellas(self):
        s = sesiones.abrir(7, ["admin"], HORA)
        todo = self._todo_redis()
        self.assertNotIn(s["sid"], todo)
        self.assertNotIn(s["refresh"].split(".")[1], todo)
        self.assertIn(llaves.huella(s["sid"]), todo)

    def test_la_sesion_dura_el_ttl(self):
        s = sesiones.abrir(7, ["admin", "analista"], HORA)
        h = llaves.huella(s["sid"])
        self.assertTrue(HORA - 5 <= self.r.ttl(llaves.sesion(h)) <= HORA)
        self.assertTrue(HORA - 5 <= self.r.ttl(llaves.sesiones_usuario(7)) <= HORA)
        self.assertEqual(sesiones.obtener(s["sid"]), {
            "usuario": 7, "roles": ["admin", "analista"],
            "creada": s["expira"] - HORA, "expira": s["expira"],
        })
        self.assertEqual(self.r.smembers(llaves.sesiones_usuario(7)), {h})

    def test_sin_roles(self):
        s = sesiones.abrir(7, [], HORA)
        self.assertEqual(sesiones.obtener(s["sid"])["roles"], [])

    def test_sid_desconocido(self):
        self.assertIsNone(sesiones.obtener("inventado"))

    def test_renovar_cambia_el_refresh_en_la_misma_sesion(self):
        s = sesiones.abrir(7, ["admin"], HORA)
        nueva = sesiones.renovar(s["refresh"])
        self.assertEqual(nueva["sid"], s["sid"])
        self.assertNotEqual(nueva["refresh"], s["refresh"])
        self.assertEqual((nueva["usuario"], nueva["roles"], nueva["expira"]), (7, ["admin"], s["expira"]))
        self.assertIsNotNone(sesiones.renovar(nueva["refresh"]))

    def test_renovar_no_alarga_la_sesion(self):
        s = sesiones.abrir(7, ["admin"], HORA)
        self.r.expire(llaves.sesion(llaves.huella(s["sid"])), 100)
        nueva = sesiones.renovar(s["refresh"])
        self.assertLessEqual(self.r.ttl(llaves.refresh(llaves.huella(nueva["refresh"]))), 100)
        self.assertLessEqual(self.r.ttl(llaves.sesion(llaves.huella(s["sid"]))), 100)

    def test_un_refresh_reutilizado_cierra_la_sesion(self):
        s = sesiones.abrir(7, ["admin"], HORA)
        nueva = sesiones.renovar(s["refresh"])
        with self.assertRaises(sesiones.RefreshReutilizado):
            sesiones.renovar(s["refresh"])
        self.assertIsNone(sesiones.obtener(s["sid"]))
        self.assertIsNone(sesiones.renovar(nueva["refresh"]))
        with self.assertRaises(sesiones.RefreshReutilizado):
            sesiones.renovar(s["refresh"])

    def test_dos_renovaciones_a_la_vez_cuentan_como_reutilizacion(self):
        s = sesiones.abrir(7, ["admin"], HORA)
        original = sesiones.transaccion
        otra = {}

        # La otra petición renueva el mismo refresh entre la lectura y la escritura.
        def con_otra_peticion_en_medio(operacion, funcion, *vigilar):
            def intercalada(p):
                resultado = funcion(p)
                if operacion == "refresh_renovar" and "sesion" not in otra:
                    otra["sesion"] = None
                    otra["sesion"] = sesiones.renovar(s["refresh"])
                return resultado
            return original(operacion, intercalada, *vigilar)

        with mock.patch.object(sesiones, "transaccion", con_otra_peticion_en_medio):
            with self.assertRaises(sesiones.RefreshReutilizado):
                sesiones.renovar(s["refresh"])
        self.assertIsNotNone(otra["sesion"])
        self.assertIsNone(sesiones.obtener(s["sid"]))

    def test_un_refresh_inventado_no_toca_la_sesion(self):
        s = sesiones.abrir(7, ["admin"], HORA)
        self.assertIsNone(sesiones.renovar("inventado"))
        self.assertIsNone(sesiones.renovar(s["sid"] + ".inventado"))
        self.assertIsNotNone(sesiones.obtener(s["sid"]))
        self.assertIsNotNone(sesiones.renovar(s["refresh"]))

    def test_cerrar(self):
        s = sesiones.abrir(7, ["admin"], HORA)
        self.assertTrue(sesiones.cerrar(s["sid"]))
        self.assertFalse(sesiones.cerrar(s["sid"]))
        self.assertIsNone(sesiones.renovar(s["refresh"]))
        self.assertEqual(sesiones.verificar(s["sid"], "jti-1"), "sin_sesion")
        self.assertEqual(self.r.keys("*"), [])

    def test_cerrar_todas_solo_las_de_esa_cuenta(self):
        a = sesiones.abrir(7, ["admin"], HORA)
        b = sesiones.abrir(7, ["admin"], HORA)
        otra = sesiones.abrir(8, ["analista"], HORA)
        self.assertEqual(sesiones.cerrar_todas(7), 2)
        self.assertIsNone(sesiones.obtener(a["sid"]))
        self.assertIsNone(sesiones.obtener(b["sid"]))
        self.assertIsNotNone(sesiones.obtener(otra["sid"]))
        self.assertEqual(sesiones.cerrar_todas(7), 0)

    def test_verificar(self):
        s = sesiones.abrir(7, ["admin"], HORA)
        self.assertEqual(sesiones.verificar(s["sid"], "jti-1"), "vigente")
        sesiones.revocar("jti-1", int(time.time()) + 1200)
        self.assertEqual(sesiones.verificar(s["sid"], "jti-1"), "revocado")
        self.assertEqual(sesiones.verificar(s["sid"], "jti-2"), "vigente")
        self.assertEqual(sesiones.verificar("otro-sid", "jti-2"), "sin_sesion")

    def test_la_revocacion_dura_lo_que_le_queda_al_token(self):
        sesiones.revocar("jti-1", int(time.time()) + 1200)
        self.assertTrue(1200 <= self.r.ttl(llaves.revocado("jti-1")) <= 1200 + sesiones.TOLERANCIA)
        sesiones.revocar("jti-2", int(time.time()) - 5000)
        self.assertTrue(0 < self.r.ttl(llaves.revocado("jti-2")) <= 1 + sesiones.TOLERANCIA)
