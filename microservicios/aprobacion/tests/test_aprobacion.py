import logging
from pathlib import Path

import jwt
import pytest
import xmlschema

from epidemia_comun.errores import ErrorAPI
from microservicios.aprobacion import datos, rutas

XSD = Path(__file__).resolve().parents[3] / "docs/contratos/aprobacion/aprobacion.xsd"

AUTOR = 5      # quien armó el escenario
TOKEN_ID = 7   # el "sub" que firma el fixture token()
HUELLA = "ab" * 32


class Resp:
    def __init__(self, estado=200, cuerpo=None):
        self.status_code, self._cuerpo = estado, cuerpo

    def json(self):
        if self._cuerpo is None:
            raise ValueError("sin json")
        return self._cuerpo


class Mundo:
    """aprobacion.datos en memoria: una versión que respeta los cambios concurrentes. El SQL de
    verdad se prueba contra la base en test_aprobacion_bd.py."""

    def __init__(self):
        self.estado = "borrador"
        self.escenario_estado = "borrador"
        self.autor_en_base = AUTOR
        self.otro_cambio_concurrente = False
        self.commits, self.bitacora, self.llamadas = 0, [], []
        self.comentario = self.huella = None
        self.validacion = Resp(200, {"valido": True, "errores": [], "avisos": ["un aviso"],
                                     "huella": HUELLA})
        self.notificaciones = Resp(201, {})

    def escenario_y_version(self, scenario_id):
        if scenario_id != 3:
            return None
        return ({"id": 3, "name": "Brote", "owner_id": AUTOR, "status": self.escenario_estado,
                 "region_id": 5},
                {"id": 11, "version_number": 2, "status": self.estado, "created_by": AUTOR})

    def envia(self, version_id, *, contexto):
        if self.otro_cambio_concurrente:
            raise ErrorAPI(409, "CONFLICTO", "Alguien cambió esta versión o su escenario mientras la enviabas.")
        self.estado = "en_revision"
        self.commits += 1
        self.bitacora.append((contexto.user_id, "envia", version_id))

    def resuelve(self, version_id, decision, comentario, *, contexto, huella=None):
        if self.autor_en_base == contexto.user_id:
            raise ErrorAPI(409, "CONFLICTO", "No puedes revisar una versión que tú creaste.")
        if self.otro_cambio_concurrente:
            raise ErrorAPI(409, "CONFLICTO", "Alguien resolvió esta revisión mientras la tuya estaba abierta.")
        self.estado = datos.DECISIONES[decision][0]
        self.comentario, self.huella = comentario or None, huella
        self.commits += 1
        self.bitacora.append((contexto.user_id, decision, version_id, comentario or None, huella))
        return self.estado

    def pendientes(self):
        return list(PENDIENTES)

    def firma(self, version_id):
        if version_id != 11:
            return None
        return {"version_id": 11, "scenario_id": 3, "version_number": 2, "status": self.estado,
                "approval_sha256": self.huella, "reviewed_at": "2026-11-23T10:00:00+00:00",
                "revisor": "Elena", "corridas": {"coinciden": 2, "distintas": 0, "sin_huella": 1}}


@pytest.fixture
def mundo(monkeypatch):
    m = Mundo()

    def llamar(servicio, metodo, ruta, **kw):
        m.llamadas.append((servicio, metodo, ruta, kw))
        respuesta = m.validacion if servicio == "validacion" else m.notificaciones
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    for nombre in ("escenario_y_version", "envia", "resuelve", "pendientes", "firma"):
        monkeypatch.setattr(datos, nombre, getattr(m, nombre))
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

def test_envio_correcto_valida_y_envia(cliente, mundo, dueno):
    r = enviar(cliente, dueno)
    assert r.status_code == 200
    assert r.get_json() == {"scenario_id": 3, "version_id": 11, "version_number": 2,
                            "status": "en_revision", "avisos": ["un aviso"]}
    servicio, metodo, ruta, kw = mundo.llamadas[0]
    assert (servicio, metodo, ruta) == ("validacion", "GET", "/api/v1/versions/11/validation")
    assert mundo.commits == 1 and mundo.bitacora == [(AUTOR, "envia", 11)]


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

