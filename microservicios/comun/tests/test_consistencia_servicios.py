"""Consistencia entre servicios: lo que arma un servicio llamador lo aceptan los de verdad.

escenarios-xml (importar) llama a validacion, escenarios e intervenciones; escenarios llama a
validacion. Aquí las tres apps reales (con la base simulada) atienden esas llamadas dentro del
mismo proceso, de modo que un campo renombrado o desconocido en un lado rompe esta prueba.
"""
import copy
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

from backend_web import dispositivos, queries
from epidemia_comun.formatos import a_xml, de_xml
from microservicios.escenarios import rutas as rutas_escenarios
from microservicios.escenarios_xml import lectura, mapeo
from microservicios.escenarios_xml import rutas as rutas_xml
from microservicios.intervenciones import rutas as rutas_intervenciones
from procesamiento.tests.corpus_resolver import ENFERMEDAD

RAIZ = Path(__file__).resolve().parents[3]
EJEMPLO = RAIZ / "docs/contratos/escenarios-xml/ejemplos/importar_escenario.xml"

GRUPOS = {"0-19": 28000, "20-39": 31000, "40-59": 24000, "60-79": 12000, "80+": 3000}
REGION = {"id": 9, "code": "19039", "name": "Monterrey", "level": "municipio",
          "population": 100000, "grupos": GRUPOS, "sin_edad": 2000}
ENFERMEDADES = [{"id": 1, "code": "INFLUENZA_A_H1N1", "name": "Influenza A", "simulable": True,
                 "faltan": 0, "sin_fuente": 0, "supuestos": 0}]
TIPOS = [
    {"id": 4, "code": "CIERRE_ESCUELAS", "name": "Cierre de escuelas", "target_layer": "escuela",
     "param_schema": {"type": "object", "properties": {
         "reduccion": {"type": "number", "minimum": 0, "maximum": 1, "default": 1.0}}}},
    {"id": 5, "code": "VACUNACION", "name": "Vacunación", "target_layer": "todas",
     "param_schema": {"type": "object", "required": ["eficacia", "dosis_diarias"], "properties": {
         "eficacia": {"type": "number", "minimum": 0, "maximum": 1},
         "dosis_diarias": {"type": "integer", "minimum": 1},
         "prioridad": {"type": "string", "enum": ["edad_desc", "zona", "ocupacion", "aleatorio"]},
         "edad_minima": {"type": "integer", "minimum": 0, "maximum": 120}}}},
]
IDS = {"enfermedad": 1, "region": 9, "tipos": {"CIERRE_ESCUELAS": 4, "VACUNACION": 5},
       "regiones": {"19039": 9}}


class Respuesta(requests.Response):
    """Respuesta del cliente de pruebas de Flask con la forma de requests."""

    def __init__(self, flask):
        super().__init__()
        self.status_code = flask.status_code
        self._content = flask.data
        self.headers["Content-Type"] = flask.headers.get("Content-Type", "")


