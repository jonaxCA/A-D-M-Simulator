import json
import re
import threading
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import requests

from epidemia_comun.formatos import a_xml
from microservicios.estado_servicios import app as modulo_app
from microservicios.estado_servicios import sondeo

RAIZ = Path(__file__).resolve().parents[3]


def respuesta(estado, cuerpo):
    r = requests.Response()
    r.status_code = estado
    r._content = cuerpo
    return r


def salud(nombre, postgresql=True, redis=True, version="0.1.0"):
    sano = postgresql and redis
    datos = {"servicio": nombre, "version": version, "estado": "ok" if sano else "degradado",
             "postgresql": postgresql, "redis": redis}
    return respuesta(200 if sano else 503, a_xml(datos, "salud"))


@pytest.fixture
def red(monkeypatch):
    """Lo que contesta cada servicio a su /health; por omisión, sano. Registra cada petición."""
    respuestas, pedidas = {}, []

    def peticion(metodo, url, **opciones):
        nombre = re.match(r"http://127\.0\.0\.1:(\d+)/health$", url)
        nombre = next(n for n, (_, p) in sondeo.SERVICIOS.items() if p == int(nombre.group(1)))
        pedidas.append((nombre, metodo, opciones))
        contesta = respuestas.get(nombre, salud)
        if isinstance(contesta, Exception):
            raise contesta
        return contesta(nombre)

    monkeypatch.setattr(requests, "request", peticion)
    return {"respuestas": respuestas, "pedidas": pedidas}


@pytest.fixture
def cliente(crear_cliente, red):
    return crear_cliente("estado_servicios")


def test_al_importar_la_app_no_arranca_el_sondeo():
    assert "sondeo" not in [h.name for h in threading.enumerate()]


def test_directorio_publico_con_los_26(cliente):
    r = cliente.get("/api/v1/services?format=json")
    assert r.status_code == 200
    servicios = r.get_json()["servicios"]
    assert [s["nombre"] for s in servicios] == list(sondeo.SERVICIOS)
    auth = servicios[0]
    assert auth == {"nombre": "auth", "dominio": "identidad", "puerto": 5201,
                    "url": "http://localhost:5201", "docs": "http://localhost:5201/docs",
                    "openapi": "http://localhost:5201/openapi.json", "version": None}


def test_directorio_no_sondea_y_toma_la_version_del_ultimo_sondeo(cliente, red):
    cliente.get("/api/v1/services")
    assert red["pedidas"] == []
    red["respuestas"]["zonas"] = lambda n: salud(n, version="0.2.0")
    cliente.get("/api/v1/services/health")
    versiones = {s["nombre"]: s["version"] for s in cliente.get("/api/v1/services?format=json").get_json()["servicios"]}
    assert versiones["zonas"] == "0.2.0" and versiones["auth"] == "0.1.0"


def test_directorio_con_otra_url_publica(cliente, monkeypatch):
    monkeypatch.setenv("URL_PUBLICA", "http://192.168.1.20:{puerto}")
    servicios = cliente.get("/api/v1/services?format=json").get_json()["servicios"]
    assert servicios[-1]["url"] == "http://192.168.1.20:5262"
    # el compose la pasa vacía cuando no está en infra/.env
    monkeypatch.setenv("URL_PUBLICA", "")
    assert sondeo.url_publica("auth") == "http://localhost:5201"


def test_directorio_en_xml_por_omision(cliente):
    r = cliente.get("/api/v1/services")
    assert r.mimetype == "application/xml"
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "directorio"
    assert [s.findtext("nombre") for s in raiz.findall("servicios/servicio")] == list(sondeo.SERVICIOS)


def test_salud_sondea_en_xml_sin_reenviar_el_token(cliente, red, token):
    r = cliente.get("/api/v1/services/health?format=json", headers=token())
    assert r.status_code == 200
    assert sorted(p[0] for p in red["pedidas"]) == sorted(sondeo.SERVICIOS)
    for _, metodo, opciones in red["pedidas"]:
        assert metodo == "GET"
        assert opciones["headers"]["Accept"] == "application/xml"
        assert "Authorization" not in opciones["headers"]
        assert opciones["timeout"] == sondeo.ESPERA


