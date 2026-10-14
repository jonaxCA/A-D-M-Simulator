import logging
from contextlib import contextmanager

import pytest

from backend_web import queries
from epidemia_comun.errores import ErrorAPI
from microservicios.aprobacion import rutas

AUTOR = 5      # quien armó el escenario
TOKEN_ID = 7   # el "sub" que firma el fixture token()


class Resp:
    def __init__(self, estado=200, cuerpo=None):
        self.status_code, self._cuerpo = estado, cuerpo

    def json(self):
        if self._cuerpo is None:
            raise ValueError("sin json")
        return self._cuerpo


class Mundo:
    """Una versión y una base falsa que respeta los UPDATE condicionales."""

    def __init__(self):
        self.estado = "borrador"
        self.autor_en_base = AUTOR
        self.otro_cambio_concurrente = False
        self.sentencias, self.commits, self.bitacora = [], 0, []
        self.llamadas = []
        self.validacion = Resp(200, {"valido": True, "errores": [], "avisos": ["un aviso"]})
        self.notificaciones = Resp(201, {})

    def detalle(self, scenario_id, version_number=None):
        if scenario_id != 3:
            return None
        return {"escenario": {"id": 3, "name": "Brote", "owner_id": AUTOR},
                "version": {"id": 11, "version_number": 2, "status": self.estado,
                            "created_by": AUTOR}}

    def ejecutar(self, sql, params):
        self.sentencias.append(sql)
        if self.otro_cambio_concurrente and sql.startswith("UPDATE"):
            return []                       # la fila ya no cumple el WHERE
        if sql.startswith("SELECT created_by"):
            return [(self.autor_en_base,)]
        if sql.startswith("UPDATE scenario_versions v SET status = 'en_revision'"):
            assert "AND v.status = 'borrador'" in sql
            self.estado = "en_revision"
            return [(2,)]
        if sql.startswith("UPDATE scenario_versions SET status = %s"):
            assert "AND status = 'en_revision'" in sql
            self.estado = params[0]
            return [(2,)]
        return []


class Cursor:
    def __init__(self, mundo):
        self.mundo, self.filas = mundo, []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def execute(self, sql, params=()):
        self.filas = self.mundo.ejecutar(" ".join(sql.split()), params)

    def fetchone(self):
        return self.filas[0] if self.filas else None


class Conexion:
    def __init__(self, mundo):
        self.mundo = mundo

    def cursor(self):
        return Cursor(self.mundo)

    def commit(self):
        self.mundo.commits += 1


@pytest.fixture
def mundo(monkeypatch):
    m = Mundo()

    @contextmanager
    def get_conn():
        yield Conexion(m)

    def llamar(servicio, metodo, ruta, **kw):
        m.llamadas.append((servicio, metodo, ruta, kw))
        respuesta = m.validacion if servicio == "validacion" else m.notificaciones
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(queries, "get_escenario_detalle", m.detalle)
    monkeypatch.setattr(queries, "_hay_parametros_congelados", lambda: True)
    monkeypatch.setattr(queries, "revisa_version", lambda d: ([], []))
    monkeypatch.setattr(queries, "get_conn", get_conn)
    monkeypatch.setattr(queries, "log_audit",
                        lambda ctx, accion, entidad, entity_id=None, data_before=None,
                        data_after=None, **kw: m.bitacora.append(
                            (ctx.user_id, accion, entidad, entity_id, data_before, data_after,
                             kw.get("cur") is not None)))
    monkeypatch.setattr(rutas, "llamar", llamar)
    return m


@pytest.fixture
def cliente(crear_cliente, mundo):
    return crear_cliente("aprobacion")


@pytest.fixture
def dueno(token):
    return token(roles=("ANALISTA",), sub=str(AUTOR))


@pytest.fixture
def revisor(token):
    return token(roles=("EPIDEMIOLOGO",))       # sub 7, distinto del autor


def enviar(cliente, headers, scenario_id=3, formato="json"):
    return cliente.post("/api/v1/scenarios/%s/submit?format=%s" % (scenario_id, formato), headers=headers)


def revisar(cliente, headers, cuerpo, scenario_id=3):
    return cliente.post("/api/v1/scenarios/%s/review?format=json" % scenario_id, json=cuerpo, headers=headers)


