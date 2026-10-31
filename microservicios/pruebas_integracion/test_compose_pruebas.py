"""El compose de las pruebas de integración, sin Docker: que nunca caiga sobre la base de la
demostración y que el script revise todos los puertos que publica."""
import importlib.util
import re
from pathlib import Path

from microservicios.estado_servicios.sondeo import SERVICIOS

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE = (RAIZ / "infra/docker-compose.yml").read_text(encoding="utf-8")
espec = importlib.util.spec_from_file_location("pruebas_integracion", RAIZ / "infra/pruebas_integracion.py")
SCRIPT = importlib.util.module_from_spec(espec)
espec.loader.exec_module(SCRIPT)


def test_cada_servicio_toma_la_base_de_postgres_db():
    urls = re.findall(r"^      DATABASE_URL: (.*)$", COMPOSE, re.M)
    assert len(urls) == len(SERVICIOS)
    assert all(u.endswith("@postgres:5432/${POSTGRES_DB:-simulador_epidemico}}") for u in urls)
    assert "      POSTGRES_DB: ${POSTGRES_DB:-simulador_epidemico}\n" in COMPOSE


def test_las_pruebas_van_en_otro_proyecto_y_otra_base():
    assert SCRIPT.PROYECTO != "epidemia"
    assert SCRIPT.FIJOS["POSTGRES_DB"] == "simulador_epidemico_pruebas"
    assert SCRIPT.ENTORNO.name.startswith(".env.")


def test_el_script_revisa_todos_los_puertos_publicados():
    publicados = {int(p) for p in re.findall(r'^      - "(\d+):8000"$', COMPOSE, re.M)}
    # Cada servicio y la consola.
    assert len(publicados) == len(SERVICIOS) + 1
    locales = {int(SCRIPT.FIJOS["REDIS_PUERTO_LOCAL"]), int(SCRIPT.FIJOS["POSTGRES_PUERTO_LOCAL"])}
    assert set(SCRIPT.PUERTOS) == publicados | locales


def test_el_segundo_simulador_no_publica_puerto():
    pruebas = (RAIZ / "infra/docker-compose.pruebas.yml").read_text(encoding="utf-8")
    assert "  simulador-2:\n    extends:\n      file: docker-compose.yml\n      service: simulador\n" in pruebas
    assert "    ports: !reset []\n" in pruebas
