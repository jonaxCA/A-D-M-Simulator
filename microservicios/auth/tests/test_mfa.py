import json
import time

import pytest
from types import SimpleNamespace

from microservicios.auth import datos as auth
from epidemia_comun import llaves
from microservicios.sesiones import almacen as sesiones
from epidemia_comun.seguridad import verificar_token
from microservicios.auth import mfa, rutas

ADMIN = {"id": 1, "username": "admin", "full_name": "Admin", "roles": ["ADMINISTRADOR"]}
EPI = {"id": 2, "username": "epi", "full_name": "Epi", "roles": ["EPIDEMIOLOGO"]}
ANALISTA = {"id": 7, "username": "analista1", "full_name": "Ana Lista", "roles": ["ANALISTA"]}
CUENTAS = {"admin": ADMIN, "epi": EPI, "analista1": ANALISTA}
DISPOSITIVO = "telefono-de-prueba-001"


class BaseMfa:
    def __init__(self):
        self.filas, self.respaldos, self.usados = {}, {}, set()

    def estado(self, usuario):
        return dict(self.filas[usuario]) if usuario in self.filas else None

    def guardar_secreto(self, contexto, usuario, secreto):
        if usuario in self.filas:
            return False
        self.filas[usuario] = {"secret": secreto, "enabled": False, "last_counter": None,
                               "pendiente_reciente": True}
        return True

    def confirmar(self, contexto, usuario, paso):
        self.filas[usuario].update(enabled=True, last_counter=paso)
        self.respaldos[usuario] = ["aaaaaaaaaaaa", "bbbbbbbbbbbb"]
        return ["aaaa-aaaa-aaaa", "bbbb-bbbb-bbbb"]

    def aceptar_paso(self, usuario, paso):
        ultimo = self.filas[usuario]["last_counter"]
        if ultimo is not None and ultimo >= paso:
            return False
        self.filas[usuario]["last_counter"] = paso
        return True

    def usar_respaldo(self, contexto, usuario, texto):
        if texto in self.respaldos.get(usuario, []) and (usuario, texto) not in self.usados:
            self.usados.add((usuario, texto))
            return True
        return False

    def restablecer(self, contexto, usuario):
        return self.filas.pop(usuario, None) is not None


@pytest.fixture
def bitacora(monkeypatch):
    eventos = []
    monkeypatch.setattr(rutas, "log_audit",
                        lambda ctx, accion, entidad, entity_id=None, **_:
                        eventos.append((ctx.user_id, accion, entidad, entity_id)))
    return eventos


@pytest.fixture
def base(monkeypatch):
    b = BaseMfa()
    for nombre in ("estado", "guardar_secreto", "confirmar", "aceptar_paso", "usar_respaldo",
                   "restablecer"):
        monkeypatch.setattr(mfa, nombre, getattr(b, nombre))
    return b


@pytest.fixture
def estados(monkeypatch, llamar_a_sesiones):
    """Lo que responde sesiones al revisar un dispositivo, por usuario."""
    estado = {}
    llamadas = []

    class Respuesta:
        def __init__(self, cuerpo):
            self.status_code, self.cuerpo = 200, cuerpo

        def json(self):
            return self.cuerpo

    def llamar(servicio, metodo, ruta, cuerpo=None, token=None, **_):
        if ruta.endswith("/internal/open"):
            return llamar_a_sesiones(servicio, metodo, ruta, cuerpo, token)
        llamadas.append((servicio, metodo, ruta, cuerpo, token))
        return Respuesta({"status": estado.get(cuerpo["usuario"], "autorizado")})

    monkeypatch.setattr(rutas, "llamar", llamar)
    estado["llamadas"] = llamadas
    return estado


@pytest.fixture
def cliente(crear_cliente, monkeypatch, bitacora, base, estados):
    monkeypatch.setenv("MFA_PERFILES", "ADMINISTRADOR,EPIDEMIOLOGO")
    monkeypatch.delenv("MAX_SESIONES_POR_USUARIO", raising=False)
    monkeypatch.delenv("DISPOSITIVO_OBLIGATORIO", raising=False)
    monkeypatch.setattr(auth, "attempt_login",
                        lambda u, p: (dict(CUENTAS[u]), None) if p == "correcta" and u in CUENTAS
                        else (None, auth.MENSAJE_CREDENCIALES))
    return crear_cliente("auth")


