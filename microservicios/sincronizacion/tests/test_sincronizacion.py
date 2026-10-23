import json
import uuid
from xml.etree import ElementTree as ET

import pytest

from epidemia_comun import llaves
from epidemia_comun.errores import ErrorAPI
from microservicios.sincronizacion import rutas

LOTE = "0b6f5a53-1d1f-4f52-8a0a-5d0a4a0e9c11"
U1 = "11111111-1111-4111-8111-111111111111"
U2 = "22222222-2222-4222-8222-222222222222"
U3 = "33333333-3333-4333-8333-333333333333"


class Resp:
    def __init__(self, estado, cuerpo):
        self.status_code, self._cuerpo = estado, cuerpo

    def json(self):
        if self._cuerpo is None:
            raise ValueError("sin json")
        return self._cuerpo


class CasosFalso:
    """Imita al servicio casos: crea una vez por local_uuid, rechaza los inválidos."""
    def __init__(self):
        self.llamadas = []
        self.creados = {}
        self.caido = False
        self.respuesta_fija = None

    def __call__(self, servicio, metodo, ruta, formato="json", cuerpo=None, token=None, **kw):
        self.llamadas.append((servicio, metodo, ruta, formato, cuerpo, token))
        if self.caido:
            raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "El servicio no respondió.")
        if self.respuesta_fija:
            return self.respuesta_fija
        if cuerpo.get("sex") == "X":
            return Resp(422, {"status": 422, "codigo": "DATOS_INVALIDOS",
                              "detail": "El sexo no es un valor del catálogo."})
        if cuerpo["local_uuid"] in self.creados:
            return Resp(200, {"id": self.creados[cuerpo["local_uuid"]], "duplicado": True})
        self.creados[cuerpo["local_uuid"]] = len(self.creados) + 100
        return Resp(201, {"id": self.creados[cuerpo["local_uuid"]], "duplicado": False})


@pytest.fixture
def casos(monkeypatch):
    falso = CasosFalso()
    monkeypatch.setattr(rutas, "llamar", falso)
    return falso


@pytest.fixture
def bitacora(monkeypatch):
    eventos = []
    monkeypatch.setattr(rutas, "log_audit",
                        lambda ctx, accion, entidad, entity_id=None, data_before=None,
                        data_after=None, **kw: eventos.append(
                            (ctx.user_id, accion, entidad, entity_id, data_after)))
    return eventos


@pytest.fixture
def cliente(crear_cliente, casos, bitacora):
    return crear_cliente("sincronizacion")


@pytest.fixture
def captura(token):
    return token(roles=("CAPTURISTA",))


def lote(**cambios):
    datos = {"batch_id": LOTE, "device_id": 3, "cases": [
        {"local_uuid": U1, "disease_id": 1, "region_id": 10, "report_date": "2026-10-01"},
        {"local_uuid": U2, "disease_id": 1, "region_id": 11, "report_date": "2026-10-02",
         "sex": "X"},
    ]}
    datos.update(cambios)
    return datos


def enviar(cliente, headers, cuerpo=None, **kw):
    return cliente.post("/api/v1/sync/cases?format=json", json=cuerpo or lote(), headers=headers, **kw)


def test_lote_nuevo_resultado_por_caso(cliente, captura, casos, bitacora):
    r = enviar(cliente, captura)
    assert r.status_code == 200
    d = r.get_json()
    assert (d["batch_id"], d["total"], d["creados"], d["duplicados"], d["rechazados"]) == (LOTE, 2, 1, 0, 1)
    assert d["repetido"] is False and "user_id" not in d
    assert d["resultados"][0] == {"indice": 0, "local_uuid": U1, "resultado": "creado",
                                  "case_id": 100, "errores": []}
    assert d["resultados"][1]["resultado"] == "rechazado"
    assert "sexo" in d["resultados"][1]["errores"][0].lower()
    assert len(casos.llamadas) == 2


def test_llama_a_casos_en_json_con_token_y_device(cliente, captura, casos):
    enviar(cliente, captura)
    servicio, metodo, ruta, formato, cuerpo, token = casos.llamadas[0]
    assert (servicio, metodo, ruta, formato) == ("casos", "POST", "/api/v1/cases", "json")
    assert token == captura["Authorization"][7:]
    assert cuerpo["device_id"] == 3 and cuerpo["local_uuid"] == U1


