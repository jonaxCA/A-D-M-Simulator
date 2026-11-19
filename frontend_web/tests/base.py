"""
Preparacion comun de las pruebas de rutas (Flask test client).

Se apoya en backend_web/tests/base.py, que fija JWT_SECRET_KEY antes de que
aqui se importe la app. No contiene pruebas: ningun metodo se llama test_*.
"""
import secrets
import unittest
from unittest.mock import patch

import fakeredis
from epidemia_comun import redis_compartido

# Primero: fija JWT_SECRET_KEY antes de que db.py cargue el .env.
from backend_web.tests.base import (contexto_de_prueba, escribe, id_de_usuario,
                                    requiere_base, version_demo_aprobada)
from backend_web import queries, simulaciones
from backend_web.auth import create_token, hash_password
from frontend_web.app import create_app

# Cuenta CAPTURISTA de prueba. Activa, porque permisos.get_current_user
# rechaza cuentas inactivas aunque el token sea valido, y con una contrasena
# al azar que no se guarda en ningun lado: solo se entra con un token firmado.
# Se queda en la base para que los PERMISSION_DENIED que genera sigan
# atribuidos a alguien.
CAPTURISTA_PRUEBA = "prueba.capturista"


def capturista_de_prueba():
    """Id de la cuenta CAPTURISTA de prueba; la crea o la reactiva."""
    escribe(
        """INSERT INTO users (username, email, password_hash, full_name, is_active)
           VALUES (%s, %s, %s, 'Capturista de prueba', TRUE)
           ON CONFLICT (username) DO UPDATE SET is_active = TRUE""",
        (CAPTURISTA_PRUEBA, f"{CAPTURISTA_PRUEBA}@example.com",
         hash_password(secrets.token_urlsafe(24))))
    escribe(
        """INSERT INTO user_roles (user_id, role_id)
           SELECT u.id, r.id FROM users u, roles r
           WHERE u.username = %s AND r.code = 'CAPTURISTA'
           ON CONFLICT DO NOTHING""", (CAPTURISTA_PRUEBA,))
    return id_de_usuario(CAPTURISTA_PRUEBA)


class PuenteServicios:
    """backend_web.servicios.llamar, pero contra la app Flask de cada microservicio en este
    mismo proceso: la misma base de pruebas y el mismo Redis falso. Así las pruebas de la web
    con base son de integración web -> servicio (D36) sin levantar contenedores."""

    def __init__(self, redis, abre_sesiones=True):
        # Con sesion_real las pruebas usan las sesiones que abre auth: no se inventan.
        self.redis, self.clientes, self.abre_sesiones = redis, {}, abre_sesiones

    def _cliente(self, servicio):
        if servicio not in self.clientes:
            import importlib
            app = importlib.import_module("microservicios.%s.app" % servicio.replace("-", "_")).app
            app.config["TESTING"] = True
            app.extensions["epidemia_redis"] = self.redis
            self.clientes[servicio] = app.test_client()
        return self.clientes[servicio]

    def _con_sesion(self, token, forzar=False):
        # Las pruebas firman tokens sin sesión (create_token sin sid ni jti); los servicios no
        # los aceptan. Aquí se vuelven a firmar con una sesión abierta en el Redis falso.
        import uuid
        from backend_web.auth import decode_token
        from epidemia_comun.seguridad import identificador_sesion
        payload = decode_token(token)
        if not payload or payload.get("sid") or not (self.abre_sesiones or forzar):
            return token
        sid, jti = str(uuid.uuid4()), uuid.uuid4().hex
        self.redis.set("session:" + identificador_sesion(sid), "1")
        return create_token({"id": int(payload["sub"]), "username": payload.get("username"),
                             "full_name": payload.get("full_name"),
                             "roles": payload.get("roles") or []}, sid=sid, jti=jti)

    def __call__(self, servicio, metodo, ruta, token=None, params=None, cuerpo=None, correlacion=None):
        from backend_web.servicios import ErrorServicio, ServicioNoDisponible, cabeceras_de_la_persona
        cabeceras = dict(cabeceras_de_la_persona(), Accept="application/json")
        if token:
            cabeceras["Authorization"] = "Bearer " + self._con_sesion(token)
        consulta = {k: v for k, v in dict(params or {}, format="json").items() if v is not None}
        r = getattr(self._cliente(servicio), metodo.lower())(
            ruta, query_string=consulta, headers=cabeceras, json=cuerpo)
        if r.status_code >= 500:
            raise ServicioNoDisponible(servicio)
        if r.status_code >= 400:
            problema = r.get_json(silent=True) or {}
            raise ErrorServicio(servicio, r.status_code, problema.get("codigo"), problema.get("detail"))
        return r.get_json(silent=True)


