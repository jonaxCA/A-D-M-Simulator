"""Cada rol de PostgreSQL solo escribe lo suyo (bloque L), contra la base del compose de pruebas.

Las sentencias no tocan ninguna fila (WHERE false), pero PostgreSQL revisa el permiso antes.
"""
import pytest
from psycopg2 import errors

NEGADAS = [
    ("regiones", "INSERT INTO scenarios (name) SELECT 'x' WHERE false"),
    ("aprobacion", "UPDATE scenario_versions SET population_size = population_size WHERE false"),
    ("casos", "INSERT INTO scenarios (name) SELECT 'x' WHERE false"),
    ("zonas", "INSERT INTO cases (local_uuid) SELECT NULL WHERE false"),
    ("comparacion", "UPDATE simulation_runs SET status = status WHERE false"),
    ("resultados", "INSERT INTO simulation_results (run_id) SELECT 1 WHERE false"),
    ("notificaciones", "UPDATE notifications SET title = title WHERE false"),
    ("pareto", "SELECT password_hash FROM users LIMIT 1"),
    ("estado-servicios", "SELECT 1 FROM users LIMIT 1"),
]
PERMITIDAS = [
    ("aprobacion", "UPDATE scenario_versions SET status = status WHERE false"),
    ("casos", "INSERT INTO cases (local_uuid) SELECT NULL WHERE false"),
    ("notificaciones", "UPDATE notifications SET read_at = read_at WHERE false"),
    ("pareto", "SELECT full_name FROM users LIMIT 1"),
]


def ejecuta(base, servicio, sql):
    conexion = base(servicio)
    try:
        with conexion.cursor() as cur:
            cur.execute(sql)
    finally:
        conexion.rollback()
        conexion.close()


@pytest.mark.parametrize("servicio,sql", NEGADAS)
def test_no_puede_escribir_ni_leer_lo_de_otro(base, servicio, sql):
    with pytest.raises(errors.InsufficientPrivilege):
        ejecuta(base, servicio, sql)


@pytest.mark.parametrize("servicio,sql", PERMITIDAS)
def test_si_puede_lo_suyo(base, servicio, sql):
    ejecuta(base, servicio, sql)


def test_un_rol_por_servicio_y_ninguno_privilegiado(base):
    conexion = base()
    with conexion.cursor() as cur:
        cur.execute("SELECT count(*), count(*) FILTER (WHERE rolsuper OR rolcreaterole OR rolcreatedb "
                    "OR rolbypassrls) FROM pg_roles WHERE starts_with(rolname, 'svc_')")
        assert cur.fetchone() == (26, 0)
    conexion.close()
