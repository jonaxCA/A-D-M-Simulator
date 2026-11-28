import json
from pathlib import Path

import pytest

from epidemia_comun import archivos, limites, llaves, salud
from epidemia_comun.fabrica import crear_app

CONTRATO = Path(__file__).resolve().parents[3] / "docs/contratos/zonas/openapi.json"


@pytest.fixture
def nueva_app(redis_falso, monkeypatch):
    from epidemia_comun import bd as db
    monkeypatch.setattr(db, "query", lambda *a, **k: {"ok": 1})

    def crear(dependencias=(), **entorno):
        for k, v in entorno.items():
            monkeypatch.setenv(k, v)
        app = crear_app("zonas", CONTRATO, dependencias=dependencias)
        app.config["TESTING"] = True
        app.extensions["epidemia_redis"] = redis_falso
        return app
    return crear


def salud_de(app):
    r = app.test_client().get("/health?format=json")
    return r.status_code, json.loads(r.data)


def test_sin_declarar_mongodb_ni_bucket_dice_que_no_los_usa(nueva_app):
    estado, datos = salud_de(nueva_app())
    assert estado == 200
    assert (datos["mongodb"], datos["bucket"]) == ("no_usa", "no_usa")
    assert datos["postgresql"] is True and datos["redis"] is True
    assert set(datos["tiempos_ms"]) == {"postgresql", "redis"}
    assert datos["tiempo_ms"] >= 0


def test_declarada_y_sin_url_es_no_configurado_y_degrada(nueva_app, monkeypatch):
    monkeypatch.delenv("MONGO_URL", raising=False)
    estado, datos = salud_de(nueva_app(dependencias=("mongodb",)))
    assert estado == 503
    assert datos["mongodb"] == "no_configurado" and datos["estado"] == "degradado"
    assert datos["bucket"] == "no_usa"


def test_mongodb_arriba_y_caido_con_ping(nueva_app, apagar_mongo):
    app = nueva_app(dependencias=("mongodb",), MONGO_URL="mongodb://mongodb:27017/epidemia")
    estado, datos = salud_de(app)
    assert estado == 200 and datos["mongodb"] is True and "mongodb" in datos["tiempos_ms"]
    apagar_mongo()
    estado, datos = salud_de(app)
    assert estado == 503 and datos["mongodb"] is False


def test_bucket_arriba_y_caido_con_el_cliente_de_archivos(nueva_app, monkeypatch):
    vivo = {"valor": True}
    monkeypatch.setattr(archivos, "ping", lambda: vivo["valor"])
    app = nueva_app(DEPENDENCIAS="bucket", ARCHIVOS="gcs", BUCKET_NOMBRE="epidemia-archivos")
    assert salud_de(app)[1]["bucket"] is True
    vivo["valor"] = False
    estado, datos = salud_de(app)
    assert estado == 503 and datos["bucket"] is False and datos["mongodb"] == "no_usa"


def test_bucket_sin_nombre_es_no_configurado(nueva_app, monkeypatch):
    monkeypatch.delenv("BUCKET_NOMBRE", raising=False)
    estado, datos = salud_de(nueva_app(DEPENDENCIAS="bucket", ARCHIVOS="gcs"))
    assert estado == 503 and datos["bucket"] == "no_configurado"


def test_bucket_en_disco(nueva_app, tmp_path):
    app = nueva_app(DEPENDENCIAS="bucket", ARCHIVOS="disco", ARCHIVOS_DIR=str(tmp_path))
    assert salud_de(app)[1]["bucket"] is True


def test_dependencias_del_entorno_ignoran_nombres_desconocidos(monkeypatch):
    monkeypatch.setenv("DEPENDENCIAS", "mongodb, otra")
    assert salud.usadas(("bucket",)) == {"mongodb", "bucket"}


def test_un_5xx_se_cuenta_pero_no_el_health_ni_un_4xx(nueva_app, redis_falso):
    app = nueva_app()

    @app.get("/falla")
    def falla():
        raise RuntimeError("x")

    cliente = app.test_client()
    cliente.get("/falla")
    cliente.get("/falla")
    cliente.get("/no-existe")
    cliente.get("/health")
    assert redis_falso.get(llaves.errores("zonas")) == "2"
    assert 0 < redis_falso.ttl(llaves.errores("zonas")) <= 86400


