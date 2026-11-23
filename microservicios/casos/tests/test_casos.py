import json
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from xml.etree import ElementTree as ET

import psycopg2
import pytest

from microservicios.casos import captura as datos_captura
from microservicios.casos import formularios, rutas

ENFERMEDADES = [{"id": 1, "name": "COVID-19", "code": "SARS"}]
MUNICIPIOS = [{"id": 10, "name": "Monterrey"}, {"id": 11, "name": "Apodaca"}]
UUID_A = "6f1f4f0e-3c6b-4f4c-9d9e-1a2b3c4d5e6f"


class BaseFalsa:
    def __init__(self):
        self.casos = []
        self.historial = []
        self.formularios = {}   # id -> versión de un formulario (D48)
        self.sentencias = []
        self.commits = 0
        self.rollbacks = 0
        self.fallo_fk = None
        self.carrera = False

    def _fila(self, c):
        nombres = {1: "COVID-19", 2: "Dengue"}
        muni = {10: "Monterrey", 11: "Apodaca"}
        return (c["id"], c["local_uuid"], c["device_id"], int(c["reported_by"]), c["disease_id"],
                nombres[c["disease_id"]], c["region_id"], muni[c["region_id"]], c["age"],
                c["sex"], c["onset_date"], c["report_date"], c["latitude"], c["longitude"],
                c["test_result"], c["severity"], c["status"],
                datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc), c["synced_at"],
                c["version"], c["updated_at"], c["updated_by"], c["status_reason"],
                c["duplicate_of"], c["form_id"], c["form_answers"])

    def ejecutar(self, sql, p):
        self.sentencias.append((sql, p))
        if sql.startswith("INSERT INTO cases"):
            if self.fallo_fk:
                raise self.fallo_fk
            if self.carrera or any(c["local_uuid"] == p[0] for c in self.casos):
                if self.carrera:
                    self.casos.append(dict(self._base(p), id=len(self.casos) + 1))
                return []
            self.casos.append(dict(self._base(p), id=len(self.casos) + 1))
            return [(len(self.casos),)]
        if sql.startswith("UPDATE cases SET"):
            columnas = [a.split(" = ")[0] for a in
                        sql[len("UPDATE cases SET "):sql.index(", version = version + 1")].split(", ")]
            *valores, usuario, case_id, version = p
            caso = next((c for c in self.casos if c["id"] == case_id and c["version"] == version), None)
            if caso is None:
                return []
            caso.update(zip(columnas, valores))
            if isinstance(caso.get("form_answers"), str):
                caso["form_answers"] = json.loads(caso["form_answers"])
            caso.update(version=version + 1, updated_by=int(usuario),
                        updated_at=datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc))
            return [(caso["version"],)]
        if sql.startswith("INSERT INTO case_history"):
            self.historial.append(dict(zip(("case_id", "version", "action", "changed_by",
                                            "status_before", "status_after", "changes", "reason",
                                            "device_id"), p)))
            return []
        if sql.startswith("SELECT version FROM cases"):
            return [(c["version"],) for c in self.casos if c["id"] == p[0]]
        if sql.startswith("SELECT region_id FROM cases"):
            return [(c["region_id"],) for c in self.casos if c["id"] == p[0]]
        if sql.startswith("SELECT version, action"):
            return [(h["version"], h["action"], int(h["changed_by"]),
                     datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc), h["status_before"],
                     h["status_after"], json.loads(h["changes"]), h["reason"], h["device_id"])
                    for h in sorted(self.historial, key=lambda h: h["version"]) if h["case_id"] == p[0]]
        if sql.startswith("SELECT id, disease_id, status FROM cases"):
            return [(c["id"], c["disease_id"], c["status"]) for c in self.casos if c["id"] == p[0]]
        if "FROM cases c" in sql and sql.startswith("SELECT count"):
            return [(len(self.filtrar(sql, p)),)]
        if sql.startswith("SELECT c.id"):
            if "WHERE c.local_uuid" in sql:
                return [self._fila(c) for c in self.casos if c["local_uuid"] == p[0]]
            if "WHERE c.id = %s" in sql and "LIMIT" not in sql:
                return [self._fila(c) for c in self.casos if c["id"] == p[0]]
            filas = self.filtrar(sql, p)
            lim, off = p[-2], p[-1]
            return [self._fila(c) for c in filas[off:off + lim]]
        raise AssertionError(sql)

    def filtrar(self, sql, p):
        # Solo el alcance (D43): la lista de regiones es el único parámetro que es lista.
        if "c.region_id = ANY(%s)" in sql:
            regiones = next(v for v in p if isinstance(v, list))
            return [c for c in self.casos if c["region_id"] in regiones]
        return list(self.casos)

    @staticmethod
    def _base(p):
        return dict(local_uuid=p[0], device_id=p[1], reported_by=p[2], disease_id=p[3],
                    region_id=p[4], age=p[5], sex=p[6], onset_date=p[7], report_date=p[8],
                    latitude=p[9], longitude=p[10], test_result=p[11], severity=p[12],
                    synced_at=p[13], status="pendiente", version=1, updated_at=None,
                    updated_by=None, status_reason=None, duplicate_of=None, form_id=p[14],
                    form_answers=json.loads(p[15]) if p[15] else None)


