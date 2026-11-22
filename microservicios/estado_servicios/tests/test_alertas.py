"""Alertas técnicas de estado-servicios a los ADMINISTRADOR (F7)."""
import json
import threading
from types import SimpleNamespace

import jwt
import pytest

from epidemia_comun import llaves
from microservicios.estado_servicios import alertas, sondeo

AJUSTES = {"JWT_SECRET_KEY": "secreto-de-pruebas-de-las-alertas-0123456789",
           "JWT_ISSUER": "epidemia-auth", "JWT_AUDIENCE_INTERNA": "epidemia-interno"}


class Resp:
    def __init__(self, estado):
        self.status_code = estado


class Reloj:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def registro(nombre, estado="ok", causas=(), detalle=None):
    return sondeo._registro(nombre, estado, causas, detalle, "0.1.0", 3.0,
                            "2026-11-21T18:30:05+00:00")


CAIDO = ("caido", ["proceso"], "sin_conexion")
SIN_REDIS = ("degradado", ["redis"])


@pytest.fixture
def mundo(monkeypatch, redis_falso):
    m = SimpleNamespace(llamadas=[], estado=201, reloj=Reloj())

    def llamar(servicio, metodo, ruta, **kw):
        m.llamadas.append(dict(kw, servicio=servicio, metodo=metodo, ruta=ruta))
        if isinstance(m.estado, Exception):
            raise m.estado
        return Resp(m.estado)

    monkeypatch.setattr(alertas, "llamar", llamar)
    m.vigia = alertas.Alertas(AJUSTES, reloj=m.reloj)
    return m


def ronda(m, **estados):
    """Una ronda de 10 s; los servicios que no se nombran salen bien."""
    m.reloj.t += 10
    nombres = ["auth", "series", "zonas"] + [n for n in estados if n not in ("auth", "series", "zonas")]
    regs = [registro(n, *estados[n]) if isinstance(estados.get(n), tuple) else registro(n, estados.get(n, "ok"))
            for n in nombres]
    return m.vigia.revisar(regs)


def pasa_la_gracia(m, **estados):
    while m.reloj.t - m.vigia.inicio < alertas.GRACIA:
        ronda(m, **estados)