def test_salud_con_la_causa_de_cada_falla(cliente, red):
    red["respuestas"].update({
        "regiones": lambda n: salud(n, postgresql=False),
        "series": lambda n: salud(n, redis=False),
        "casos": requests.Timeout(),
        "corridas": requests.ConnectionError(),
        # en el puerto de zonas contesta otro servicio
        "zonas": lambda n: salud("series"),
        "pareto": lambda n: respuesta(404, b"<html>no</html>"),
    })
    datos = cliente.get("/api/v1/services/health?format=json").get_json()
    por_nombre = {s["nombre"]: s for s in datos["servicios"]}
    assert [s["nombre"] for s in datos["servicios"]] == list(sondeo.SERVICIOS)
    vistos = {n: (s["estado"], s["causas"], s["detalle"]) for n, s in por_nombre.items()}
    assert vistos["auth"] == ("ok", [], None)
    assert vistos["regiones"] == ("degradado", ["postgresql"], None)
    assert vistos["series"] == ("degradado", ["redis"], None)
    assert vistos["casos"] == ("caido", ["proceso"], "tiempo_agotado")
    assert vistos["corridas"] == ("caido", ["proceso"], "sin_conexion")
    assert vistos["zonas"] == ("caido", ["proceso"], "respuesta_invalida")
    assert vistos["pareto"] == ("caido", ["proceso"], "respuesta_invalida")
    assert datos["resumen"] == {"ok": 20, "degradado": 2, "caido": 4}
    assert por_nombre["auth"]["version"] == "0.1.0" and por_nombre["auth"]["latencia_ms"] >= 0
    assert por_nombre["casos"]["latencia_ms"] is None
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00", por_nombre["auth"]["revisado"])


def test_un_503_sin_causa_conocida_es_degradado(cliente, red):
    red["respuestas"]["zonas"] = lambda n: respuesta(503, salud(n).content)
    zonas = cliente.get("/api/v1/services/health?format=json").get_json()["servicios"][23]
    assert (zonas["nombre"], zonas["estado"], zonas["causas"]) == ("zonas", "degradado", [])


def test_no_reenvia_el_token_aunque_sondee_dentro_de_una_peticion(red, token):
    with modulo_app.app.test_request_context(headers=token()):
        assert sondeo.sondear("auth")["estado"] == "ok"
    assert "Authorization" not in red["pedidas"][0][2]["headers"]


def test_salud_en_xml(cliente, red):
    red["respuestas"]["series"] = lambda n: salud(n, postgresql=False, redis=False)
    raiz = ET.fromstring(cliente.get("/api/v1/services/health").data)
    assert raiz.tag == "estado_servicios"
    series = next(s for s in raiz.findall("servicios/servicio") if s.findtext("nombre") == "series")
    assert [c.text for c in series.findall("causas/causa")] == ["postgresql", "redis"]


def test_salud_guardada_en_redis_no_se_vuelve_a_sondear(cliente, red, redis_falso):
    cliente.get("/api/v1/services/health")
    assert len(red["pedidas"]) == 26
    assert 0 < redis_falso.ttl("health:auth") <= 3 * sondeo.INTERVALO
    cliente.get("/api/v1/services/health")
    assert len(red["pedidas"]) == 26
    redis_falso.delete("health:zonas")
    cliente.get("/api/v1/services/health")
    assert [p[0] for p in red["pedidas"][26:]] == ["zonas"]


def test_con_redis_caido_la_salud_se_sondea_en_vivo(cliente, red, apagar_redis, monkeypatch):
    apagar_redis()
    guardados = []
    monkeypatch.setattr(sondeo, "guardar", guardados.append)
    r = cliente.get("/api/v1/services/health?format=json")
    assert r.status_code == 200
    assert r.get_json()["resumen"]["ok"] == 26
    cliente.get("/api/v1/services/health")
    assert len(red["pedidas"]) == 52
    # ni intenta guardar: con Redis caído solo sumaría otra espera
    assert guardados == []
    assert cliente.get("/api/v1/services?format=json").status_code == 200