class Cursor:
    def __init__(self, base):
        self.base, self.filas = base, []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def execute(self, sql, params=()):
        self.filas = self.base.ejecutar(" ".join(sql.split()), params)

    def fetchone(self):
        return self.filas[0] if self.filas else None

    def fetchall(self):
        return list(self.filas)


class Conexion:
    def __init__(self, base):
        self.base = base

    def cursor(self):
        return Cursor(self.base)

    def commit(self):
        self.base.commits += 1

    def rollback(self):
        self.base.rollbacks += 1


@pytest.fixture
def base(monkeypatch):
    falsa = BaseFalsa()

    @contextmanager
    def get_conn():
        yield Conexion(falsa)

    monkeypatch.setattr(rutas, "get_conn", get_conn)
    monkeypatch.setattr(datos_captura, "get_enfermedades_para_captura", lambda: ENFERMEDADES)
    monkeypatch.setattr(datos_captura, "get_municipios_catalogo", lambda: MUNICIPIOS)
    simula_dispositivos(monkeypatch, falsa)
    simula_formularios(monkeypatch, falsa)
    return falsa


def simula_formularios(monkeypatch, falsa):
    """Los formularios de la base falsa: por id y la versión publicada de cada enfermedad."""
    monkeypatch.setattr(formularios, "por_id", lambda form_id: falsa.formularios.get(form_id))
    monkeypatch.setattr(formularios, "vigentes", lambda disease_id=None: [
        f for f in falsa.formularios.values() if f["status"] == "publicado"
        and (disease_id is None or f["disease_id"] == disease_id)])


def simula_dispositivos(monkeypatch, falsa):
    """id -> (dueño, revocado). El 3 es de quien firma el token (sub 7)."""
    falsa.dispositivos = {3: (7, False), 4: (7, True), 5: (8, False)}

    def estado(device_id, user_id):
        dueno, revocado = falsa.dispositivos.get(device_id, (None, False))
        return "ajeno" if dueno != user_id else ("revocado" if revocado else "ok")

    monkeypatch.setattr(datos_captura, "estado_para_captura", estado)


@pytest.fixture
def bitacora(monkeypatch):
    eventos = []
    monkeypatch.setattr(rutas, "log_audit",
                        lambda ctx, accion, entidad, entity_id=None, data_before=None,
                        data_after=None, **kw: eventos.append(
                            (ctx.user_id, accion, entidad, entity_id, data_after, kw.get("cur"))))
    return eventos


@pytest.fixture
def cliente(crear_cliente, base, bitacora):
    return crear_cliente("casos")


@pytest.fixture
def captura(token):
    return token(roles=("CAPTURISTA",))


def cuerpo(**cambios):
    datos = {"local_uuid": UUID_A, "device_id": 3, "disease_id": 1, "region_id": 10,
             "report_date": "2026-10-01", "onset_date": "2026-09-28", "age": 34, "sex": "F",
             "latitude": 25.6866, "longitude": -100.3161, "test_result": "positivo",
             "severity": "leve"}
    datos.update(cambios)
    return datos


def test_crear_json_201_y_bitacora(cliente, captura, base, bitacora):
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura)
    assert r.status_code == 201
    caso = r.get_json()
    assert caso["id"] == 1 and caso["duplicado"] is False and caso["status"] == "pendiente"
    assert caso["enfermedad"] == "COVID-19" and caso["municipio"] == "Monterrey"
    assert caso["reported_by"] == 7 and caso["local_uuid"] == UUID_A
    assert base.commits == 1
    assert len(bitacora) == 1
    usuario, accion, entidad, entity_id, despues, cur = bitacora[0]
    assert (usuario, accion, entidad, entity_id) == (7, "CREATE", "cases", 1)
    assert despues["disease_id"] == 1 and cur is not None  # misma transacción