def sesion_simulada(token):
    """Lo que responderia el servicio sesiones (D36) por un token que la prueba firmo a mano."""
    from backend_web.auth import decode_token
    from backend_web.servicios import ErrorServicio
    payload = decode_token(token)
    if not payload:
        raise ErrorServicio("sesiones", 401, "TOKEN_INVALIDO")
    return {"sub": int(payload["sub"]), "roles": payload.get("roles") or [],
            "username": payload.get("username"), "full_name": payload.get("full_name")}


class AppTestCase(unittest.TestCase):
    # La app se crea una vez por clase. Redis es fakeredis (self.redis).
    # Con D36 la sesion la valida el servicio sesiones: aqui se simula leyendo el token que la
    # prueba firmo. Con sesion_real = True la prueba usa la verificacion de verdad (login y
    # logout por /login y /logout, contra auth y sesiones).

    sesion_real = False
    # Las llamadas de la web a los servicios van al PuenteServicios (los servicios en este
    # proceso). Una prueba que intercepta la petición HTTP misma lo apaga.
    puente_servicios = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = create_app()
        cls.app.testing = True

    def setUp(self):
        super().setUp()
        self.servidor_redis = fakeredis.FakeServer()
        self.redis = fakeredis.FakeRedis(server=self.servidor_redis, decode_responses=True)
        redis_compartido.usar(self.redis)
        self.addCleanup(redis_compartido.usar, None)
        if self.puente_servicios:
            self.puente = PuenteServicios(self.redis, abre_sesiones=not self.sesion_real)
            for objetivo in ("backend_web.servicios.llamar",
                             "frontend_web.app.sesion_servicios.llamar"):
                simulado = patch(objetivo, side_effect=self.puente)
                simulado.start()
                self.addCleanup(simulado.stop)
        if not self.sesion_real:
            simulado = patch("frontend_web.app.sesion_servicios._actual", side_effect=sesion_simulada)
            simulado.start()
            self.addCleanup(simulado.stop)

    def _captcha(self):
        """Los campos del captcha de auth, ya contestado (D36)."""
        from frontend_web.app import sesion_servicios
        captcha = sesion_servicios.captcha()
        a, b = (int(x) for x in captcha["pregunta"].split("+"))
        return {"captcha_id": captcha["captcha_id"], "captcha_respuesta": str(a + b)}

    def _login(self, client, usuario, password):
        resp = client.post("/login", data=dict(self._captcha(), usuario=usuario, password=password),
                           follow_redirects=False)
        self.assertEqual(resp.status_code, 302, f"login de {usuario} fallo: {resp.data}")


class ConUsuarioSimulado(AppTestCase):
    """Para pruebas con las consultas simuladas: el token es de un usuario
    inventado (id 999); sesion_simulada lo da por vigente."""

    def _token(self, rol="ANALISTA"):
        return create_token({
            "id": 999,
            "username": "prueba",
            "full_name": "Usuario Prueba",
            "roles": [rol],
        })


@requiere_base
class RutasConCorridas(AppTestCase):
    """Rutas que muestran corridas reales sobre la version aprobada de la demo.
    La web ya no las lanza (D4): `_corre` las crea por el mismo camino que el
    escritorio y el simulador. Los lotes que las pruebas registran en
    `_batches_creados` se borran al terminar cada una (en cascada, con sus
    corridas y resultados)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.version_id = version_demo_aprobada()
        if cls.version_id is None:
            raise unittest.SkipTest("Falta el escenario de demostracion aprobado.")

    def setUp(self):
        super().setUp()
        self._batches_creados = []

    def tearDown(self):
        for batch_id in self._batches_creados:
            escribe("DELETE FROM simulation_batches WHERE id = %s", (batch_id,))
        super().tearDown()

    def _encola(self, semilla, usuario="alex.cavazos", forzar_error=False):
        """Una corrida encolada, como la deja `corridas` al lanzarla el
        escritorio: con su RUN «encolado» en la bitacora. Devuelve su id."""
        user_id = id_de_usuario(usuario)
        run_id, batch_id, error = queries.crear_corrida(
            self.version_id, semilla, user_id, simulaciones.ENGINE_VERSION,
            contexto=contexto_de_prueba(user_id), forzar_error=forzar_error)
        self.assertIsNone(error, error)
        self._batches_creados.append(batch_id)
        return run_id

    def _corre(self, semilla, usuario="alex.cavazos", forzar_error=False):
        """Una corrida terminada: encolada y ejecutada como lo hace el
        simulador al tomarla de la cola, aqui en el mismo hilo y sin pausa.
        Devuelve su id."""
        run_id = self._encola(semilla, usuario, forzar_error)
        simulaciones.ejecutar_run(run_id, forzar_error=forzar_error, demora_seg=0)
        return run_id