def test_device_del_caso_manda_sobre_el_del_lote(cliente, captura, casos):
    c = lote()
    c["cases"][0]["device_id"] = 9
    enviar(cliente, captura, c)
    assert casos.llamadas[0][4]["device_id"] == 9


def test_reenviar_el_lote_no_duplica(cliente, captura, casos, bitacora):
    primero = enviar(cliente, captura).get_json()
    segundo = enviar(cliente, captura)
    assert segundo.status_code == 200
    d = segundo.get_json()
    assert d["repetido"] is True
    assert d["resultados"] == primero["resultados"] and d["recibido_en"] == primero["recibido_en"]
    assert len(casos.llamadas) == 2          # no volvió a llamar a casos
    assert len(bitacora) == 1                # un SYNC por lote procesado


def test_sync_deja_una_bitacora_con_conteos(cliente, captura, bitacora):
    enviar(cliente, captura)
    assert bitacora == [(7, "SYNC", "sync_batches", LOTE,
                         {"batch_id": LOTE, "device_id": 3, "total": 2, "creados": 1,
                          "duplicados": 0, "rechazados": 1})]


def test_falla_de_bitacora_no_tumba_el_lote(cliente, captura, monkeypatch):
    def falla(*a, **k):
        raise RuntimeError("sin base")
    monkeypatch.setattr(rutas, "log_audit", falla)
    assert enviar(cliente, captura).status_code == 200


def test_caso_ya_existente_sale_duplicado(cliente, captura, casos):
    casos.creados[U1] = 55
    d = enviar(cliente, captura, lote(batch_id=str(uuid.uuid4()))).get_json()
    assert d["resultados"][0] == {"indice": 0, "local_uuid": U1, "resultado": "duplicado",
                                  "case_id": 55, "errores": []}
    assert d["duplicados"] == 1


def test_guarda_en_redis_con_ttl(cliente, captura, redis_falso):
    enviar(cliente, captura)
    llave = llaves.lote(LOTE)
    assert llave == "sync:lote:" + LOTE
    ttl = redis_falso.ttl(llave)
    assert 7 * 24 * 3600 - 10 < ttl <= 7 * 24 * 3600
    assert json.loads(redis_falso.get(llave))["creados"] == 1
    assert redis_falso.exists(rutas.llave_candado(LOTE)) == 0   # candado liberado


def test_ttl_configurable(cliente, captura, redis_falso, monkeypatch):
    monkeypatch.setenv("SYNC_LOTE_TTL_SECONDS", "120")
    enviar(cliente, captura)
    assert redis_falso.ttl(llaves.lote(LOTE)) <= 120


def test_lote_en_proceso_409(cliente, captura, casos, redis_falso):
    redis_falso.set(rutas.llave_candado(LOTE), "otro", ex=60)
    r = enviar(cliente, captura)
    assert r.status_code == 409 and r.get_json()["codigo"] == "CONFLICTO"
    assert casos.llamadas == []


def test_casos_caido_503_y_no_se_guarda(cliente, captura, casos, redis_falso):
    casos.caido = True
    r = enviar(cliente, captura)
    assert r.status_code == 503 and r.get_json()["codigo"] == "SERVICIO_NO_DISPONIBLE"
    assert len(casos.llamadas) == 1          # sin reintentos
    assert redis_falso.exists(llaves.lote(LOTE)) == 0
    assert redis_falso.exists(rutas.llave_candado(LOTE)) == 0
    casos.caido = False                       # el cliente reenvía y ahora sí pasa
    assert enviar(cliente, captura).get_json()["creados"] == 1


def test_casos_con_500_es_503(cliente, captura, casos):
    casos.respuesta_fija = Resp(500, None)
    assert enviar(cliente, captura).status_code == 503


def test_casos_rechaza_el_token_se_propaga(cliente, captura, casos):
    casos.respuesta_fija = Resp(403, {"codigo": "PERMISO_INSUFICIENTE", "detail": "No tienes permiso."})
    r = enviar(cliente, captura)
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"


def test_redis_caido_503(cliente, captura, apagar_redis, casos):
    apagar_redis()
    assert enviar(cliente, captura).status_code == 503
    assert casos.llamadas == []