def test_crear_sin_local_uuid_lo_genera(cliente, captura):
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(local_uuid=None, device_id=None),
                     headers=captura)
    assert r.status_code == 201
    assert str(uuid.UUID(r.get_json()["local_uuid"])) == r.get_json()["local_uuid"]
    assert r.get_json()["synced_at"] is None


def test_synced_at_con_device_id(cliente, captura):
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura)
    assert r.get_json()["synced_at"] is not None


@pytest.mark.parametrize("device_id,estado,codigo", [(99, 422, "DATOS_INVALIDOS"),
                                                     (5, 422, "DATOS_INVALIDOS"),
                                                     (4, 409, "CONFLICTO")])
def test_dispositivo_inexistente_ajeno_o_revocado_no_captura(cliente, captura, base, bitacora,
                                                             device_id, estado, codigo):
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(device_id=device_id), headers=captura)
    assert r.status_code == estado and r.get_json()["codigo"] == codigo
    assert base.commits == 0 and bitacora == []


def test_el_reintento_de_un_caso_ya_guardado_no_depende_del_dispositivo(cliente, captura, base):
    assert cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura).status_code == 201
    # Revocar el teléfono no deshace lo que ya había sincronizado.
    base.dispositivos[3] = (7, True)
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura)
    assert r.status_code == 200 and r.get_json()["duplicado"] is True


def test_xml_por_omision_en_la_respuesta(cliente, captura):
    r = cliente.post("/api/v1/cases", json=cuerpo(), headers=captura)
    assert r.status_code == 201 and r.content_type.startswith("application/xml")
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "caso" and raiz.findtext("municipio") == "Monterrey"
    assert raiz.find("duplicado").text == "false"


def test_cuerpo_xml_aceptado(cliente, captura):
    xml = ("<caso><local_uuid>%s</local_uuid><disease_id>1</disease_id><region_id>11</region_id>"
           "<report_date>2026-10-01</report_date><age>40</age><sex>M</sex>"
           "<latitude>25.7</latitude><longitude>-100.3</longitude></caso>" % UUID_A)
    r = cliente.post("/api/v1/cases?format=json", data=xml, headers=dict(
        captura, **{"Content-Type": "application/xml"}))
    assert r.status_code == 201
    assert r.get_json()["municipio"] == "Apodaca" and r.get_json()["age"] == 40


def test_cuerpo_xml_con_atributos_de_tipo(cliente, captura):
    xml = ('<caso><disease_id tipo="numero">1</disease_id><region_id tipo="numero">10</region_id>'
           '<report_date>2026-10-01</report_date><age nil="true"/></caso>')
    r = cliente.post("/api/v1/cases?format=json", data=xml, headers=dict(
        captura, **{"Content-Type": "application/xml"}))
    assert r.status_code == 201 and r.get_json()["age"] is None


def test_local_uuid_repetido_regresa_200_duplicado(cliente, captura, base, bitacora):
    cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura)
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(age=99), headers=captura)
    assert r.status_code == 200
    assert r.get_json()["duplicado"] is True and r.get_json()["id"] == 1
    assert r.get_json()["age"] == 34          # el original, no el reenviado
    assert len(base.casos) == 1 and len(bitacora) == 1


def test_duplicado_no_revalida(cliente, captura):
    cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura)
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(disease_id=999), headers=captura)
    assert r.status_code == 200 and r.get_json()["duplicado"] is True


def test_carrera_por_local_uuid_regresa_duplicado(cliente, captura, base, bitacora):
    base.carrera = True
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura)
    assert r.status_code == 200 and r.get_json()["duplicado"] is True
    assert base.rollbacks == 1 and bitacora == []