def test_aprobar_firma_y_notifica(cliente, mundo, revisor):
    mundo.estado = "en_revision"
    r = revisar(cliente, revisor, {"decision": "aprobar", "comentario": " ok "})
    assert r.status_code == 200
    assert r.get_json() == {"scenario_id": 3, "version_id": 11, "version_number": 2,
                            "status": "aprobado", "decision": "aprobar", "approval_sha256": HUELLA}
    assert mundo.estado == "aprobado" and mundo.commits == 1
    assert mundo.bitacora == [(TOKEN_ID, "aprobar", 11, "ok", HUELLA)]
    assert mundo.llamadas[0][:3] == ("validacion", "GET", "/api/v1/versions/11/validation")
    servicio, metodo, ruta, kw = mundo.llamadas[-1]
    assert (servicio, metodo, ruta) == ("notificaciones", "POST", "/api/v1/notifications")
    assert kw["cuerpo"]["user_id"] == AUTOR and kw["cuerpo"]["type"] == "SCENARIO_APPROVED"
    assert kw["cuerpo"]["payload"] == {"scenario_id": 3, "version_id": 11, "version_number": 2}
    # Token de servicio (audiencia interna), no el de quien aprueba.
    assert jwt.decode(kw["token"], options={"verify_signature": False})["aud"] == "epidemia-interno"


def test_rechazar_con_comentario_avisa_al_autor(cliente, mundo, revisor):
    mundo.estado = "en_revision"
    r = revisar(cliente, revisor, {"decision": "rechazar", "comentario": "Faltan fuentes"})
    assert r.status_code == 200 and r.get_json()["status"] == "rechazado"
    assert mundo.bitacora[0][3] == "Faltan fuentes" and mundo.huella is None
    assert not [l for l in mundo.llamadas if l[0] == "validacion"]
    servicio, metodo, ruta, kw = mundo.llamadas[-1]
    assert (servicio, metodo, ruta) == ("notificaciones", "POST", "/api/v1/notifications")
    assert kw["cuerpo"]["user_id"] == AUTOR and kw["cuerpo"]["type"] == "SCENARIO_REJECTED"
    assert "Faltan fuentes" in kw["cuerpo"]["body"]
    assert kw["cuerpo"]["payload"] == {"scenario_id": 3, "version_id": 11, "version_number": 2}
    assert jwt.decode(kw["token"], options={"verify_signature": False})["aud"] == "epidemia-interno"


def test_enviar_a_revision_avisa_a_los_epidemiologos(cliente, mundo, dueno):
    assert enviar(cliente, dueno).status_code == 200
    servicio, metodo, ruta, kw = mundo.llamadas[-1]
    assert (servicio, metodo, ruta) == ("notificaciones", "POST", "/api/v1/notifications")
    assert kw["cuerpo"]["role"] == "EPIDEMIOLOGO" and "user_id" not in kw["cuerpo"]
    assert kw["cuerpo"]["type"] == "SCENARIO_SUBMITTED"
    assert kw["cuerpo"]["payload"] == {"scenario_id": 3, "version_id": 11, "version_number": 2}
    assert jwt.decode(kw["token"], options={"verify_signature": False})["aud"] == "epidemia-interno"


def test_envio_rechazado_no_avisa(cliente, mundo, dueno):
    mundo.estado = "en_revision"
    assert enviar(cliente, dueno).status_code == 409
    assert [l[0] for l in mundo.llamadas] == []


@pytest.mark.parametrize("falla", [ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "caído"), Resp(500)])
def test_aviso_fallido_no_tumba_el_envio_ni_el_rechazo(cliente, mundo, dueno, revisor, falla):
    mundo.notificaciones = falla
    assert enviar(cliente, dueno).status_code == 200 and mundo.estado == "en_revision"
    r = revisar(cliente, revisor, {"decision": "rechazar", "comentario": "No"})
    assert r.status_code == 200 and mundo.estado == "rechazado"


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


def test_review_sin_token_401_y_analista_403(cliente, token):
    # scenarios.approve (D1, 034): EPIDEMIOLOGO y ADMINISTRADOR; el ANALISTA no.
    cuerpo = {"decision": "aprobar"}
    assert revisar(cliente, {}, cuerpo).status_code == 401
    r = revisar(cliente, token(roles=("ANALISTA",)), cuerpo)
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"


def test_el_administrador_revisa_una_version_ajena(cliente, mundo, token):
    mundo.estado = "en_revision"
    r = revisar(cliente, token(roles=("ADMINISTRADOR",)), {"decision": "aprobar"})
    assert r.status_code == 200 and mundo.estado == "aprobado"


def test_el_administrador_tampoco_revisa_la_suya(cliente, mundo, token):
    mundo.estado = "en_revision"
    r = revisar(cliente, token(roles=("ADMINISTRADOR",), sub=str(AUTOR)), {"decision": "aprobar"})
    assert r.status_code == 409 and "No puedes revisar una versión que tú creaste" in r.get_json()["detail"]
    assert mundo.estado == "en_revision" and mundo.commits == 0


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


