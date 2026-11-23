# Archivos en disco o en Cloud Storage (D30), según ARCHIVOS. Con ARCHIVOS=gcs usa el bucket
# BUCKET_NOMBRE: con STORAGE_EMULATOR_HOST, el emulador del compose; sin él, las credenciales de
# la máquina de GCP, que firman las URLs con signBlob (sin llaves en el .env). ARCHIVOS=disco
# (o sin la variable) guarda en ARCHIVOS_DIR, para pruebas y fuera de Docker, y no firma URLs.
import functools
import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

MINUTOS = 15
ESPERA = 10
CARPETA = "/var/lib/epidemia/archivos"


class BucketNoDisponible(Exception):
    pass


def respaldo():
    return os.environ.get("ARCHIVOS", "").strip().lower() or "disco"


def configurado():
    if respaldo() == "gcs":
        return bool(os.environ.get("BUCKET_NOMBRE"))
    return bool(os.environ.get("ARCHIVOS") or os.environ.get("ARCHIVOS_DIR"))


def _emulador():
    return os.environ.get("STORAGE_EMULATOR_HOST", "").strip()


def _carpeta():
    return Path(os.environ.get("ARCHIVOS_DIR") or CARPETA)


def _en_disco(objeto):
    return _carpeta() / objeto


@functools.lru_cache(maxsize=None)
def _cliente():
    from google.cloud import storage
    if _emulador():
        from google.auth.credentials import AnonymousCredentials
        return storage.Client(project="epidemia", credentials=AnonymousCredentials())
    return storage.Client()


def _blob(objeto):
    return _cliente().bucket(os.environ["BUCKET_NOMBRE"]).blob(objeto)


def _errores_del_bucket():
    import requests
    from google.api_core.exceptions import GoogleAPIError
    from google.auth.exceptions import GoogleAuthError
    return GoogleAPIError, GoogleAuthError, requests.RequestException


def guardar(objeto, datos, tipo):
    if respaldo() == "disco":
        try:
            ruta = _en_disco(objeto)
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(datos)
        except OSError as exc:
            raise BucketNoDisponible(str(exc)) from exc
        return
    try:
        _blob(objeto).upload_from_string(datos, content_type=tipo, timeout=ESPERA, retry=None)
    except _errores_del_bucket() as exc:
        raise BucketNoDisponible(type(exc).__name__) from exc


def leer(objeto):
    if respaldo() == "disco":
        try:
            return _en_disco(objeto).read_bytes()
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise BucketNoDisponible(str(exc)) from exc
    from google.api_core.exceptions import NotFound
    try:
        return _blob(objeto).download_as_bytes(timeout=ESPERA)
    except NotFound:
        raise FileNotFoundError(objeto)
    except _errores_del_bucket() as exc:
        raise BucketNoDisponible(type(exc).__name__) from exc


def borrar(objeto):
    if respaldo() == "disco":
        _en_disco(objeto).unlink(missing_ok=True)
        return
    from google.api_core.exceptions import NotFound
    try:
        _blob(objeto).delete(timeout=ESPERA, retry=None)
    except NotFound:
        pass
    except _errores_del_bucket() as exc:
        raise BucketNoDisponible(type(exc).__name__) from exc


def _firmante_del_emulador():
    from google.auth.credentials import AnonymousCredentials, Signing

    # El emulador no revisa la firma: basta una con la forma de V4.
    class Firmante(AnonymousCredentials, Signing):
        signer_email = "emulador@epidemia.local"
        signer = None

        def sign_bytes(self, mensaje):
            return hashlib.sha256(mensaje).digest()
    return Firmante()


def _firma_de_gcp():
    import google.auth
    from google.auth.credentials import Signing
    from google.auth.transport.requests import Request
    credenciales, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if isinstance(credenciales, Signing):
        return {"credentials": credenciales}
    if not credenciales.valid:
        credenciales.refresh(Request())
    # La VM no tiene llave privada: la biblioteca firma con signBlob de IAM.
    return {"service_account_email": credenciales.service_account_email,
            "access_token": credenciales.token}


def url_firmada(objeto, minutos=MINUTOS, nombre=None):
    if respaldo() == "disco":
        raise BucketNoDisponible("El almacenamiento en disco no firma URLs.")
    duracion = timedelta(minutes=minutos)
    vence = datetime.now(timezone.utc).replace(microsecond=0) + duracion
    opciones = {"version": "v4", "expiration": duracion, "method": "GET"}
    if nombre:
        opciones["response_disposition"] = 'inline; filename="%s"' % nombre
    try:
        if _emulador():
            opciones.update(credentials=_firmante_del_emulador(),
                            api_access_endpoint=os.environ.get("BUCKET_URL_PUBLICA") or _emulador())
        else:
            opciones.update(_firma_de_gcp())
        return _blob(objeto).generate_signed_url(**opciones), vence
    except _errores_del_bucket() as exc:
        raise BucketNoDisponible(type(exc).__name__) from exc


def ping():
    if respaldo() == "disco":
        return _carpeta().is_dir() and os.access(_carpeta(), os.W_OK)
    # Listar un objeto, no bucket.exists(): la cuenta de la máquina solo tiene
    # storage.objectAdmin sobre el bucket, que no incluye storage.buckets.get.
    objetos = _cliente().list_blobs(os.environ["BUCKET_NOMBRE"], max_results=1, timeout=2, retry=None)
    next(iter(objetos), None)
    return True