@pytest.fixture
def red(crear_cliente, token, monkeypatch):
    """Las tres apps reales detrás de llamar(); registra lo que escribirían."""
    clientes = {n: crear_cliente(n) for n in ("validacion", "escenarios", "intervenciones",
                                              "escenarios_xml")}
    cabeceras = token(roles=("ANALISTA",))
    escrito = {"escenarios": [], "intervenciones": [], "llamadas": []}

    monkeypatch.setattr(queries, "get_regiones_para_escenario", lambda: [copy.deepcopy(REGION)])
    monkeypatch.setattr(queries, "get_enfermedades_para_escenario",
                        lambda: copy.deepcopy(ENFERMEDADES))
    monkeypatch.setattr(queries, "get_tipos_intervencion", lambda: copy.deepcopy(TIPOS))
    monkeypatch.setattr(queries, "query",
                        lambda sql, params=(), one=False: {"default_params": copy.deepcopy(ENFERMEDAD)})

    def crea_escenario(datos, *, contexto):
        escrito["escenarios"].append(datos)
        return True, None, 12
    monkeypatch.setattr(queries, "crea_escenario", crea_escenario)

    def detalle(scenario_id, numero=None):
        if scenario_id != 12:
            return None
        return {"escenario": {"id": 12, "name": "E", "description": None, "status": "borrador",
                              "owner_id": 7, "created_at": "2026-09-20T15:30:00+00:00",
                              "disease_id": 1, "enfermedad": "Influenza A", "default_params": {},
                              "region_id": 9, "region": "Monterrey", "autor": "Ana"},
                "version": {"id": 31, "version_number": 1, "status": "borrador", "is_current": True,
                            "population_size": 100000, "horizon_days": 180, "initial_infected": 10,
                            "notes": None, "created_at": "2026-09-20T15:30:00+00:00",
                            "population_by_age": GRUPOS, "population_age_unknown": 2000,
                            "age_unknown_policy": "prorratear", "autor": "Ana", "revisor": None,
                            "submitted_at": None, "reviewed_at": None, "review_comment": None},
                "intervenciones": [], "editable": True}
    monkeypatch.setattr(queries, "get_escenario_detalle", detalle)

    def query_version(sql, params=(), one=False):
        if "FROM scenario_versions" in sql:
            return {"id": 31, "scenario_id": 12, "version_number": 1, "status": "borrador",
                    "is_current": True, "horizon_days": 180, "owner_id": 7}
        return [dict(i, name="x", target_layer="todas") for i in escrito["intervenciones"]]
    monkeypatch.setattr(rutas_intervenciones, "query", query_version)

    def agrega(version_id, datos, *, contexto):
        escrito["intervenciones"].append(dict(datos, id=100 + len(escrito["intervenciones"]),
                                              order_index=len(escrito["intervenciones"])))
        return True, None
    monkeypatch.setattr(queries, "agrega_intervencion", agrega)

    def llamar(servicio, metodo, ruta, formato="json", cuerpo=None, **_):
        escrito["llamadas"].append((servicio, metodo, ruta, formato, cuerpo))
        opciones = {"headers": cabeceras}
        if cuerpo is not None:
            if formato == "json":
                opciones["json"] = cuerpo
            else:
                opciones.update(data=a_xml(cuerpo, "solicitud"), content_type="application/xml")
        respuesta = clientes[servicio].open(
            ruta + "?format=" + formato, method=metodo, **opciones)
        return Respuesta(respuesta)
    monkeypatch.setattr(rutas_xml, "llamar", llamar)
    monkeypatch.setattr(rutas_escenarios, "llamar", llamar)
    monkeypatch.setattr(lectura, "resolver_ids", lambda *a: (copy.deepcopy(IDS), []))
    escrito["cabeceras"] = cabeceras
    escrito["clientes"] = clientes
    return escrito


def documento():
    from defusedxml import ElementTree as XMLSeguro
    doc, fallas = mapeo.leer_documento(XMLSeguro.fromstring(EJEMPLO.read_bytes()))
    assert fallas == []
    return doc


def test_validacion_acepta_el_cuerpo_plano_del_importador(red):
    cuerpo = mapeo.cuerpo_validacion(documento(), IDS)
    assert "scenario" not in cuerpo
    r = red["clientes"]["validacion"].post("/api/v1/validate?format=json", json=cuerpo,
                                           headers=red["cabeceras"])
    assert r.status_code == 200, r.data
    datos = r.get_json()
    assert datos["errores"] == [] and datos["valido"] is True
    # y no ignora campos: ningún aviso de «Se ignoró el campo»
    assert not [a for a in datos["avisos"] if a.startswith("Se ignoró")]


def test_validacion_detecta_un_reparto_que_no_es_el_censo(red):
    doc = documento()
    doc["por_edad"]["0-19"] += 1
    r = red["clientes"]["validacion"].post("/api/v1/validate?format=json",
                                           json=mapeo.cuerpo_validacion(doc, IDS),
                                           headers=red["cabeceras"])
    assert r.get_json()["valido"] is False


@pytest.mark.parametrize("formato", ["json", "xml"])
def test_escenarios_acepta_el_alta_del_importador(red, formato):
    cuerpo = mapeo.cuerpo_escenarios(documento(), IDS)
    opciones = ({"json": cuerpo} if formato == "json"
                else {"data": a_xml(cuerpo, "solicitud"), "content_type": "application/xml"})
    r = red["clientes"]["escenarios"].post("/api/v1/scenarios?format=json",
                                           headers=red["cabeceras"], **opciones)
    assert r.status_code == 201, r.data
    # por edad: toma el censo de la región (con la política de la edad no especificada)
    guardado = red["escenarios"][0]
    assert guardado["population_by_age"] == GRUPOS and guardado["age_unknown_policy"] == "prorratear"
    assert r.get_json()["id"] == 12
    # la llamada de escenarios a validacion también la aceptó la validacion real
    assert [c[0] for c in red["llamadas"]] == ["validacion"]