@pytest.mark.parametrize("cambios,texto", [
    ({"disease_id": 999}, "enfermedad"),
    ({"region_id": 999}, "municipio"),
    ({"report_date": "2999-01-01"}, "futuro"),
    ({"report_date": "no-es-fecha"}, "formato"),
    ({"report_date": None}, "obligatoria"),
    ({"onset_date": "2026-10-05"}, "posterior"),
    ({"sex": "X"}, "sexo"),
    ({"test_result": "quizas"}, "resultado"),
    ({"severity": "mortal"}, "severidad"),
    ({"age": 500}, "edad"),
    ({"latitude": 95}, "latitud"),
    ({"longitude": None}, "latitud y longitud"),
])
def test_validaciones_422(cliente, captura, base, bitacora, cambios, texto):
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(**cambios), headers=captura)
    assert r.status_code == 422, r.data
    assert r.content_type.startswith("application/problem+json")
    assert r.get_json()["codigo"] == "DATOS_INVALIDOS" and texto in r.get_json()["detail"].lower()
    assert base.casos == [] and bitacora == []


@pytest.mark.parametrize("cambios", [
    {"local_uuid": "123"}, {"device_id": 0}, {"device_id": "abc"}, {"extra": 1},
    {"age": True}, {"age": [1]},
])
def test_entradas_malformadas_422(cliente, captura, cambios):
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(**cambios), headers=captura)
    assert r.status_code == 422


def test_cuerpo_que_no_es_objeto_422(cliente, captura):
    assert cliente.post("/api/v1/cases", json=[1], headers=captura).status_code == 422


def test_cuerpo_ilegible_400_y_tipo_415(cliente, captura):
    r = cliente.post("/api/v1/cases", data="{", headers=dict(
        captura, **{"Content-Type": "application/json"}))
    assert r.status_code == 400
    r = cliente.post("/api/v1/cases", data="x", headers=dict(
        captura, **{"Content-Type": "text/plain"}))
    assert r.status_code == 415


def test_error_en_xml_por_omision(cliente, captura):
    r = cliente.post("/api/v1/cases", json=cuerpo(sex="X"), headers=captura)
    assert r.status_code == 422 and r.content_type.startswith("application/problem+xml")


def test_fk_de_dispositivo_422(cliente, captura, base):
    exc = psycopg2.errors.ForeignKeyViolation("fk_cases_device")
    base.fallo_fk = exc
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura)
    assert r.status_code == 422


def test_sin_token_401(cliente):
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo())
    assert r.status_code == 401 and r.get_json()["codigo"] == "TOKEN_AUSENTE"
    assert cliente.get("/api/v1/cases").status_code == 401
    assert cliente.get("/api/v1/cases/1").status_code == 401


# El ADMINISTRADOR tampoco captura (D1).
@pytest.mark.parametrize("rol", ["EPIDEMIOLOGO", "ANALISTA", "ADMINISTRADOR"])
def test_crear_con_rol_sin_permiso_403(cliente, token, rol):
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=token(roles=(rol,)))
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"


@pytest.mark.parametrize("rol", ["CAPTURISTA", "EPIDEMIOLOGO", "ANALISTA", "ADMINISTRADOR",
                                 "INVESTIGADOR", "AUTORIDAD_SANITARIA"])
def test_los_seis_perfiles_leen(cliente, token, rol):
    assert cliente.get("/api/v1/cases/1", headers=token(roles=(rol,))).status_code == 404
    assert cliente.get("/api/v1/cases?format=json", headers=token(roles=(rol,))).status_code == 200


# ---- alcance por región (D43, D56) ---------------------------------------------------------

def _dos_municipios(cliente, captura):
    for region in (10, 11):
        r = cliente.post("/api/v1/cases?format=json", json=cuerpo(local_uuid=str(uuid.uuid4()), region_id=region),
                         headers=captura)
        assert r.status_code == 201, r.get_json()


def test_con_alcance_la_lista_y_los_incompletos_solo_traen_sus_municipios(cliente, captura, token, alcance_falso):
    _dos_municipios(cliente, captura)
    autoridad = token(roles=("AUTORIDAD_SANITARIA",))
    alcance_falso["regiones"] = [11]
    lista = cliente.get("/api/v1/cases?format=json", headers=autoridad).get_json()
    assert (lista["total"], [c["region_id"] for c in lista["casos"]]) == (1, [11])
    incompletos = cliente.get("/api/v1/cases/incomplete?format=json", headers=autoridad).get_json()
    assert {c["region_id"] for c in incompletos["casos"]} <= {11}
    alcance_falso["regiones"] = None
    assert cliente.get("/api/v1/cases?format=json", headers=autoridad).get_json()["total"] == 2