def test_autorrevision_tambien_la_ataja_datos_si_la_ruta_no_la_vio(cliente, mundo, token):
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
    assert mundo.bitacora == [] and [l[0] for l in mundo.llamadas] == ["validacion"]


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
    assert mundo.comentario == "Sin fuentes"


# ---- pending --------------------------------------------------------------------------

PENDIENTES = [{"scenario_id": 3, "name": "Brote", "version_number": 2,
               "submitted_at": "2026-10-01T10:00:00", "population_size": 1000, "horizon_days": 60,
               "created_by": AUTOR, "enfermedad": "Influenza", "region": "Monterrey",
               "autor": "Ana", "n_intervenciones": 1}]


def test_bandeja_para_epidemiologo_y_admin(cliente, token):
    for rol in ("EPIDEMIOLOGO", "ADMINISTRADOR"):
        r = cliente.get("/api/v1/reviews/pending?format=json", headers=token(roles=(rol,)))
        assert r.status_code == 200 and r.get_json() == {"total": 1, "pendientes": PENDIENTES}


def test_bandeja_en_xml_por_defecto(cliente, token):
    r = cliente.get("/api/v1/reviews/pending", headers=token(roles=("EPIDEMIOLOGO",)))
    assert r.mimetype == "application/xml" and b"<bandeja>" in r.data and b"<item>" in r.data


def test_las_respuestas_xml_validan_contra_el_xsd(cliente, mundo, dueno, revisor, token):
    xsd = xmlschema.XMLSchema(str(XSD))
    respuestas = [
        enviar(cliente, dueno, formato="xml"),
        cliente.post("/api/v1/scenarios/3/review", json={"decision": "devolver", "comentario": "Falta la fuente"},
                     headers=revisor),
        enviar(cliente, dueno, formato="xml"),
        cliente.post("/api/v1/scenarios/3/review", json={"decision": "aprobar"}, headers=revisor),
        cliente.get("/api/v1/reviews/pending", headers=token(roles=("EPIDEMIOLOGO",))),
        cliente.get("/api/v1/versions/11/signature", headers=revisor),
    ]
    for r in respuestas:
        assert r.status_code == 200 and r.mimetype == "application/xml", r.data
        xsd.validate(r.data.decode("utf-8"))


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
    assert operaciones == {"enviar_a_revision", "revisar_version", "listar_pendientes", "firma_version"}
    rutas_flask = {r.rule for r in cliente.application.url_map.iter_rules() if r.rule.startswith("/api/")}
    assert rutas_flask == {"/api/v1/scenarios/<scenario_id>/submit",
                           "/api/v1/scenarios/<scenario_id>/review", "/api/v1/reviews/pending",
                           "/api/v1/versions/<version_id>/signature"}


def test_ejemplos_de_peticion_de_review_se_aceptan(cliente, mundo, revisor):
    import json
    ejemplos = CONTRATOS / "ejemplos"
    for nombre in ("revisar_version", "revisar_version_rechazo", "revisar_version_devolucion"):
        esperado = json.loads((ejemplos / (nombre + ".json")).read_text(encoding="utf-8"))
        mundo.validacion = Resp(200, {"valido": True, "errores": [], "avisos": [],
                                      "huella": esperado.get("approval_sha256")})
        for sufijo, tipo in (("json", "application/json"), ("xml", "application/xml")):
            mundo.estado = "en_revision"
            r = cliente.post("/api/v1/scenarios/3/review?format=json", headers={**revisor, "Content-Type": tipo},
                             data=(ejemplos / (nombre + ".peticion." + sufijo)).read_bytes())
            assert r.status_code == 200 and r.get_json() == esperado, r.data
    from epidemia_comun.formatos import a_xml
    for nombre, raiz in (("revisar_version_rechazo", "revision"), ("revisar_version_devolucion", "revision"),
                         ("firma_version", "firma")):
        esperado = json.loads((ejemplos / (nombre + ".json")).read_text(encoding="utf-8"))
        assert a_xml(esperado, raiz).decode() == (ejemplos / (nombre + ".xml")).read_text(encoding="utf-8").rstrip("\n")
        xmlschema.XMLSchema(str(XSD)).validate((ejemplos / (nombre + ".xml")).read_text(encoding="utf-8"))


# ---- devolver y firma (D55) ------------------------------------------------------------

