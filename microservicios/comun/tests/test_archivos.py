import os
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from google.api_core.exceptions import NotFound, ServiceUnavailable

from epidemia_comun import archivos
from epidemia_comun.archivos import BucketNoDisponible

# Para probar contra un emulador de verdad: EMULADOR_BUCKET_PRUEBAS=http://localhost:4443,
# con el bucket epidemia-archivos creado.
EMULADOR = os.environ.get("EMULADOR_BUCKET_PRUEBAS")


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    for nombre in ("ARCHIVOS", "ARCHIVOS_DIR", "BUCKET_NOMBRE", "STORAGE_EMULATOR_HOST",
                   "BUCKET_URL_PUBLICA"):
        monkeypatch.delenv(nombre, raising=False)
    archivos._cliente.cache_clear()
    yield
    archivos._cliente.cache_clear()


@pytest.fixture
def en_disco(monkeypatch, tmp_path):
    monkeypatch.setenv("ARCHIVOS", "disco")
    monkeypatch.setenv("ARCHIVOS_DIR", str(tmp_path))
    return tmp_path


class BlobFalso:
    def __init__(self, error=None):
        self.error, self.llamadas = error, []

    def _llamada(self, nombre, *args, **kwargs):
        self.llamadas.append((nombre, args, kwargs))
        if self.error:
            raise self.error
        return b"datos" if nombre == "download_as_bytes" else "https://firmada"

    def upload_from_string(self, *a, **k):
        return self._llamada("upload_from_string", *a, **k)

    def download_as_bytes(self, *a, **k):
        return self._llamada("download_as_bytes", *a, **k)

    def delete(self, *a, **k):
        return self._llamada("delete", *a, **k)

    def generate_signed_url(self, *a, **k):
        return self._llamada("generate_signed_url", *a, **k)


@pytest.fixture
def en_gcs(monkeypatch):
    monkeypatch.setenv("ARCHIVOS", "gcs")
    monkeypatch.setenv("BUCKET_NOMBRE", "epidemia-archivos")

    def con(blob):
        monkeypatch.setattr(archivos, "_blob", lambda objeto: blob)
        return blob
    return con


def test_disco_guarda_lee_y_borra(en_disco):
    archivos.guardar("evidencias/1/a.jpg", b"\xff\xd8\xff", "image/jpeg")
    assert (en_disco / "evidencias/1/a.jpg").read_bytes() == b"\xff\xd8\xff"
    assert archivos.leer("evidencias/1/a.jpg") == b"\xff\xd8\xff"
    archivos.borrar("evidencias/1/a.jpg")
    archivos.borrar("evidencias/1/a.jpg")
    with pytest.raises(FileNotFoundError):
        archivos.leer("evidencias/1/a.jpg")


def test_disco_no_firma_urls_y_su_ping(en_disco):
    with pytest.raises(BucketNoDisponible):
        archivos.url_firmada("evidencias/1/a.jpg")
    assert archivos.ping() is True
    assert archivos.configurado()


def test_sin_variables_no_esta_configurado():
    assert archivos.respaldo() == "disco" and not archivos.configurado()


def test_gcs_sin_nombre_no_esta_configurado(monkeypatch):
    monkeypatch.setenv("ARCHIVOS", "gcs")
    assert not archivos.configurado()


def test_gcs_sube_con_su_tipo_y_sin_reintentar(en_gcs):
    blob = en_gcs(BlobFalso())
    archivos.guardar("reportes/1/a.pdf", b"%PDF-", "application/pdf")
    nombre, args, kwargs = blob.llamadas[0]
    assert nombre == "upload_from_string" and args == (b"%PDF-",)
    assert kwargs["content_type"] == "application/pdf" and kwargs["retry"] is None


@pytest.mark.parametrize("error", [ServiceUnavailable("caido"), requests.ConnectionError("rechazada")])
def test_gcs_caido_es_bucket_no_disponible(en_gcs, error):
    en_gcs(BlobFalso(error))
    for operacion in (lambda: archivos.guardar("a", b"x", "image/png"),
                      lambda: archivos.leer("a"), lambda: archivos.borrar("a")):
        with pytest.raises(BucketNoDisponible):
            operacion()


def test_gcs_objeto_que_no_existe(en_gcs):
    en_gcs(BlobFalso(NotFound("no")))
    with pytest.raises(FileNotFoundError):
        archivos.leer("a")
    archivos.borrar("a")


def test_url_firmada_con_el_emulador_vence_en_15_minutos(monkeypatch):
    monkeypatch.setenv("ARCHIVOS", "gcs")
    monkeypatch.setenv("BUCKET_NOMBRE", "epidemia-archivos")
    monkeypatch.setenv("STORAGE_EMULATOR_HOST", "http://bucket:4443")
    monkeypatch.setenv("BUCKET_URL_PUBLICA", "http://localhost:4443")
    url, vence = archivos.url_firmada("evidencias/7/a.jpg", nombre="evidencia-3.jpg")
    partes = urlsplit(url)
    consulta = parse_qs(partes.query)
    assert f"{partes.scheme}://{partes.netloc}{partes.path}" == \
        "http://localhost:4443/epidemia-archivos/evidencias/7/a.jpg"
    assert consulta["X-Goog-Expires"] == ["900"]
    assert consulta["X-Goog-Algorithm"] == ["GOOG4-RSA-SHA256"]
    assert consulta["response-content-disposition"] == ['inline; filename="evidencia-3.jpg"']
    falta = vence - datetime.now(timezone.utc)
    assert timedelta(minutes=14) < falta <= timedelta(minutes=15)


def test_url_firmada_en_gcp_usa_signblob(en_gcs, monkeypatch):
    import google.auth

    class CredencialesDeLaVM:
        valid, token, service_account_email = False, None, "default"

        def refresh(self, peticion):
            self.valid, self.token = True, "token-de-acceso"
            self.service_account_email = "epidemia@proyecto.iam.gserviceaccount.com"

    monkeypatch.setattr(google.auth, "default", lambda scopes: (CredencialesDeLaVM(), "proyecto"))
    blob = en_gcs(BlobFalso())
    url, _ = archivos.url_firmada("reportes/2/a.pdf", minutos=5)
    _, _, kwargs = blob.llamadas[0]
    assert url == "https://firmada"
    assert kwargs["service_account_email"] == "epidemia@proyecto.iam.gserviceaccount.com"
    assert kwargs["access_token"] == "token-de-acceso"
    assert kwargs["expiration"] == timedelta(minutes=5) and kwargs["version"] == "v4"
    assert "api_access_endpoint" not in kwargs


@pytest.mark.skipif(not EMULADOR, reason="Sin EMULADOR_BUCKET_PRUEBAS")
def test_contra_el_emulador(monkeypatch):
    monkeypatch.setenv("ARCHIVOS", "gcs")
    monkeypatch.setenv("BUCKET_NOMBRE", "epidemia-archivos")
    monkeypatch.setenv("STORAGE_EMULATOR_HOST", EMULADOR)
    archivos.guardar("pruebas/a.png", b"\x89PNG\r\n\x1a\nhola", "image/png")
    assert archivos.leer("pruebas/a.png") == b"\x89PNG\r\n\x1a\nhola"
    url, _ = archivos.url_firmada("pruebas/a.png")
    respuesta = requests.get(url, timeout=5)
    assert respuesta.status_code == 200 and respuesta.content.endswith(b"hola")
    archivos.borrar("pruebas/a.png")
    with pytest.raises(FileNotFoundError):
        archivos.leer("pruebas/a.png")
    assert archivos.ping() is True
