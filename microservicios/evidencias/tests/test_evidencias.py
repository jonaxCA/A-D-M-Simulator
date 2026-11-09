import hashlib
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from backend_web import evidencias
from microservicios.evidencias import rutas

RAIZ = Path(__file__).resolve().parents[3]
PROPIO, AJENO = 418, 500       # el 418 lo reportó quien firma el token (sub 7); el 500, la cuenta 8
JPEG = b"\xff\xd8\xff\xe0" + b"foto" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"otra" * 16


class Mundo:
    """backend_web.evidencias simulado, con archivos de verdad en `carpeta`."""

    def __init__(self, carpeta):
        self.carpeta = carpeta
        self.casos = {PROPIO: {"id": PROPIO, "reported_by": 7}, AJENO: {"id": AJENO, "reported_by": 8}}
        self.filas, self.archivos, self.guardadas, self.borradas = {}, {}, [], []

    def get_caso(self, case_id):
        return dict(self.casos[case_id]) if case_id in self.casos else None

    def guardar_evidencia(self, case_id, datos, user_id, carpeta, *, contexto):
        self.guardadas.append((case_id, user_id, carpeta, contexto.user_id))
        huella = hashlib.sha256(datos).hexdigest()
        previa = next((f for f in self.filas.values()
                       if f["case_id"] == case_id and f["sha256"] == huella), None)
        if previa:
            return dict(previa), False
        evidencia_id = len(self.filas) + 1
        self.filas[evidencia_id] = {
            "id": evidencia_id, "case_id": case_id, "mime_type": evidencias.tipo_por_contenido(datos),
            "size_bytes": len(datos), "sha256": huella, "privacy": "privado", "uploaded_by": user_id,
            "uploaded_at": datetime(2026, 11, 1, 17, tzinfo=timezone.utc)}
        ruta = Path(carpeta) / ("%d.bin" % evidencia_id)
        ruta.write_bytes(datos)
        self.archivos[evidencia_id] = ruta
        return dict(self.filas[evidencia_id]), True

    def listar_evidencias(self, case_id):
        return [dict(f) for f in self.filas.values() if f["case_id"] == case_id]

    def get_evidencia(self, evidencia_id):
        return dict(self.filas[evidencia_id]) if evidencia_id in self.filas else None

    def archivo_de_evidencia(self, evidencia_id, carpeta):
        if evidencia_id not in self.filas:
            return None, None
        return dict(self.filas[evidencia_id]), self.archivos[evidencia_id]

    def borrar_evidencia(self, evidencia_id, carpeta, *, contexto):
        self.borradas.append((evidencia_id, contexto.user_id))
        return self.filas.pop(evidencia_id, None)


@pytest.fixture
def mundo(monkeypatch, tmp_path):
    monkeypatch.setenv("EVIDENCIAS_DIR", str(tmp_path))
    m = Mundo(tmp_path)
    for nombre in ("get_caso", "guardar_evidencia", "listar_evidencias", "get_evidencia",
                   "archivo_de_evidencia", "borrar_evidencia"):
        monkeypatch.setattr(evidencias, nombre, getattr(m, nombre))
    return m


@pytest.fixture
def cliente(crear_cliente, mundo):
    return crear_cliente("evidencias")


@pytest.fixture
def capturista(token):
    return token(("CAPTURISTA",))


def subir(cliente, cabeceras, datos=JPEG, caso=PROPIO, tipo="image/jpeg"):
    return cliente.post("/api/v1/cases/%d/attachments?format=json" % caso, data=datos,
                        headers=cabeceras, content_type=tipo)


# ---- subir ----------------------------------------------------------------------------

def test_sin_token_es_401(cliente):
    assert cliente.post("/api/v1/cases/%d/attachments" % PROPIO, data=JPEG).status_code == 401


@pytest.mark.parametrize("rol", ["ANALISTA", "EPIDEMIOLOGO"])
def test_quien_no_captura_no_sube(cliente, token, mundo, rol):
    assert subir(cliente, token((rol,))).status_code == 403
    assert mundo.guardadas == []


def test_quien_reporto_el_caso_sube_y_el_reintento_no_duplica(cliente, capturista, mundo, tmp_path):
    r = subir(cliente, capturista)
    assert r.status_code == 201
    assert r.get_json()["mime_type"] == "image/jpeg" and r.get_json()["case_id"] == PROPIO
    assert mundo.guardadas == [(PROPIO, 7, tmp_path, 7)]
    r = subir(cliente, capturista)
    assert r.status_code == 200 and r.get_json()["id"] == 1