def test_durante_la_gracia_no_avisa(mundo):
    for _ in range(alertas.GRACIA // 10 - 1):
        ronda(mundo, zonas=CAIDO)
    assert mundo.llamadas == []


def test_una_caida_confirmada_avisa_una_sola_vez_a_los_administradores(mundo):
    pasa_la_gracia(mundo)
    ronda(mundo, zonas=CAIDO)
    ronda(mundo, zonas=CAIDO)
    assert mundo.llamadas == []
    cambios = ronda(mundo, zonas=CAIDO)
    assert [c["nombre"] for c in cambios] == ["zonas"]
    (llamada,) = mundo.llamadas
    assert (llamada["servicio"], llamada["metodo"], llamada["ruta"]) == (
        "notificaciones", "POST", "/api/v1/notifications")
    cuerpo = llamada["cuerpo"]
    assert (cuerpo["role"], cuerpo["type"]) == ("ADMINISTRADOR", "SYSTEM")
    assert cuerpo["title"] == "zonas está caído"
    assert cuerpo["body"] == "zonas: en línea → caído (proceso, sin conexión)"
    assert cuerpo["payload"]["servicios"] == [
        {"nombre": "zonas", "anterior": "ok", "estado": "caido", "causas": ["proceso"],
         "detalle": "sin_conexion", "revisado": "2026-11-21T18:30:05+00:00"}]
    token = jwt.decode(llamada["token"], AJUSTES["JWT_SECRET_KEY"], algorithms=["HS256"],
                       audience="epidemia-interno")
    assert token["sub"] == "estado-servicios"
    for _ in range(10):
        ronda(mundo, zonas=CAIDO)
    assert len(mundo.llamadas) == 1


def test_un_reinicio_corto_no_avisa(mundo):
    pasa_la_gracia(mundo)
    ronda(mundo, zonas=CAIDO)
    ronda(mundo, zonas=CAIDO)
    for _ in range(5):
        ronda(mundo)
    assert mundo.llamadas == []


def test_la_recuperacion_se_avisa(mundo):
    pasa_la_gracia(mundo)
    for _ in range(3):
        ronda(mundo, zonas=CAIDO)
    for _ in range(3):
        ronda(mundo)
    assert len(mundo.llamadas) == 2
    cuerpo = mundo.llamadas[1]["cuerpo"]
    assert cuerpo["title"] == "zonas se recuperó"
    assert cuerpo["body"] == "zonas: caído → en línea"


def test_los_cambios_de_una_ronda_van_en_un_solo_aviso(mundo):
    pasa_la_gracia(mundo)
    for _ in range(3):
        ronda(mundo, series=SIN_REDIS, zonas=SIN_REDIS)
    (llamada,) = mundo.llamadas
    assert llamada["cuerpo"]["title"] == "2 servicios con fallas: series, zonas"
    assert llamada["cuerpo"]["body"] == ("series: en línea → degradado (redis)\n"
                                         "zonas: en línea → degradado (redis)")


def test_una_falla_repetida_espera_10_minutos_desde_la_anterior(mundo):
    pasa_la_gracia(mundo)
    for _ in range(3):
        ronda(mundo, zonas=CAIDO)
    avisada = mundo.reloj.t
    for _ in range(3):
        ronda(mundo)
    assert len(mundo.llamadas) == 2
    # Vuelve a caer: no avisa hasta que pasen 10 min desde la falla avisada.
    while mundo.reloj.t + 10 - avisada < alertas.ESPERA_ENTRE_FALLAS:
        ronda(mundo, zonas=CAIDO)
        assert len(mundo.llamadas) == 2
    ronda(mundo, zonas=CAIDO)
    assert len(mundo.llamadas) == 3
    assert mundo.llamadas[2]["cuerpo"]["title"] == "zonas está caído"


def test_sin_notificaciones_los_cambios_esperan_y_llegan_juntos(mundo):
    """Con Redis caído, notificaciones rechaza el token de servicio: la falla llega al final."""
    pasa_la_gracia(mundo)
    mundo.estado = 503
    for _ in range(3):
        ronda(mundo, auth=SIN_REDIS)
    assert len(mundo.llamadas) == 1
    # El siguiente intento espera REINTENTO (60 s).
    for _ in range(3):
        ronda(mundo)
    assert len(mundo.llamadas) == 1
    mundo.estado = 201
    while len(mundo.llamadas) == 1:
        ronda(mundo)
    assert mundo.reloj.t - mundo.vigia.inicio <= alertas.GRACIA + 30 + alertas.REINTENTO + 10
    cuerpo = mundo.llamadas[1]["cuerpo"]
    assert cuerpo["title"] == "auth se recuperó"
    assert cuerpo["body"] == "auth: en línea → degradado (redis) → en línea"
    assert [c["estado"] for c in cuerpo["payload"]["servicios"]] == ["degradado", "ok"]
    ronda(mundo)
    assert len(mundo.llamadas) == 2


def test_un_error_al_llamar_tampoco_pierde_el_cambio(mundo):
    from epidemia_comun.errores import ErrorAPI
    pasa_la_gracia(mundo)
    mundo.estado = ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio no respondió.")
    for _ in range(3):
        ronda(mundo, zonas=CAIDO)
    mundo.estado = 201
    for _ in range(alertas.REINTENTO // 10):
        ronda(mundo, zonas=CAIDO)
    assert mundo.llamadas[-1]["cuerpo"]["title"] == "zonas está caído"
    assert len(mundo.llamadas) == 2


def test_lo_avisado_sobrevive_a_un_reinicio(mundo, redis_falso):
    pasa_la_gracia(mundo)
    for _ in range(3):
        ronda(mundo, zonas=CAIDO)
    guardado = json.loads(redis_falso.get(llaves.alerta("zonas")))
    assert guardado["estado"] == "caido"
    assert 0 < redis_falso.ttl(llaves.alerta("zonas")) <= alertas.TTL_AVISADO
    # Otro proceso: no repite la falla, y sí avisa la recuperación.
    mundo.vigia = alertas.Alertas(AJUSTES, reloj=mundo.reloj)
    pasa_la_gracia(mundo, zonas=CAIDO)
    for _ in range(5):
        ronda(mundo, zonas=CAIDO)
    assert len(mundo.llamadas) == 1
    for _ in range(3):
        ronda(mundo)
    assert mundo.llamadas[-1]["cuerpo"]["title"] == "zonas se recuperó"


def test_con_redis_caido_lleva_la_cuenta_en_la_memoria(mundo, apagar_redis):
    apagar_redis()
    pasa_la_gracia(mundo)
    for _ in range(3):
        ronda(mundo, zonas=CAIDO)
    for _ in range(3):
        ronda(mundo, zonas=CAIDO)
    assert len(mundo.llamadas) == 1


def test_sin_espacio_se_quedan_los_cambios_mas_nuevos(mundo, monkeypatch):
    monkeypatch.setattr(alertas, "MAXIMO_PENDIENTES", 2)
    monkeypatch.setattr(alertas, "ESPERA_ENTRE_FALLAS", 0)
    pasa_la_gracia(mundo)
    mundo.estado = 503
    for estado in (CAIDO, "ok", CAIDO):
        for _ in range(3):
            ronda(mundo, zonas=estado)
    # Caída (intento fallido), recuperación y otra caída (otro intento fallido): no caben tres.
    assert len(mundo.llamadas) == 2
    mundo.estado = 201
    while len(mundo.llamadas) < 3:
        ronda(mundo, zonas=CAIDO)
    cuerpo = mundo.llamadas[-1]["cuerpo"]
    assert [c["estado"] for c in cuerpo["payload"]["servicios"]] == ["ok", "caido"]
    assert cuerpo["body"] == ("zonas: caído → en línea → caído (proceso, sin conexión)\n"
                              "(Se omitió el cambio más antiguo.)")


def test_un_titulo_largo_se_corta():
    cambios = [{"nombre": "servicio-con-nombre-largo-%02d" % i, "anterior": "ok", "estado": "caido",
                "causas": ["proceso"], "detalle": "sin_conexion"} for i in range(20)]
    titulo = alertas.titulo(cambios)
    assert len(titulo) == alertas.TITULO_MAX and titulo.startswith("20 servicios con fallas: ")
    assert titulo.endswith("…")


def test_titulo_con_fallas_y_recuperaciones():
    cambios = [{"nombre": "auth", "anterior": "caido", "estado": "ok", "causas": [], "detalle": None},
               {"nombre": "zonas", "anterior": "ok", "estado": "degradado", "causas": ["postgresql"],
                "detalle": None}]
    assert alertas.titulo(cambios) == "Cambios en 2 servicios: auth, zonas"


@pytest.mark.parametrize("url,interruptor,activas", [
    ("http://notificaciones:8000", None, True),
    ("http://notificaciones:8000", "1", True),
    ("http://notificaciones:8000", "0", False),
    (None, None, False),
])
def test_cuando_estan_prendidas(monkeypatch, url, interruptor, activas):
    for variable, valor in (("SERVICIO_NOTIFICACIONES_URL", url), ("ALERTAS_TECNICAS", interruptor)):
        if valor is None:
            monkeypatch.delenv(variable, raising=False)
        else:
            monkeypatch.setenv(variable, valor)
    assert alertas.activas() is activas


@pytest.mark.parametrize("url,con_vigia", [("http://notificaciones:8000", True), (None, False)])
def test_iniciar_prende_las_alertas_solo_si_hay_a_quien_avisar(monkeypatch, url, con_vigia):
    hilos = []

    class Hilo:
        def __init__(self, target, args=(), name=None, daemon=None):
            hilos.append((target, args, name))

        def start(self):
            pass

    if url:
        monkeypatch.setenv("SERVICIO_NOTIFICACIONES_URL", url)
    else:
        monkeypatch.delenv("SERVICIO_NOTIFICACIONES_URL", raising=False)
    monkeypatch.delenv("ALERTAS_TECNICAS", raising=False)
    monkeypatch.setattr(threading, "Thread", Hilo)
    sondeo.iniciar(AJUSTES)
    ((objetivo, (vigia,), nombre),) = hilos
    assert objetivo is sondeo._ciclo and nombre == "sondeo"
    assert isinstance(vigia, alertas.Alertas) is con_vigia


class Alto(Exception):
    pass


def test_el_ciclo_revisa_las_alertas_y_sigue_si_fallan(monkeypatch):
    regs = [registro("auth")]
    vistas = []

    class Vigia:
        def revisar(self, registros):
            vistas.append(registros)
            raise RuntimeError("falla de prueba")

    def dormir(segundos):
        if len(vistas) == 2:
            raise Alto

    monkeypatch.setattr(sondeo, "sondear_varios", lambda nombres: regs)
    monkeypatch.setattr(sondeo, "guardar", lambda registros: None)
    monkeypatch.setattr(sondeo.time, "sleep", dormir)
    with pytest.raises(Alto):
        sondeo._ciclo(Vigia())
    assert vistas == [regs, regs]