def login(cliente, redis_falso, usuario, **extra):
    datos = cliente.get("/api/v1/auth/captcha?format=json").get_json()
    a, b = (int(x) for x in datos["pregunta"].split(" + "))
    return cliente.post("/api/v1/auth/login?format=json", json={
        "usuario": usuario, "password": "correcta", "captcha_id": datos["captcha_id"],
        "captcha_respuesta": str(a + b), **extra})


def post(cliente, ruta, **cuerpo):
    return cliente.post("/api/v1/auth/mfa/%s?format=json" % ruta, json=cuerpo)


def dar_alta(redis_falso, id_usuario, codigo="alta-de-prueba"):
    redis_falso.set(llaves.mfa_alta(id_usuario), llaves.huella(codigo))
    return codigo


def enrolar(cliente, redis_falso, base, usuario="admin"):
    reto = login(cliente, redis_falso, usuario, dispositivo_id=DISPOSITIVO).get_json()
    codigo_alta = dar_alta(redis_falso, CUENTAS[usuario]["id"])
    secreto = post(cliente, "enroll", mfa_token=reto["mfa_token"],
                   codigo_alta=codigo_alta).get_json()["secreto"]
    paso = int(time.time() // mfa.PASO)
    return reto["mfa_token"], secreto, mfa.codigo(secreto, paso), paso


def test_vector_de_rfc_6238():
    secreto = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert mfa.codigo(secreto, 59 // 30) == "287082"
    assert mfa.codigo(secreto, 1111111109 // 30) == "081804"


def test_ventana_de_mas_menos_un_paso():
    secreto = mfa.nuevo_secreto()
    ahora = 1_000_000
    paso = ahora // mfa.PASO
    assert mfa.paso_valido(secreto, mfa.codigo(secreto, paso - 1), ahora=ahora) == paso - 1
    assert mfa.paso_valido(secreto, mfa.codigo(secreto, paso + 1), ahora=ahora) == paso + 1
    assert mfa.paso_valido(secreto, mfa.codigo(secreto, paso - 2), ahora=ahora) is None
    assert mfa.paso_valido(secreto, mfa.codigo(secreto, paso), ultimo=paso, ahora=ahora) is None


def test_no_critico_inicia_sesion_como_siempre(cliente, redis_falso):
    r = login(cliente, redis_falso, "analista1")
    assert r.status_code == 200 and "access_token" in r.get_json()


@pytest.mark.parametrize("usuario", ["admin", "epi"])
def test_critico_no_recibe_tokens_con_solo_la_password(cliente, redis_falso, usuario):
    r = login(cliente, redis_falso, usuario, dispositivo_id=DISPOSITIVO)
    datos = r.get_json()
    assert r.status_code == 200 and datos["mfa_requerido"] is True
    assert datos["mfa_enrolado"] is False and "access_token" not in datos
    ttl = redis_falso.ttl(llaves.mfa(llaves.huella(datos["mfa_token"])))
    assert 0 < ttl <= rutas.MFA_TTL


def test_critico_sin_dispositivo_es_422(cliente, redis_falso):
    r = login(cliente, redis_falso, "admin")
    assert r.status_code == 422 and "dispositivo_id" in r.get_json()["detail"]


def test_enrolar_confirmar_y_entrar(cliente, redis_falso, base, bitacora):
    token, secreto, codigo, paso = enrolar(cliente, redis_falso, base)
    secreto = base.filas[1]["secret"]
    codigo = mfa.codigo(secreto, paso)
    r = post(cliente, "confirm", mfa_token=token, codigo=codigo)
    datos = r.get_json()
    assert r.status_code == 200 and datos["codigos_respaldo"] == ["aaaa-aaaa-aaaa", "bbbb-bbbb-bbbb"]
    claims = verificar_token(datos["access_token"], cliente.application.config,
                             redis_falso, roles=("ADMINISTRADOR",))
    assert claims["sub"] == "1"
    assert post(cliente, "confirm", mfa_token=token, codigo=codigo).status_code == 401
    assert (1, "LOGIN", "users", "1") in bitacora


def test_segundo_paso_con_codigo_correcto(cliente, redis_falso, base):
    token, secreto, codigo, paso = enrolar(cliente, redis_falso, base)
    secreto = base.filas[1]["secret"]
    post(cliente, "confirm", mfa_token=token, codigo=mfa.codigo(secreto, paso))
    reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
    assert reto["mfa_enrolado"] is True
    base.filas[1]["last_counter"] = paso - 1
    r = post(cliente, "verify", mfa_token=reto["mfa_token"], codigo=mfa.codigo(secreto, paso))
    assert r.status_code == 200 and r.get_json()["usuario"]["roles"] == ["ADMINISTRADOR"]
    assert post(cliente, "verify", mfa_token=reto["mfa_token"],
                codigo=mfa.codigo(secreto, paso)).status_code == 401


def test_codigo_ya_usado_no_sirve_otra_vez(cliente, redis_falso, base):
    token, _, _, paso = enrolar(cliente, redis_falso, base)
    secreto = base.filas[1]["secret"]
    post(cliente, "confirm", mfa_token=token, codigo=mfa.codigo(secreto, paso))
    reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
    r = post(cliente, "verify", mfa_token=reto["mfa_token"], codigo=mfa.codigo(secreto, paso))
    assert r.status_code == 401 and r.get_json()["codigo"] == "MFA_CODIGO_INVALIDO"


def test_codigo_de_respaldo_sirve_una_vez(cliente, redis_falso, base):
    token, _, _, paso = enrolar(cliente, redis_falso, base)
    secreto = base.filas[1]["secret"]
    post(cliente, "confirm", mfa_token=token, codigo=mfa.codigo(secreto, paso))
    for esperado in (200, 401):
        reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
        r = post(cliente, "verify", mfa_token=reto["mfa_token"], codigo="AAAA-AAAA-AAAA")
        assert r.status_code == esperado


def test_cinco_fallos_matan_el_token(cliente, redis_falso, base, bitacora):
    token, _, _, paso = enrolar(cliente, redis_falso, base)
    secreto = base.filas[1]["secret"]
    post(cliente, "confirm", mfa_token=token, codigo=mfa.codigo(secreto, paso))
    reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
    for _ in range(rutas.MFA_INTENTOS):
        assert post(cliente, "verify", mfa_token=reto["mfa_token"], codigo="000000").status_code == 401
    r = post(cliente, "verify", mfa_token=reto["mfa_token"], codigo=mfa.codigo(secreto, paso + 1))
    assert r.status_code == 401 and r.get_json()["codigo"] == "MFA_TOKEN_INVALIDO"
    assert bitacora.count((1, "LOGIN_FAILED", "user_mfa", "1")) == rutas.MFA_INTENTOS


def test_token_de_mfa_desconocido_es_401(cliente):
    assert post(cliente, "verify", mfa_token="inventado", codigo="123456").status_code == 401


def test_verify_sin_enrolar_es_409(cliente, redis_falso):
    reto = login(cliente, redis_falso, "epi", dispositivo_id=DISPOSITIVO).get_json()
    assert post(cliente, "verify", mfa_token=reto["mfa_token"], codigo="123456").status_code == 409


def test_enroll_con_mfa_activo_es_409(cliente, redis_falso, base):
    token, _, _, paso = enrolar(cliente, redis_falso, base)
    post(cliente, "confirm", mfa_token=token, codigo=mfa.codigo(base.filas[1]["secret"], paso))
    reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
    assert post(cliente, "enroll", mfa_token=reto["mfa_token"]).status_code == 409


def test_mfa_perfiles_vacio_lo_apaga(cliente, redis_falso, monkeypatch):
    monkeypatch.setenv("MFA_PERFILES", "")
    r = login(cliente, redis_falso, "admin")
    assert r.status_code == 200 and "access_token" in r.get_json()


def test_restablecer_solo_lo_hace_un_administrador(cliente, redis_falso, base, token, bitacora):
    base.filas[2] = {"secret": "X", "enabled": True, "last_counter": None}
    ruta = "/api/v1/auth/mfa/2?format=json"
    assert cliente.delete(ruta).status_code == 401
    assert cliente.delete(ruta, headers=token(("EPIDEMIOLOGO",))).status_code == 403
    r = cliente.delete(ruta, headers=token(("ADMINISTRADOR",)))
    assert r.status_code == 200 and r.get_json() == {"usuario": 2, "restablecido": True}
    assert 2 not in base.filas


def test_dispositivo_pendiente_es_403_y_no_abre_sesion(cliente, redis_falso, estados):
    estados[7] = "pendiente"
    r = login(cliente, redis_falso, "analista1", dispositivo_id=DISPOSITIVO)
    assert r.status_code == 403 and r.get_json()["codigo"] == "DISPOSITIVO_NO_AUTORIZADO"
    assert redis_falso.keys("session:*") == []
    servicio, metodo, ruta, cuerpo, token = estados["llamadas"][0]
    assert (servicio, metodo, ruta) == ("sesiones", "POST", "/api/v1/sessions/devices/check")
    assert cuerpo["usuario"] == 7 and token


def test_dispositivo_autorizado_marca_la_sesion(cliente, redis_falso):
    r = login(cliente, redis_falso, "analista1", dispositivo_id=DISPOSITIVO)
    assert r.status_code == 200
    (h,) = redis_falso.smembers(llaves.sesiones_usuario(7))
    assert redis_falso.hget(llaves.sesion(h), "dispositivo") == llaves.huella(DISPOSITIVO)


def test_dispositivo_invalido_es_422(cliente, redis_falso):
    assert login(cliente, redis_falso, "analista1", dispositivo_id="corto").status_code == 422


def test_dispositivo_obligatorio_para_todos(cliente, redis_falso, monkeypatch):
    monkeypatch.setenv("DISPOSITIVO_OBLIGATORIO", "1")
    assert login(cliente, redis_falso, "analista1").status_code == 422


def test_tope_de_sesiones_cierra_la_mas_antigua(cliente, redis_falso, monkeypatch, bitacora):
    ahora = [1_000]
    monkeypatch.setattr(sesiones, "time", SimpleNamespace(time=lambda: ahora[0]))
    refrescos = []
    for _ in range(4):
        ahora[0] += 10
        refrescos.append(login(cliente, redis_falso, "analista1").get_json()["refresh_token"])
    assert len(redis_falso.smembers(llaves.sesiones_usuario(7))) == 3
    assert sesiones.renovar(refrescos[0]) is None
    assert all(sesiones.renovar(r) for r in refrescos[1:])
    assert (7, "LOGIN", "users", "7") in bitacora


def test_tope_configurable(cliente, redis_falso, monkeypatch):
    monkeypatch.setenv("MAX_SESIONES_POR_USUARIO", "1")
    for _ in range(3):
        login(cliente, redis_falso, "analista1")
    assert len(redis_falso.smembers(llaves.sesiones_usuario(7))) == 1


def activar(cliente, redis_falso, base):
    token, _, _, paso = enrolar(cliente, redis_falso, base)
    secreto = base.filas[1]["secret"]
    post(cliente, "confirm", mfa_token=token, codigo=mfa.codigo(secreto, paso))
    return secreto, paso


def test_el_tope_por_cuenta_no_se_reinicia_con_otro_token(cliente, redis_falso, base):
    secreto, paso = activar(cliente, redis_falso, base)
    for _ in range(rutas.MFA_FALLOS_CUENTA):
        reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
        assert post(cliente, "verify", mfa_token=reto["mfa_token"], codigo="000000").status_code == 401
    # Ya bloqueada: ni /login entrega otro reto ni un código correcto se verifica.
    r = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO)
    assert r.status_code == 429 and r.get_json()["codigo"] == "MFA_BLOQUEADO"
    reto = _reto_sin_bloqueo(cliente, redis_falso)
    r = post(cliente, "verify", mfa_token=reto, codigo=mfa.codigo(secreto, paso + 1))
    assert r.status_code == 429
    redis_falso.delete(llaves.mfa_fallos(1))
    assert login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).status_code == 200


def _reto_sin_bloqueo(cliente, redis_falso):
    # Un reto emitido antes del bloqueo: se guarda a mano para probar /verify.
    token = "reto-previo"
    redis_falso.hset(llaves.mfa(llaves.huella(token)), mapping={
        "cuenta": json.dumps(ADMIN), "dispositivo": "", "intentos": 0})
    return token


def test_el_tope_por_cuenta_aguanta_peticiones_en_paralelo(cliente, redis_falso, base, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    secreto, paso = activar(cliente, redis_falso, base)
    token = _reto_sin_bloqueo(cliente, redis_falso)
    redis_falso.hset(llaves.mfa(llaves.huella(token)), "intentos", -1000)
    llamadas = []
    real = mfa.paso_valido
    monkeypatch.setattr(mfa, "paso_valido", lambda *a, **k: llamadas.append(1) or real(*a, **k))
    with ThreadPoolExecutor(20) as pool:
        estados = list(pool.map(lambda _: cliente.post(
            "/api/v1/auth/mfa/verify?format=json",
            json={"mfa_token": token, "codigo": "000000"}).status_code, range(20)))
    assert len(llamadas) <= rutas.MFA_FALLOS_CUENTA and estados.count(429) >= 15


def test_pasar_el_mfa_borra_los_fallos(cliente, redis_falso, base):
    secreto, paso = activar(cliente, redis_falso, base)
    reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
    post(cliente, "verify", mfa_token=reto["mfa_token"], codigo="000000")
    assert redis_falso.get(llaves.mfa_fallos(1)) == "1"
    base.filas[1]["last_counter"] = paso - 1
    assert post(cliente, "verify", mfa_token=reto["mfa_token"], codigo=mfa.codigo(secreto, paso)).status_code == 200
    assert redis_falso.get(llaves.mfa_fallos(1)) is None


def test_el_contador_por_cuenta_vence(cliente, redis_falso, base):
    activar(cliente, redis_falso, base)
    reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
    post(cliente, "verify", mfa_token=reto["mfa_token"], codigo="000000")
    assert 0 < redis_falso.ttl(llaves.mfa_fallos(1)) <= rutas.MFA_BLOQUEO


@pytest.mark.parametrize("ruta", ["verify", "confirm"])
def test_codigo_no_ascii_es_422_y_no_500(cliente, redis_falso, base, ruta):
    reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
    r = post(cliente, ruta, mfa_token=reto["mfa_token"], codigo="١٢٣٤٥٦")
    assert r.status_code == 422
    assert mfa.paso_valido(mfa.nuevo_secreto(), "١٢٣٤٥٦") is None


def test_confirm_con_codigo_mal_formado_es_422(cliente, redis_falso, base):
    token, _, _, _ = enrolar(cliente, redis_falso, base)
    assert post(cliente, "confirm", mfa_token=token, codigo="12ab").status_code == 422


def test_enroll_sin_codigo_de_alta_es_403(cliente, redis_falso, base):
    reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
    r = post(cliente, "enroll", mfa_token=reto["mfa_token"])
    assert r.status_code == 403 and r.get_json()["codigo"] == "ALTA_REQUERIDA" and not base.filas
    r = post(cliente, "enroll", mfa_token=reto["mfa_token"], codigo_alta="inventado")
    assert r.status_code == 403 and r.get_json()["codigo"] == "ALTA_INVALIDA" and not base.filas


def test_el_codigo_de_alta_es_de_la_cuenta_y_de_un_solo_uso(cliente, redis_falso, base):
    reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
    otro = login(cliente, redis_falso, "epi", dispositivo_id=DISPOSITIVO).get_json()
    codigo = dar_alta(redis_falso, 1)
    assert post(cliente, "enroll", mfa_token=otro["mfa_token"], codigo_alta=codigo).status_code == 403
    assert post(cliente, "enroll", mfa_token=reto["mfa_token"], codigo_alta=codigo).status_code == 200
    base.filas.clear()
    assert post(cliente, "enroll", mfa_token=reto["mfa_token"], codigo_alta=codigo).status_code == 403


def test_un_enrolamiento_pendiente_no_se_pisa(cliente, redis_falso, base):
    reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
    post(cliente, "enroll", mfa_token=reto["mfa_token"], codigo_alta=dar_alta(redis_falso, 1))
    secreto = base.filas[1]["secret"]
    r = post(cliente, "enroll", mfa_token=reto["mfa_token"], codigo_alta=dar_alta(redis_falso, 1))
    assert r.status_code == 409 and base.filas[1]["secret"] == secreto
    # No gasta el código de alta si el enrolamiento no procede.
    assert redis_falso.exists(llaves.mfa_alta(1)) == 1


def test_administrador_emite_el_codigo_de_alta(cliente, redis_falso, base, token, bitacora):
    ruta = "/api/v1/auth/mfa/2/enrollment-code?format=json"
    assert cliente.post(ruta).status_code == 401
    assert cliente.post(ruta, headers=token(("EPIDEMIOLOGO",))).status_code == 403
    r = cliente.post(ruta, headers=token(("ADMINISTRADOR",)))
    datos = r.get_json()
    assert r.status_code == 200 and datos["usuario"] == 2 and len(datos["codigo_alta"]) == 16
    assert 0 < redis_falso.ttl(llaves.mfa_alta(2)) <= rutas.ALTA_TTL
    assert redis_falso.get(llaves.mfa_alta(2)) == llaves.huella(datos["codigo_alta"])
    assert datos["codigo_alta"] not in str(bitacora)
    reto = login(cliente, redis_falso, "epi", dispositivo_id=DISPOSITIVO).get_json()
    assert post(cliente, "enroll", mfa_token=reto["mfa_token"],
                codigo_alta=datos["codigo_alta"]).status_code == 200


def test_enrolamiento_libre_es_la_via_del_primer_administrador(cliente, redis_falso, base, monkeypatch):
    monkeypatch.setenv("MFA_ENROLAMIENTO_LIBRE", "1")
    reto = login(cliente, redis_falso, "admin", dispositivo_id=DISPOSITIVO).get_json()
    assert post(cliente, "enroll", mfa_token=reto["mfa_token"]).status_code == 200