# ---- submit ---------------------------------------------------------------------------

def test_envio_correcto_valida_congela_y_audita(cliente, mundo, dueno):
    r = enviar(cliente, dueno)
    assert r.status_code == 200
    assert r.get_json() == {"scenario_id": 3, "version_id": 11, "version_number": 2,
                            "status": "en_revision", "avisos": ["un aviso"]}
    servicio, metodo, ruta, kw = mundo.llamadas[0]
    assert (servicio, metodo, ruta) == ("validacion", "GET", "/api/v1/versions/11/validation")
    assert any("disease_params = d.default_params" in s for s in mundo.sentencias)
    assert mundo.commits == 1
    assert mundo.bitacora == [(AUTOR, "UPDATE", "scenario_versions", 11, {"status": "borrador"},
                               {"status": "en_revision", "version_number": 2,
                                "parametros_congelados": True}, True)]


def test_envio_en_xml(cliente, dueno):
    r = enviar(cliente, dueno, formato="xml")
    assert r.status_code == 200 and r.mimetype == "application/xml"
    assert b"<status>en_revision</status>" in r.data


def test_envio_sin_token_401_y_rol_ajeno_403(cliente, token):
    assert enviar(cliente, {}).status_code == 401
    r = enviar(cliente, token(roles=("OBSERVADOR",)))
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"


def test_envio_de_quien_no_es_dueno_403_pero_admin_si(cliente, mundo, token):
    r = enviar(cliente, token(roles=("ANALISTA",)))          # sub 7, no es el dueño
    assert r.status_code == 403 and "Solo quien creó" in r.get_json()["detail"]
    assert mundo.llamadas == [] and mundo.commits == 0
    assert enviar(cliente, token(roles=("ADMINISTRADOR",))).status_code == 200


def test_envio_escenario_inexistente_404(cliente, dueno):
    r = enviar(cliente, dueno, scenario_id=99)
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"
    assert enviar(cliente, dueno, scenario_id="abc").status_code == 422


def test_envio_de_version_que_no_es_borrador_409(cliente, mundo, dueno):
    mundo.estado = "en_revision"
    r = enviar(cliente, dueno)
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"
    assert mundo.bitacora == []


def test_envio_con_version_invalida_422_sin_escribir(cliente, mundo, dueno):
    mundo.validacion = Resp(200, {"valido": False, "errores": ["R0 fuera de rango"], "avisos": []})
    r = enviar(cliente, dueno)
    assert r.status_code == 422 and "R0 fuera de rango" in r.get_json()["detail"]
    assert mundo.commits == 0 and mundo.bitacora == [] and mundo.estado == "borrador"


def test_envio_con_validacion_caida_503(cliente, mundo, dueno):
    mundo.validacion = ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio no respondió.")
    r = enviar(cliente, dueno)
    assert r.status_code == 503 and r.get_json()["codigo"] == "SERVICIO_NO_DISPONIBLE"
    assert mundo.estado == "borrador" and mundo.commits == 0


@pytest.mark.parametrize("respuesta,esperado", [(Resp(500), 503), (Resp(200), 503),
                                                (Resp(404), 404), (Resp(403), 403)])
def test_envio_con_respuestas_raras_de_validacion(cliente, mundo, dueno, respuesta, esperado):
    mundo.validacion = respuesta
    assert enviar(cliente, dueno).status_code == esperado
    assert mundo.commits == 0


def test_envio_con_cambio_concurrente_409(cliente, mundo, dueno):
    mundo.otro_cambio_concurrente = True
    r = enviar(cliente, dueno)
    assert r.status_code == 409 and "Alguien cambió" in r.get_json()["detail"]
    assert mundo.bitacora == [] and mundo.commits == 0


# ---- review ---------------------------------------------------------------------------

