"""El préstamo de conexiones a PostgreSQL (epidemia_comun/conexiones.py, F4), con conexiones
falsas: sin base de datos."""
import psycopg2
import pytest

from epidemia_comun import conexiones


class Falsa:
    def __init__(self, n, viva=True):
        self.n, self.viva = n, viva
        self.closed = 0
        self.rollbacks = 0

    def cursor(self):
        conn = self

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql):
                if not conn.viva:
                    raise psycopg2.OperationalError("server closed the connection unexpectedly")
        return Cursor()

    def rollback(self):
        if not self.viva:
            raise psycopg2.InterfaceError("connection already closed")
        self.rollbacks += 1

    def close(self):
        self.closed = 1


@pytest.fixture
def abiertas(monkeypatch):
    conexiones.vacia()
    monkeypatch.setenv("DB_CONEXIONES_LIBRES", "4")
    lista = []

    def conecta(url):
        lista.append(Falsa(len(lista)))
        return lista[-1]
    yield lista, conecta
    conexiones.vacia()


def test_una_conexion_se_reutiliza_y_vuelve_con_rollback(abiertas):
    lista, conecta = abiertas
    with conexiones.conexion("pg://a", conecta) as c1:
        pass
    with conexiones.conexion("pg://a", conecta) as c2:
        pass
    assert c1 is c2 and len(lista) == 1
    # Una al devolverla y otra al comprobar que sigue viva antes de prestarla.
    assert c1.rollbacks >= 2 and conexiones.libres("pg://a") == 1


def test_si_algo_falla_a_la_mitad_la_conexion_se_cierra(abiertas):
    lista, conecta = abiertas
    with pytest.raises(ValueError):
        with conexiones.conexion("pg://a", conecta) as c1:
            raise ValueError("a la mitad")
    assert c1.closed and conexiones.libres("pg://a") == 0
    with conexiones.conexion("pg://a", conecta) as c2:
        pass
    assert c2 is not c1


def test_una_conexion_muerta_se_descarta_sin_que_falle_la_peticion(abiertas):
    """PostgreSQL se reinició: la conexión guardada ya no sirve y se abre otra."""
    lista, conecta = abiertas
    with conexiones.conexion("pg://a", conecta) as c1:
        pass
    c1.viva = False
    with conexiones.conexion("pg://a", conecta) as c2:
        pass
    assert c2 is not c1 and c1.closed and len(lista) == 2


def test_no_guarda_mas_libres_que_el_maximo_ni_se_bloquea_al_anidar(abiertas, monkeypatch):
    lista, conecta = abiertas
    monkeypatch.setenv("DB_CONEXIONES_LIBRES", "1")
    with conexiones.conexion("pg://a", conecta) as c1:
        # Pedir otra mientras se tiene una abre una nueva: nunca espera.
        with conexiones.conexion("pg://a", conecta) as c2:
            assert c2 is not c1
    assert conexiones.libres("pg://a") == 1 and sum(c.closed for c in lista) == 1


def test_cada_url_tiene_sus_propias_conexiones(abiertas):
    lista, conecta = abiertas
    with conexiones.conexion("pg://a", conecta) as c1:
        pass
    with conexiones.conexion("pg://otra", conecta) as c2:
        pass
    assert c1 is not c2 and len(lista) == 2


def test_con_cero_libres_se_comporta_como_antes(abiertas, monkeypatch):
    lista, conecta = abiertas
    monkeypatch.setenv("DB_CONEXIONES_LIBRES", "0")
    for _ in range(3):
        with conexiones.conexion("pg://a", conecta):
            pass
    assert len(lista) == 3 and all(c.closed for c in lista)


def test_el_maximo_viene_del_entorno():
    assert conexiones.maximo_libres({}) == 4
    assert conexiones.maximo_libres({"DB_CONEXIONES_LIBRES": "10"}) == 10
    assert conexiones.maximo_libres({"DB_CONEXIONES_LIBRES": "x"}) == 4