def test_con_alcance_el_detalle_y_el_historial_de_otro_municipio_son_403(cliente, captura, token, alcance_falso):
    _dos_municipios(cliente, captura)
    autoridad = token(roles=("AUTORIDAD_SANITARIA",))
    alcance_falso["regiones"] = [11]
    assert cliente.get("/api/v1/cases/1?format=json", headers=autoridad).status_code == 403
    assert cliente.get("/api/v1/cases/1/history?format=json", headers=autoridad).status_code == 403
    assert cliente.get("/api/v1/cases/2?format=json", headers=autoridad).status_code == 200
    assert cliente.get("/api/v1/cases/2/history?format=json", headers=autoridad).status_code == 200
    # Un caso que no existe sigue siendo 404, no 403.
    assert cliente.get("/api/v1/cases/99/history?format=json", headers=autoridad).status_code == 404


def test_una_cuenta_nacional_no_hace_la_consulta_de_la_region_del_historial(cliente, captura, base):
    _dos_municipios(cliente, captura)
    assert cliente.get("/api/v1/cases/1/history?format=json", headers=captura).status_code == 200
    assert not [s for s in base.sentencias if "SELECT region_id FROM cases" in s[0]]


def test_redis_caido_503(cliente, captura, apagar_redis):
    apagar_redis()
    r = cliente.get("/api/v1/cases?format=json", headers=captura)
    assert r.status_code == 503


def test_detalle_json_y_xml(cliente, captura):
    cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura)
    r = cliente.get("/api/v1/cases/1?format=json", headers=captura)
    assert r.status_code == 200 and r.get_json()["id"] == 1
    r = cliente.get("/api/v1/cases/1", headers=captura)
    assert r.content_type.startswith("application/xml")
    assert ET.fromstring(r.data).findtext("local_uuid") == UUID_A


def test_detalle_404(cliente, captura):
    r = cliente.get("/api/v1/cases/77?format=json", headers=captura)
    assert r.status_code == 404 and r.get_json()["codigo"] == "NO_ENCONTRADO"


def test_lista_paginada(cliente, captura, base):
    for i in range(5):
        cliente.post("/api/v1/cases?format=json", json=cuerpo(local_uuid=str(uuid.uuid4())),
                     headers=captura)
    r = cliente.get("/api/v1/cases?format=json&page=2&per_page=2", headers=captura)
    datos = r.get_json()
    assert r.status_code == 200
    assert (datos["total"], datos["pagina"], datos["por_pagina"], datos["paginas"]) == (5, 2, 2, 3)
    assert len(datos["casos"]) == 2 and datos["casos"][0]["id"] == 3
    sql, p = base.sentencias[-1]
    assert "LIMIT %s OFFSET %s" in sql and p == (2, 2)


def test_lista_xml(cliente, captura):
    cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura)
    r = cliente.get("/api/v1/cases", headers=captura)
    raiz = ET.fromstring(r.data)
    assert raiz.tag == "lista_casos" and raiz.find("casos").find("item").findtext("id") == "1"
    assert raiz.findtext("total") == "1"


def test_lista_filtros_llegan_a_la_consulta(cliente, captura, base):
    r = cliente.get("/api/v1/cases?format=json&disease_id=1&region_id=10&status=validado"
                    "&sex=F&from=2026-09-01&to=2026-10-31", headers=captura)
    assert r.status_code == 200
    sql, p = base.sentencias[-1]
    assert "c.disease_id = %s" in sql and "c.status = %s" in sql and "c.sex = %s" in sql
    assert "c.report_date >= %s" in sql and "c.report_date <= %s" in sql
    assert p[:6] == (1, 10, "validado", "F", date(2026, 9, 1), date(2026, 10, 31))


@pytest.mark.parametrize("consulta", [
    "page=0", "page=x", "per_page=101", "status=otro", "sex=Z", "from=ayer",
    "from=2026-10-02&to=2026-10-01", "disease_id=0", "region_id=a",
])
def test_filtros_invalidos_422(cliente, captura, consulta):
    r = cliente.get("/api/v1/cases?format=json&" + consulta, headers=captura)
    assert r.status_code == 422


def test_format_desconocido_400(cliente, captura):
    assert cliente.get("/api/v1/cases?format=csv", headers=captura).status_code == 400


# --- POST /api/v1/cases/batch: varios casos en una petición (la usa sincronizacion, F4) -------