def test_redis_cae_al_guardar_503(cliente, captura, casos, monkeypatch, redis_falso):
    import redis as paquete

    def falla(*a, **k):
        raise paquete.ConnectionError("caído")
    monkeypatch.setattr(redis_falso, "set", falla)
    r = enviar(cliente, captura)
    assert r.status_code == 503


@pytest.mark.parametrize("cambios", [
    {"batch_id": "no-uuid"}, {"batch_id": None}, {"cases": []}, {"cases": "x"},
    {"cases": [{"disease_id": 1}]}, {"cases": [{"local_uuid": "abc"}]}, {"cases": [3]},
    {"extra": 1}, {"device_id": True}, {"cases": [{"local_uuid": U1}] * 101},
    {"batch_id": LOTE, "lote_id": U3},
])
def test_lote_invalido_422(cliente, captura, casos, cambios):
    r = enviar(cliente, captura, lote(**cambios))
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"
    assert casos.llamadas == []


def test_lote_id_como_alias(cliente, captura):
    c = lote()
    c["lote_id"] = c.pop("batch_id")
    assert enviar(cliente, captura, c).get_json()["batch_id"] == LOTE


def test_cuerpo_xml_y_respuesta_xml(cliente, captura, casos):
    xml = ("<lote><batch_id>%s</batch_id><device_id>3</device_id><cases>"
           "<item><local_uuid>%s</local_uuid><disease_id>1</disease_id><region_id>10</region_id>"
           "<report_date>2026-10-01</report_date></item></cases></lote>" % (LOTE, U1))
    r = cliente.post("/api/v1/sync/cases", data=xml,
                     headers=dict(captura, **{"Content-Type": "application/xml"}))
    assert r.status_code == 200 and r.content_type.startswith("application/xml")
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "resultado_lote" and raiz.findtext("creados") == "1"
    item = raiz.find("resultados").find("item")
    assert item.findtext("resultado") == "creado" and item.find("errores") is not None
    assert casos.llamadas[0][4]["local_uuid"] == U1


def test_sin_token_401_y_rol_403(cliente, token):
    assert cliente.post("/api/v1/sync/cases", json=lote()).status_code == 401
    assert cliente.get("/api/v1/sync/batches/" + LOTE).status_code == 401
    for rol in ("EPIDEMIOLOGO", "ANALISTA"):
        h = token(roles=(rol,))
        assert enviar(cliente, h).status_code == 403
        assert cliente.get("/api/v1/sync/batches/" + LOTE, headers=h).status_code == 403


def test_consultar_lote(cliente, captura):
    enviado = enviar(cliente, captura).get_json()
    r = cliente.get("/api/v1/sync/batches/" + LOTE + "?format=json", headers=captura)
    assert r.status_code == 200
    d = r.get_json()
    assert d["resultados"] == enviado["resultados"] and d["repetido"] is True
    x = cliente.get("/api/v1/sync/batches/" + LOTE, headers=captura)
    assert x.content_type.startswith("application/xml") and ET.fromstring(x.data).tag == "resultado_lote"


def test_consultar_lote_inexistente_o_vencido_404(cliente, captura, redis_falso):
    r = cliente.get("/api/v1/sync/batches/" + LOTE + "?format=json", headers=captura)
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"
    enviar(cliente, captura)
    redis_falso.delete(llaves.lote(LOTE))     # venció
    assert cliente.get("/api/v1/sync/batches/" + LOTE, headers=captura).status_code == 404


def test_consultar_id_malo_422(cliente, captura):
    assert cliente.get("/api/v1/sync/batches/abc", headers=captura).status_code == 422


def test_lote_ajeno_no_se_ve_ni_se_reenvia(cliente, token):
    dueno = token(roles=("CAPTURISTA",))
    otro = token(roles=("CAPTURISTA",), sub="8")
    admin = token(roles=("ADMINISTRADOR",), sub="9")
    enviar(cliente, dueno)
    assert cliente.get("/api/v1/sync/batches/" + LOTE, headers=otro).status_code == 404
    assert enviar(cliente, otro).status_code == 409
    assert cliente.get("/api/v1/sync/batches/" + LOTE, headers=admin).status_code == 200


def test_consultar_con_redis_caido_503(cliente, captura, apagar_redis):
    apagar_redis()
    assert cliente.get("/api/v1/sync/batches/" + LOTE, headers=captura).status_code == 503