def test_devolver_regresa_a_borrador_con_el_motivo_y_avisa_al_autor(cliente, mundo, revisor):
    mundo.estado = "en_revision"
    r = revisar(cliente, revisor, {"decision": "devolver", "comentario": "Falta la fuente del R0"})
    assert r.status_code == 200 and r.get_json()["status"] == "borrador"
    assert "approval_sha256" not in r.get_json()
    assert mundo.bitacora == [(TOKEN_ID, "devolver", 11, "Falta la fuente del R0", None)]
    servicio, metodo, ruta, kw = mundo.llamadas[-1]
    assert kw["cuerpo"]["type"] == "SCENARIO_RETURNED" and kw["cuerpo"]["user_id"] == AUTOR
    assert "Falta la fuente del R0" in kw["cuerpo"]["body"]


def test_devolver_sin_comentario_es_422(cliente, mundo, revisor):
    mundo.estado = "en_revision"
    r = revisar(cliente, revisor, {"decision": "devolver"})
    assert r.status_code == 422 and "devolver" in r.get_json()["detail"]
    assert mundo.estado == "en_revision" and mundo.commits == 0


def test_lo_devuelto_se_reenvia(cliente, mundo, dueno, revisor):
    assert enviar(cliente, dueno).status_code == 200
    assert revisar(cliente, revisor, {"decision": "devolver", "comentario": "Corrige"}).status_code == 200
    assert enviar(cliente, dueno).status_code == 200 and mundo.estado == "en_revision"


@pytest.mark.parametrize("respuesta", [Resp(200, {"valido": True, "errores": [], "avisos": []}),
                                       Resp(500), ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "caído")])
def test_sin_huella_de_validacion_no_se_aprueba(cliente, mundo, revisor, respuesta):
    mundo.estado = "en_revision"
    mundo.validacion = respuesta
    r = revisar(cliente, revisor, {"decision": "aprobar"})
    assert r.status_code == 503 and mundo.estado == "en_revision" and mundo.commits == 0


def test_no_se_aprueba_lo_que_el_motor_ya_no_corre(cliente, mundo, revisor):
    mundo.estado = "en_revision"
    mundo.validacion = Resp(200, {"valido": False, "errores": ["R0 fuera de rango"], "avisos": [],
                                  "huella": HUELLA})
    r = revisar(cliente, revisor, {"decision": "aprobar"})
    assert r.status_code == 422 and "no se aprueba" in r.get_json()["detail"]
    assert mundo.estado == "en_revision"


def test_un_escenario_archivado_no_se_envia(cliente, mundo, dueno):
    mundo.escenario_estado = "archivado"
    r = enviar(cliente, dueno)
    assert r.status_code == 409 and "archivado" in r.get_json()["detail"]
    assert mundo.llamadas == [] and mundo.commits == 0


def test_la_firma_se_verifica_contra_la_huella_actual(cliente, mundo, revisor, token):
    mundo.estado = "en_revision"
    revisar(cliente, revisor, {"decision": "aprobar"})
    r = cliente.get("/api/v1/versions/11/signature?format=json", headers=token(("ANALISTA",)))
    firma = r.get_json()
    assert r.status_code == 200 and firma["firmada"] is True and firma["integra"] is True
    assert (firma["huella"], firma["huella_actual"], firma["revisor"]) == (HUELLA, HUELLA, "Elena")
    assert firma["corridas"] == {"coinciden": 2, "distintas": 0, "sin_huella": 1}
    mundo.validacion = Resp(200, {"valido": True, "errores": [], "avisos": [], "huella": "cd" * 32})
    firma = cliente.get("/api/v1/versions/11/signature?format=json", headers=revisor).get_json()
    assert firma["firmada"] is True and firma["integra"] is False


def test_una_version_sin_firma_no_es_integra(cliente, mundo, revisor):
    firma = cliente.get("/api/v1/versions/11/signature?format=json", headers=revisor).get_json()
    assert firma["firmada"] is False and firma["integra"] is False and firma["huella"] is None
    xmlschema.XMLSchema(str(XSD)).validate(
        cliente.get("/api/v1/versions/11/signature", headers=revisor).data.decode("utf-8"))


def test_firma_404_401_y_403(cliente, token, mundo):
    assert cliente.get("/api/v1/versions/99/signature?format=json", headers=token()).status_code == 404
    assert cliente.get("/api/v1/versions/abc/signature?format=json", headers=token()).status_code == 422
    assert cliente.get("/api/v1/versions/11/signature?format=json").status_code == 401
    r = cliente.get("/api/v1/versions/11/signature?format=json", headers=token(("CAPTURISTA",)))
    assert r.status_code == 403