def test_historial_del_mas_reciente_al_mas_viejo_y_corto(cliente, red, redis_falso):
    for i in range(sondeo.HISTORIAL + 5):
        red["respuestas"]["series"] = lambda n, i=i: salud(n, version="0.%d" % i)
        sondeo.guardar(sondeo.sondear_varios(["series"]))
    r = cliente.get("/api/v1/services/series/history?format=json")
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["servicio"] == "series"
    assert [s["version"] for s in datos["sondeos"]] == ["0.%d" % i for i in range(sondeo.HISTORIAL + 4, 4, -1)]
    assert 0 < redis_falso.ttl("health:history:series") <= sondeo.TTL_HISTORIAL


def test_historial_vacio_y_en_xml(cliente):
    raiz = ET.fromstring(cliente.get("/api/v1/services/zonas/history").data)
    assert raiz.tag == "historial" and raiz.findtext("servicio") == "zonas"
    assert raiz.findall("sondeos/sondeo") == []


def test_historial_de_un_servicio_que_no_existe(cliente):
    r = cliente.get("/api/v1/services/pasarela/history?format=json")
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"


def test_historial_con_redis_caido_es_503(cliente, apagar_redis):
    apagar_redis()
    r = cliente.get("/api/v1/services/zonas/history?format=json")
    assert r.status_code == 503 and r.get_json()["codigo"] == "SERVICIO_NO_DISPONIBLE"


class Alto(Exception):
    pass


def test_el_ciclo_guarda_cada_ronda_y_sigue_si_una_falla(red, redis_falso, monkeypatch):
    rondas, real = [], sondeo.sondear_varios

    def varios(nombres):
        rondas.append(nombres)
        if len(rondas) == 1:
            raise RuntimeError("falla de prueba")
        return real(nombres)

    def dormir(segundos):
        assert 0 <= segundos <= sondeo.INTERVALO
        if len(rondas) == 2:
            raise Alto

    monkeypatch.setattr(sondeo, "sondear_varios", varios)
    monkeypatch.setattr(sondeo.time, "sleep", dormir)
    with pytest.raises(Alto):
        sondeo._ciclo()
    assert rondas == [list(sondeo.SERVICIOS)] * 2
    assert redis_falso.exists("health:auth") and redis_falso.llen("health:history:auth") == 1


def test_url_de_sondeo_del_compose(monkeypatch):
    monkeypatch.setenv("URL_SONDEO", "http://{servicio}:8000")
    assert sondeo.url_sondeo("tipos-intervencion") == "http://tipos-intervencion:8000"


def test_intervalo_invalido_usa_el_de_omision(monkeypatch):
    monkeypatch.setenv("SONDEO_SEGUNDOS", "diez")
    assert sondeo.intervalo() == sondeo.INTERVALO
    monkeypatch.setenv("SONDEO_SEGUNDOS", "0")
    assert sondeo.intervalo() == 1


# ------------------------------------------- el directorio contra el catálogo y el compose

def test_los_26_del_catalogo_con_su_puerto():
    texto = (RAIZ / "docs/arquitectura/microservicios.md").read_text(encoding="utf-8")
    catalogo = {m.group(1): int(m.group(2))
                for m in re.finditer(r"^\| \d+ +\| `([a-z-]+)` .*\| (\d{4}) +\|$", texto, re.M)}
    assert catalogo == {n: p for n, (_, p) in sondeo.SERVICIOS.items()}


def test_cada_servicio_del_compose_con_su_puerto_y_perfil():
    compose = (RAIZ / "infra/docker-compose.yml").read_text(encoding="utf-8")
    vistos = {m.group(1): (m.group(2), int(m.group(3))) for m in re.finditer(
        r"^  ([a-z-]+):\n(?:    .*\n)*?    profiles: \[([a-z]+)\]\n    ports:\n      - \"(\d+):8000\"",
        compose, re.M)}
    # La consola está en el compose, pero no es uno de los 26: no tiene /health de servicio.
    vistos.pop("consola")
    assert vistos and all(sondeo.SERVICIOS[n] == v for n, v in vistos.items())


def test_cada_servicio_existente_se_llama_como_en_el_directorio():
    # El sondeo compara el nombre que da /health con el del directorio.
    for app in sorted((RAIZ / "microservicios").glob("*/app.py")):
        if app.parent.name == "consola":
            continue
        texto = app.read_text(encoding="utf-8")
        nombre = re.search(r'crear_app\("([a-z-]+)"', texto).group(1)
        assert "port=%d" % sondeo.SERVICIOS[nombre][1] in texto, app