def test_sin_proxy_se_ignoran_las_cabeceras_forwarded(nueva_app):
    app = nueva_app()
    r = app.test_client().get("/docs", headers={"X-Forwarded-Prefix": "/zonas"})
    assert 'url:"/openapi.json"' in r.get_data(as_text=True)
    contrato = json.loads(app.test_client().get("/openapi.json").data)
    assert contrato["servers"] == json.loads(CONTRATO.read_text(encoding="utf-8"))["servers"]


def test_detras_del_proxy_docs_y_openapi_llevan_el_prefijo(nueva_app):
    app = nueva_app(DETRAS_DE_PROXY="1")
    cabeceras = {"X-Forwarded-Prefix": "/zonas", "X-Forwarded-Proto": "https",
                 "X-Forwarded-Host": "epidemia.example.com"}
    cliente = app.test_client()
    assert 'url:"/zonas/openapi.json"' in cliente.get("/docs", headers=cabeceras).get_data(as_text=True)
    contrato = json.loads(cliente.get("/openapi.json", headers=cabeceras).data)
    assert contrato["servers"] == [{"url": "https://epidemia.example.com/zonas"}]


def test_cors_detras_del_proxy(nueva_app, monkeypatch):
    app = nueva_app(DETRAS_DE_PROXY="1")
    app.config["CONSOLE_ORIGIN"] = "https://epidemia.example.com"
    r = app.test_client().get("/openapi.json", headers={
        "Origin": "https://epidemia.example.com", "X-Forwarded-Prefix": "/zonas"})
    assert r.headers["Access-Control-Allow-Origin"] == "https://epidemia.example.com"


def test_el_limite_usa_la_ip_real_solo_detras_del_proxy(nueva_app, redis_falso, monkeypatch):
    monkeypatch.setenv("LIMITE_PUBLICO", "1/60")
    for detras in ("1", "0"):
        app = nueva_app(DETRAS_DE_PROXY=detras)

        @app.get("/publica%s" % detras)
        @limites.limitar("publico")
        def publica():
            return "ok"

        cliente = app.test_client()
        estados = [cliente.get("/publica" + detras, headers={"X-Forwarded-For": "203.0.113.%d" % n},
                              environ_base={"REMOTE_ADDR": "10.0.0.2"}).status_code for n in (1, 2)]
        # Con proxy, cada IP real tiene su contador; sin él, todo cuenta como 10.0.0.2.
        assert estados == ([200, 200] if detras == "1" else [200, 429])
    assert redis_falso.exists("ratelimit:ip-203.0.113.2:GET:/publica1")


def test_cada_linea_de_registro_trae_fecha_servicio_nivel_y_correlacion(crear_cliente):
    import logging
    import re
    from epidemia_comun import registro
    import io
    cliente = crear_cliente("zonas")
    salida = io.StringIO()
    next(h for h in logging.getLogger().handlers if getattr(h, "_epidemia", False)).setStream(salida)
    cliente.get("/health", headers={"X-Correlation-ID": "abc-123"})
    fuera = logging.getLogger("prueba")
    fuera.warning("fuera de una peticion")
    err = salida.getvalue()
    linea = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d{4} zonas (INFO|WARNING) (\S+) ")
    lineas = [l for l in err.splitlines() if l]
    assert lineas and all(linea.match(l) for l in lineas)
    assert any(" INFO abc-123 GET /health" in l for l in lineas)
    assert any(" WARNING - fuera de una peticion" in l for l in lineas)
    assert registro.FORMATO.count("%(") == 5


def test_cabeceras_hostiles_no_inyectan_html_en_docs_ni_en_openapi(nueva_app):
    app = nueva_app(DETRAS_DE_PROXY="1")
    cabeceras = {"X-Forwarded-Prefix": "/x\"</script><script>alert(1)</script>",
                 "X-Forwarded-Host": "a.example"}
    cliente = app.test_client()
    html = cliente.get("/docs", headers=cabeceras).get_data(as_text=True)
    assert "alert(1)</script>" not in html and html.count("<script>") == 1
    contrato = json.loads(cliente.get("/openapi.json", headers=cabeceras).data)
    assert contrato["servers"][0]["url"].startswith("http://a.example")