@pytest.mark.parametrize("formato", ["json", "xml"])
def test_intervenciones_acepta_cada_intervencion_del_importador(red, formato):
    for intervencion in documento()["intervenciones"]:
        cuerpo = mapeo.cuerpo_intervencion(intervencion, IDS)
        opciones = ({"json": cuerpo} if formato == "json"
                    else {"data": a_xml(cuerpo, "solicitud"), "content_type": "application/xml"})
        r = red["clientes"]["intervenciones"].post(
            "/api/v1/versions/31/interventions?format=json", headers=red["cabeceras"], **opciones)
        assert r.status_code == 201, (formato, r.data)
    assert [i["code"] for i in red["intervenciones"]] == ["CIERRE_ESCUELAS", "VACUNACION"]
    assert red["intervenciones"][1]["params"]["dosis_diarias"] == 500


def test_importar_de_punta_a_punta_con_los_servicios_reales(red):
    cabeceras = red["cabeceras"]
    cliente = red["clientes"]["escenarios_xml"]
    r = cliente.post("/api/v1/scenarios/import?format=json", data=EJEMPLO.read_bytes(),
                     headers=dict(cabeceras, **{"Content-Type": "application/xml"}))
    assert r.status_code == 201, r.data
    datos = r.get_json()
    assert (datos["scenario_id"], datos["version_id"], datos["intervenciones_creadas"]) == (12, 31, 2)
    assert [(c[0], c[1]) for c in red["llamadas"]] == [
        ("validacion", "POST"), ("escenarios", "POST"), ("validacion", "POST"),
        ("escenarios", "GET"), ("intervenciones", "POST"), ("intervenciones", "POST")]
    # la única pérdida declarada: la región destino de la intervención
    assert any("19039" in a for a in datos["avisos"])
    assert len(red["intervenciones"]) == 2


def test_la_respuesta_de_alta_de_escenarios_trae_lo_que_lee_el_importador(red):
    r = red["clientes"]["escenarios"].post(
        "/api/v1/scenarios?format=json", json=mapeo.cuerpo_escenarios(documento(), IDS),
        headers=red["cabeceras"])
    assert mapeo.ids_de_respuesta(r.get_json())[0] == 12
    d = red["clientes"]["escenarios"].get("/api/v1/scenarios/12?format=json", headers=red["cabeceras"])
    assert mapeo.ids_de_respuesta(d.get_json()) == (12, 31)
    assert de_xml(red["clientes"]["escenarios"].get(
        "/api/v1/scenarios/12", headers=red["cabeceras"]).data)["version"]["id"] == 31


# ---------------------------------------------------- sincronizacion -> casos (servicio real)

class _CasosFalsos:
    """Base mínima de `cases`: INSERT ... ON CONFLICT DO NOTHING y los dos SELECT de casos."""

    def __init__(self):
        self.filas = {}

    def fila(self, caso):
        return (caso["id"], caso["uuid"], caso["device"], 7, 1, "COVID-19", 10, "Monterrey", None,
                None, None, caso["fecha"], None, None, None, None, "pendiente",
                datetime(2026, 10, 12, tzinfo=timezone.utc), None)

    def ejecutar(self, sql, p):
        if sql.startswith("INSERT INTO cases"):
            if p[0] in self.filas:
                return []
            self.filas[p[0]] = {"id": 100 + len(self.filas), "uuid": p[0], "device": p[1],
                                "fecha": p[8]}
            return [(self.filas[p[0]]["id"],)]
        if "WHERE c.local_uuid" in sql:
            return [self.fila(self.filas[p[0]])] if p[0] in self.filas else []
        if "WHERE c.id" in sql:
            return [self.fila(c) for c in self.filas.values() if c["id"] == p[0]]
        raise AssertionError(sql)