def test_aprobar_audita_y_notifica(cliente, mundo, revisor):
    mundo.estado = "en_revision"
    r = revisar(cliente, revisor, {"decision": "aprobar", "comentario": " ok "})
    assert r.status_code == 200
    assert r.get_json() == {"scenario_id": 3, "version_id": 11, "version_number": 2,
                            "status": "aprobado", "decision": "aprobar"}
    assert mundo.estado == "aprobado" and mundo.commits == 1
    assert mundo.bitacora == [(TOKEN_ID, "UPDATE", "scenario_versions", 11,
                               {"status": "en_revision"},
                               {"status": "aprobado", "version_number": 2, "review_comment": "ok"},
                               True)]
    servicio, metodo, ruta, kw = mundo.llamadas[-1]
    assert (servicio, metodo, ruta) == ("notificaciones", "POST", "/api/v1/notifications")
    assert kw["cuerpo"]["user_id"] == AUTOR and kw["cuerpo"]["entity_id"] == 11


def test_rechazar_con_comentario_no_notifica(cliente, mundo, revisor):
    mundo.estado = "en_revision"
    r = revisar(cliente, revisor, {"decision": "rechazar", "comentario": "Faltan fuentes"})
    assert r.status_code == 200 and r.get_json()["status"] == "rechazado"
    assert mundo.bitacora[0][5]["review_comment"] == "Faltan fuentes"
    assert mundo.llamadas == []


def test_rechazar_sin_comentario_422(cliente, mundo, revisor):
    mundo.estado = "en_revision"
    for cuerpo in ({"decision": "rechazar"}, {"decision": "rechazar", "comentario": "   "}):
        r = revisar(cliente, revisor, cuerpo)
        assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"
    assert mundo.estado == "en_revision" and mundo.commits == 0


@pytest.mark.parametrize("cuerpo", [{}, {"decision": "tal vez"}, {"decision": 1},
                                    {"decision": "aprobar", "comentario": 5},
                                    {"decision": "aprobar", "comentario": "x" * 1001}, [1]])
def test_review_con_cuerpo_invalido_422(cliente, mundo, revisor, cuerpo):
    mundo.estado = "en_revision"
    assert revisar(cliente, revisor, cuerpo).status_code == 422


def test_review_sin_token_401_y_solo_epidemiologo_403(cliente, token):
    cuerpo = {"decision": "aprobar"}
    assert revisar(cliente, {}, cuerpo).status_code == 401
    for rol in ("ANALISTA", "ADMINISTRADOR"):
        r = revisar(cliente, token(roles=(rol,)), cuerpo)
        assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"


def test_review_escenario_inexistente_404(cliente, revisor):
    assert revisar(cliente, revisor, {"decision": "aprobar"}, scenario_id=99).status_code == 404


def test_review_de_version_que_no_esta_en_revision_409(cliente, mundo, revisor):
    r = revisar(cliente, revisor, {"decision": "aprobar"})     # sigue en borrador
    assert r.status_code == 409 and "no en revisión" in r.get_json()["detail"]


def test_autorrevision_409_con_mensaje_claro(cliente, mundo, token):
    mundo.estado = "en_revision"
    r = revisar(cliente, token(roles=("EPIDEMIOLOGO",), sub=str(AUTOR)), {"decision": "aprobar"})
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"
    assert "No puedes revisar una versión que tú creaste" in r.get_json()["detail"]
    assert mundo.estado == "en_revision" and mundo.commits == 0 and mundo.bitacora == []


def test_autorrevision_tambien_la_ataja_backend_si_la_ruta_no_la_vio(cliente, mundo, token):
    mundo.estado = "en_revision"
    mundo.autor_en_base = TOKEN_ID       # el detalle aún decía otra cosa
    r = revisar(cliente, token(roles=("EPIDEMIOLOGO",)), {"decision": "aprobar"})
    assert r.status_code == 409 and "No puedes revisar" in r.get_json()["detail"]
    assert mundo.bitacora == []


def test_review_con_cambio_concurrente_409(cliente, mundo, revisor):
    mundo.estado = "en_revision"
    mundo.otro_cambio_concurrente = True
    r = revisar(cliente, revisor, {"decision": "aprobar"})
    assert r.status_code == 409 and "Alguien resolvió" in r.get_json()["detail"]
    assert mundo.bitacora == [] and mundo.llamadas == []


@pytest.mark.parametrize("falla", [ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "caído"),
                                   Resp(403), Resp(500), RuntimeError("boom")])