def test_el_tipo_sale_del_contenido_no_del_encabezado(cliente, capturista):
    r = subir(cliente, capturista, datos=PNG, tipo="image/jpeg")
    assert r.status_code == 201 and r.get_json()["mime_type"] == "image/png"
    assert subir(cliente, capturista, datos=JPEG, tipo="application/octet-stream").status_code == 201


def test_el_caso_de_otra_persona_solo_lo_toca_administrador(cliente, capturista, token, mundo):
    r = subir(cliente, capturista, caso=AJENO)
    assert r.status_code == 403 and r.get_json()["codigo"] == "PERMISO_INSUFICIENTE"
    assert mundo.guardadas == []
    assert subir(cliente, token(("ADMINISTRADOR",)), caso=AJENO).status_code == 201


@pytest.mark.parametrize("datos,tipo", [(b"", "image/jpeg"), (b"GIF89a" + b"x" * 20, "image/gif"),
                                        (b"MZ ejecutable", "application/octet-stream"),
                                        (b"--x\r\nContent-Disposition: form-data; name=\"foto\"\r\n\r\n",
                                         "multipart/form-data; boundary=x")])
def test_archivo_invalido_es_422(cliente, capturista, mundo, datos, tipo):
    r = subir(cliente, capturista, datos=datos, tipo=tipo)
    assert r.status_code == 422 and r.get_json()["codigo"] == "DATOS_INVALIDOS"
    assert mundo.guardadas == []


def test_mas_de_20_mb_es_413(cliente, capturista, mundo, monkeypatch):
    monkeypatch.setattr(evidencias, "MAXIMO", len(JPEG) - 1)
    assert subir(cliente, capturista).status_code == 413
    assert mundo.guardadas == []


def test_caso_inexistente_es_404_y_id_invalido_422(cliente, capturista):
    assert subir(cliente, capturista, caso=999).status_code == 404
    r = cliente.post("/api/v1/cases/x/attachments", data=JPEG, headers=capturista)
    assert r.status_code == 422


# ---- consultar, descargar y borrar ----------------------------------------------------

@pytest.mark.parametrize("rol", rutas.ROLES_LEEN)
def test_los_que_leen_casos_ven_las_evidencias(cliente, capturista, token, rol):
    subir(cliente, capturista)
    subir(cliente, capturista, datos=PNG)
    r = cliente.get("/api/v1/cases/%d/attachments?format=json" % PROPIO, headers=token((rol,)))
    assert r.status_code == 200 and r.get_json()["total"] == 2
    assert cliente.get("/api/v1/attachments/1", headers=token((rol,))).status_code == 200


def test_lista_en_xml_con_un_elemento_por_evidencia(cliente, capturista):
    subir(cliente, capturista)
    raiz = ET.fromstring(cliente.get("/api/v1/cases/%d/attachments" % PROPIO, headers=capturista).data)
    assert raiz.tag == "evidencias_caso"
    assert [e.findtext("mime_type") for e in raiz.findall("evidencias/evidencia")] == ["image/jpeg"]


def test_descargar_regresa_el_archivo_tal_cual(cliente, capturista, token):
    subir(cliente, capturista)
    r = cliente.get("/api/v1/attachments/1/content", headers=token(("EPIDEMIOLOGO",)))
    assert r.status_code == 200 and r.data == JPEG and r.mimetype == "image/jpeg"
    assert r.headers["Content-Disposition"] == 'inline; filename="evidencia-1.jpg"'
    assert r.headers["Cache-Control"] == "private, no-store"
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_descargar_sin_archivo_o_sin_evidencia_es_404(cliente, capturista, mundo):
    subir(cliente, capturista)
    mundo.archivos[1].unlink()
    assert cliente.get("/api/v1/attachments/1/content", headers=capturista).status_code == 404
    assert cliente.get("/api/v1/attachments/9/content", headers=capturista).status_code == 404
    assert cliente.get("/api/v1/attachments/9", headers=capturista).status_code == 404


def test_solo_administrador_borra(cliente, capturista, token, mundo):
    subir(cliente, capturista)
    assert cliente.delete("/api/v1/attachments/1", headers=capturista).status_code == 403
    r = cliente.delete("/api/v1/attachments/1?format=json", headers=token(("ADMINISTRADOR",)))
    assert r.status_code == 200 and r.get_json()["id"] == 1
    assert mundo.borradas == [(1, 7)]
    assert cliente.delete("/api/v1/attachments/1", headers=token(("ADMINISTRADOR",))).status_code == 404


def test_redis_caido_es_503(cliente, capturista, apagar_redis):
    apagar_redis()
    assert cliente.get("/api/v1/attachments/1", headers=capturista).status_code == 503


def test_contrato_servido_es_el_del_repo(cliente):
    r = cliente.get("/openapi.json")
    assert r.data == (RAIZ / "docs/contratos/evidencias/openapi.json").read_bytes()