def test_sincronizacion_y_casos_reales_201_nuevo_y_200_duplicado(crear_cliente, token, monkeypatch):
    from contextlib import contextmanager
    from microservicios.casos import rutas as rutas_casos
    from microservicios.sincronizacion import rutas as rutas_sync

    base = _CasosFalsos()

    class Cur:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, sql, p=()):
            self.f = base.ejecutar(" ".join(sql.split()), p)

        def fetchone(self):
            return self.f[0] if self.f else None

    class Conn:
        def cursor(self):
            return Cur()

        def commit(self):
            pass

        def rollback(self):
            pass

    @contextmanager
    def get_conn():
        yield Conn()

    monkeypatch.setattr(rutas_casos, "get_conn", get_conn)
    monkeypatch.setattr(rutas_casos, "log_audit", lambda *a, **k: None)
    monkeypatch.setattr(rutas_sync, "log_audit", lambda *a, **k: None)
    # El dispositivo 3 del lote es de quien firma el token (sub 7); el 4, de la misma persona
    # pero revocado.
    monkeypatch.setattr(dispositivos, "estado_para_captura",
                        lambda device_id, user_id: {3: "ok", 4: "revocado"}.get(device_id, "ajeno"))
    monkeypatch.setattr(queries, "get_enfermedades_para_captura",
                        lambda: [{"id": 1, "name": "COVID-19", "code": "SARS"}])
    monkeypatch.setattr(queries, "get_municipios_catalogo", lambda: [{"id": 10, "name": "Monterrey"}])
    cliente_casos = crear_cliente("casos")
    cliente_sync = crear_cliente("sincronizacion")
    cabeceras = token(roles=("CAPTURISTA",))

    def llamar(servicio, metodo, ruta, formato="json", cuerpo=None, token=None, **_):
        assert servicio == "casos" and formato == "json"
        return Respuesta(cliente_casos.open(ruta + "?format=json", method=metodo, json=cuerpo,
                                            headers=cabeceras))
    monkeypatch.setattr(rutas_sync, "llamar", llamar)

    u1, u2 = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
    # u1 ya existe en casos (lo creó otro intento): casos responde 200 duplicado:true
    assert cliente_casos.post("/api/v1/cases?format=json", headers=cabeceras, json={
        "local_uuid": u1, "disease_id": 1, "region_id": 10, "report_date": "2026-10-01"}
    ).status_code == 201
    lote = {"batch_id": "0b6f5a53-1d1f-4f52-8a0a-5d0a4a0e9c11", "device_id": 3, "cases": [
        {"local_uuid": u1, "disease_id": 1, "region_id": 10, "report_date": "2026-10-01"},
        {"local_uuid": u2, "disease_id": 1, "region_id": 10, "report_date": "2026-10-02"},
        {"local_uuid": "33333333-3333-4333-8333-333333333333", "disease_id": 1, "region_id": 10,
         "report_date": "2026-10-02", "campo_raro": 1}]}
    r = cliente_sync.post("/api/v1/sync/cases?format=json", json=lote, headers=cabeceras)
    assert r.status_code == 200, r.data
    resultados = {x["local_uuid"]: x for x in r.get_json()["resultados"]}
    assert resultados[u1]["resultado"] == "duplicado" and resultados[u1]["case_id"] == 100
    assert resultados[u2]["resultado"] == "creado" and resultados[u2]["case_id"] == 101
    assert [x["resultado"] for x in r.get_json()["resultados"]][2] == "rechazado"

    # Desde un teléfono revocado, casos rechaza cada caso con 409 y el lote lo reporta.
    revocado = {"batch_id": "5d1c9d2e-7b3a-4c1f-9e8d-2a6b4c8e0f13", "device_id": 4, "cases": [
        {"local_uuid": "44444444-4444-4444-8444-444444444444", "disease_id": 1, "region_id": 10,
         "report_date": "2026-10-03"}]}
    r = cliente_sync.post("/api/v1/sync/cases?format=json", json=revocado, headers=cabeceras)
    assert r.status_code == 200, r.data
    [resultado] = r.get_json()["resultados"]
    assert resultado["resultado"] == "rechazado" and "revocado" in resultado["errores"][0]


# ------------------------------------------------------------ aprobacion -> validacion real

def test_aprobacion_lee_el_dictamen_de_la_validacion_real(red, monkeypatch):
    from microservicios.aprobacion import rutas as rutas_aprobacion
    monkeypatch.setattr(queries, "get_version_simulacion",
                        lambda vid: {"id": 31, "scenario_id": 12, "version_number": 1,
                                     "status": "borrador"} if vid == 31 else None)
    monkeypatch.setattr(queries, "revisa_version", lambda detalle: ([], ["Aviso del motor"]))

    def llamar(servicio, metodo, ruta, formato="json", cuerpo=None, **_):
        assert servicio == "validacion"
        return Respuesta(red["clientes"]["validacion"].open(
            ruta + "?format=json", method=metodo, headers=red["cabeceras"]))
    monkeypatch.setattr(rutas_aprobacion, "llamar", llamar)
    assert rutas_aprobacion._revisar_con_validacion(31) == ["Aviso del motor"]
    with pytest.raises(Exception) as exc:
        rutas_aprobacion._revisar_con_validacion(99)
    assert getattr(exc.value, "estado", None) == 404
