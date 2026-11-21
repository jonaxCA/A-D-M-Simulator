"""Conexiones a PostgreSQL que se reutilizan, en lugar de abrir una por consulta (F4).

Abrir una conexión cuesta unos 47 ms y la hace PostgreSQL con un proceso nuevo y la verificación
de la contraseña (SCRAM); una consulta sobre una conexión abierta, menos de 1 ms. En la prueba de
carga en la nube (docs/pruebas/carga/2026-11-21_nube_perfiles) cada página abría varias, el mapa
53, y PostgreSQL se quedó sin CPU. Este módulo guarda hasta DB_CONEXIONES_LIBRES (4 por omisión)
conexiones libres por proceso y por URL, y las presta:

- Antes de prestar una, comprueba que siga viva (SELECT 1): si PostgreSQL se reinició, se
  descarta y se abre otra, sin que falle la petición.
- Al devolverla hace rollback, igual que antes al cerrarla: lo que no se confirmó se descarta.
  Nadie deja estado de sesión (SET, autocommit), así que la siguiente la recibe limpia.
- Si algo falla a la mitad, la conexión se cierra en lugar de volver.
- Si no hay libres, se abre otra, como antes: nunca se espera, así que no hay bloqueos aunque una
  función pida otra conexión mientras tiene una.
- Una URL distinta tiene sus propias conexiones: las pruebas que cambian DATABASE_URL (una
  contraseña equivocada, un servidor que no responde) siguen fallando como deben.
"""
import os
import threading
from contextlib import contextmanager

import psycopg2

_grupos = {}
_candado = threading.Lock()


def maximo_libres(entorno=None):
    entorno = os.environ if entorno is None else entorno
    try:
        return max(0, int(entorno.get("DB_CONEXIONES_LIBRES", "4")))
    except ValueError:
        return 4


def _cierra(conn):
    try:
        conn.close()
    except psycopg2.Error:
        pass


def _viva(conn):
    if conn.closed:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.rollback()
        return True
    except psycopg2.Error:
        return False


class _Grupo:
    def __init__(self, url, conecta):
        self.url, self.conecta = url, conecta
        self.libres = []
        self.candado = threading.Lock()

    def tomar(self):
        while True:
            with self.candado:
                conn = self.libres.pop() if self.libres else None
            if conn is None:
                return self.conecta(self.url)
            if _viva(conn):
                return conn
            _cierra(conn)

    def devolver(self, conn):
        if conn.closed:
            return
        try:
            conn.rollback()
        except psycopg2.Error:
            _cierra(conn)
            return
        with self.candado:
            if len(self.libres) < maximo_libres():
                self.libres.append(conn)
                return
        _cierra(conn)


def _grupo(url, conecta):
    with _candado:
        grupo = _grupos.get(url)
        if grupo is None:
            grupo = _grupos[url] = _Grupo(url, conecta)
        return grupo


@contextmanager
def conexion(url, conecta=psycopg2.connect):
    """Una conexión a `url`, prestada. `conecta(url)` abre una nueva cuando hace falta."""
    grupo = _grupo(url, conecta)
    conn = grupo.tomar()
    try:
        yield conn
    except BaseException:
        _cierra(conn)
        raise
    grupo.devolver(conn)


def libres(url):
    """Cuántas conexiones libres hay para `url` (para las pruebas y el diagnóstico)."""
    grupo = _grupos.get(url)
    return len(grupo.libres) if grupo else 0


def vacia():
    """Cierra todas las conexiones libres (para las pruebas)."""
    with _candado:
        grupos = list(_grupos.values())
        _grupos.clear()
    for grupo in grupos:
        with grupo.candado:
            conexiones, grupo.libres = grupo.libres, []
        for conn in conexiones:
            _cierra(conn)