UUID_B = "7a2b3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d"
UUID_C = "8b3c4d5e-6f7a-4b2c-9d3e-4f5a6b7c8d9e"
UUID_D = "9c4d5e6f-7a8b-4c3d-8e4f-5a6b7c8d9e0f"


def test_lote_cada_caso_con_su_resultado_y_en_orden(cliente, captura, base, bitacora):
    assert cliente.post("/api/v1/cases?format=json", json=cuerpo(), headers=captura).status_code == 201
    r = cliente.post("/api/v1/cases/batch?format=json", headers=captura, json={"cases": [
        cuerpo(local_uuid=UUID_B),               # nuevo
        cuerpo(),                                # su local_uuid ya existía
        cuerpo(local_uuid=UUID_C, sex="X"),      # datos que no pasan
        cuerpo(local_uuid=UUID_D, device_id=4),  # teléfono revocado
    ]})
    assert r.status_code == 200
    d = r.get_json()
    assert d["total"] == 4
    assert [(f["indice"], f["estado"]) for f in d["resultados"]] == [(0, 201), (1, 200), (2, 422), (3, 409)]
    assert d["resultados"][0]["caso"]["local_uuid"] == UUID_B
    assert d["resultados"][1]["caso"]["duplicado"] is True
    assert d["resultados"][2]["codigo"] == "DATOS_INVALIDOS"
    assert d["resultados"][3]["codigo"] == "CONFLICTO"
    # Cada caso en su transacción: el rechazado no deshace al nuevo.
    assert base.commits == 2 and len(bitacora) == 2


def test_lote_lee_los_catalogos_y_el_dispositivo_una_sola_vez(cliente, captura, base, monkeypatch):
    cuenta = {"catalogo": 0, "dispositivo": 0}
    original = datos_captura.estado_para_captura

    def enfermedades():
        cuenta["catalogo"] += 1
        return ENFERMEDADES

    def estado(device_id, user_id):
        cuenta["dispositivo"] += 1
        return original(device_id, user_id)

    monkeypatch.setattr(datos_captura, "get_enfermedades_para_captura", enfermedades)
    monkeypatch.setattr(datos_captura, "estado_para_captura", estado)
    casos = [cuerpo(local_uuid=str(uuid.uuid4())) for _ in range(5)]
    r = cliente.post("/api/v1/cases/batch?format=json", json={"cases": casos}, headers=captura)
    assert [f["estado"] for f in r.get_json()["resultados"]] == [201] * 5
    assert cuenta == {"catalogo": 1, "dispositivo": 1}


def test_el_lote_cuenta_cada_caso_en_el_limite_de_post_cases(cliente, captura, monkeypatch):
    """Un lote no se brinca el límite de D31: descuenta un caso por caso, de la misma cuenta que
    POST /cases."""
    monkeypatch.setenv("LIMITE_PERMISIVO", "5/60")
    casos = [cuerpo(local_uuid=str(uuid.uuid4())) for _ in range(4)]
    assert cliente.post("/api/v1/cases/batch?format=json", json={"cases": casos},
                        headers=captura).status_code == 200
    assert cliente.post("/api/v1/cases?format=json", json=cuerpo(local_uuid=str(uuid.uuid4())),
                        headers=captura).status_code == 201
    r = cliente.post("/api/v1/cases?format=json", json=cuerpo(local_uuid=str(uuid.uuid4())),
                     headers=captura)
    assert r.status_code == 429 and r.headers.get("Retry-After")
    r = cliente.post("/api/v1/cases/batch?format=json", json={"cases": casos[:1]}, headers=captura)
    assert r.status_code == 429 and r.headers.get("Retry-After")


@pytest.mark.parametrize("cuerpo_lote, texto", [
    ({"cases": []}, "al menos un caso"),
    ({"cases": [{"local_uuid": UUID_B}] * 101}, "máximo 100"),
    ({"cases": ["no es un objeto"]}, "objeto"),
    ({"cases": [{}], "otro": 1}, "no reconocidos"),
])
def test_lote_malformado_422(cliente, captura, cuerpo_lote, texto):
    r = cliente.post("/api/v1/cases/batch?format=json", json=cuerpo_lote, headers=captura)
    assert r.status_code == 422 and texto in r.get_json()["detail"]


def test_solo_el_capturista_envia_lotes(cliente, token):
    r = cliente.post("/api/v1/cases/batch?format=json", json={"cases": [cuerpo()]},
                     headers=token(roles=("ANALISTA",)))
    assert r.status_code == 403