def test_notificacion_fallida_no_tumba_la_aprobacion(cliente, mundo, revisor, caplog, falla):
    mundo.estado = "en_revision"
    mundo.notificaciones = falla
    with caplog.at_level(logging.WARNING, logger="aprobacion"):
        r = revisar(cliente, revisor, {"decision": "aprobar"})
    assert r.status_code == 200 and mundo.estado == "aprobado" and mundo.commits == 1
    assert any(x.levelno == logging.WARNING for x in caplog.records)


def test_review_responde_xml_y_acepta_cuerpo_xml(cliente, mundo, revisor):
    mundo.estado = "en_revision"
    r = cliente.post("/api/v1/scenarios/3/review", headers={**revisor, "Content-Type": "application/xml"},
                     data=b"<solicitud><decision>rechazar</decision><comentario>Sin fuentes</comentario></solicitud>")
    assert r.status_code == 200 and r.mimetype == "application/xml"
    assert b"<status>rechazado</status>" in r.data
    assert mundo.bitacora[0][5]["review_comment"] == "Sin fuentes"


# ---- pending --------------------------------------------------------------------------

PENDIENTES = [{"scenario_id": 3, "name": "Brote", "version_number": 2,
               "submitted_at": "2026-10-01T10:00:00", "population_size": 1000, "horizon_days": 60,
               "created_by": AUTOR, "enfermedad": "Influenza", "region": "Monterrey",
               "autor": "Ana", "n_intervenciones": 1}]


def test_bandeja_para_epidemiologo_y_admin(cliente, token, monkeypatch):
    monkeypatch.setattr(queries, "get_pendientes_revision", lambda: PENDIENTES)
    for rol in ("EPIDEMIOLOGO", "ADMINISTRADOR"):
        r = cliente.get("/api/v1/reviews/pending?format=json", headers=token(roles=(rol,)))
        assert r.status_code == 200 and r.get_json() == {"total": 1, "pendientes": PENDIENTES}


def test_bandeja_en_xml_por_defecto(cliente, token, monkeypatch):
    monkeypatch.setattr(queries, "get_pendientes_revision", lambda: PENDIENTES)
    r = cliente.get("/api/v1/reviews/pending", headers=token(roles=("EPIDEMIOLOGO",)))
    assert r.mimetype == "application/xml" and b"<bandeja>" in r.data and b"<item>" in r.data


def test_bandeja_401_403(cliente, token):
    assert cliente.get("/api/v1/reviews/pending?format=json").status_code == 401
    assert cliente.get("/api/v1/reviews/pending?format=json",
                       headers=token(roles=("ANALISTA",))).status_code == 403


# ---- contrato ------------------------------------------------------------------------

CONTRATOS = __import__("pathlib").Path(__file__).resolve().parents[3] / "docs/contratos/aprobacion"


def test_openapi_servido_es_el_del_contrato(cliente):
    import json
    servido = cliente.get("/openapi.json").data
    assert servido == (CONTRATOS / "openapi.json").read_bytes()
    spec = json.loads(servido)
    operaciones = {op["operationId"] for ruta in spec["paths"].values() for op in ruta.values()}
    assert operaciones == {"enviar_a_revision", "revisar_version", "listar_pendientes"}
    rutas_flask = {r.rule for r in cliente.application.url_map.iter_rules() if r.rule.startswith("/api/")}
    assert rutas_flask == {"/api/v1/scenarios/<scenario_id>/submit",
                           "/api/v1/scenarios/<scenario_id>/review", "/api/v1/reviews/pending"}


def test_ejemplos_de_peticion_de_review_se_aceptan(cliente, mundo, revisor):
    import json
    ejemplos = CONTRATOS / "ejemplos"
    for nombre in ("revisar_version", "revisar_version_rechazo"):
        esperado = json.loads((ejemplos / (nombre + ".json")).read_text(encoding="utf-8"))
        for sufijo, tipo in (("json", "application/json"), ("xml", "application/xml")):
            mundo.estado = "en_revision"
            r = cliente.post("/api/v1/scenarios/3/review?format=json", headers={**revisor, "Content-Type": tipo},
                             data=(ejemplos / (nombre + ".peticion." + sufijo)).read_bytes())
            assert r.status_code == 200 and r.get_json() == esperado, r.data
    from epidemia_comun.formatos import a_xml
    assert a_xml(esperado, "revision").decode() == (ejemplos / "revisar_version_rechazo.xml").read_text(encoding="utf-8")
