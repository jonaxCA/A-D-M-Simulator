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
    locales = {int(SCRIPT.FIJOS[v]) for v in ("REDIS_PUERTO_LOCAL", "POSTGRES_PUERTO_LOCAL",
                                              "MONGO_PUERTO_LOCAL")}
    assert set(SCRIPT.PUERTOS) == publicados | locales


def test_el_segundo_simulador_no_publica_puerto():
    pruebas = (RAIZ / "infra/docker-compose.pruebas.yml").read_text(encoding="utf-8")
    assert "  simulador-2:\n    extends:\n      file: docker-compose.yml\n      service: simulador\n" in pruebas
    assert "    ports: !reset []\n" in pruebas


def _servicios_con_puerto():
    """Los servicios del compose principal que publican su puerto 8000."""
    nombres, actual = set(), None
    for linea in COMPOSE.splitlines():
        encabezado = re.match(r"^  ([a-z][a-z0-9-]*):$", linea)
        if encabezado:
            actual = encabezado.group(1)
        elif re.match(r'^      - "\d+:8000"$', linea):
            nombres.add(actual)
    return nombres


def test_nginx_enruta_cada_servicio_del_directorio_y_la_consola():
    plantilla = (RAIZ / "infra/nginx/templates/default.conf.template").read_text(encoding="utf-8")
    ruta = re.search(r"\(\?<servicio>([a-z|-]+)\)", plantilla).group(1).split("|")
    assert sorted(ruta) == sorted(set(SERVICIOS) | {"consola"})
    assert len(ruta) == len(set(ruta))


def test_detras_de_nginx_ningun_servicio_publica_su_puerto():
    """docker-compose.nginx.yml le quita el puerto y prende DETRAS_DE_PROXY a todo servicio que
    lo publique en el compose principal: si falta uno, quien llegue directo falsea su IP."""
    nginx = (RAIZ / "infra/docker-compose.nginx.yml").read_text(encoding="utf-8")
    sin_puerto = set(re.findall(r"^  ([a-z][a-z0-9-]*): \*detras-de-nginx$", nginx, re.M))
    sin_puerto |= set(re.findall(r"^  ([a-z][a-z0-9-]*):\n    <<: \*detras-de-nginx$", nginx, re.M))
    assert sin_puerto == _servicios_con_puerto()
    assert "  ports: !reset []\n  environment:\n    DETRAS_DE_PROXY: \"1\"\n" in nginx


def test_el_modo_nginx_revisa_sus_puertos_y_corre_su_prueba():
    assert SCRIPT.PUERTOS_NGINX == [80, 443]
    assert (SCRIPT.CONTENEDORES / "test_compose_nginx.py").exists()
    assert SCRIPT.ARCHIVO_NGINX[-1].endswith("docker-compose.nginx.yml")


def test_cada_variable_de_la_plantilla_de_nginx_tiene_valor():
    """La imagen de nginx solo sustituye las variables definidas: una que falte quedaría como
    ${...} en la configuración y nginx no arrancaría. Let's Encrypt cambia las del certificado."""
    plantilla = (RAIZ / "infra/nginx/templates/default.conf.template").read_text(encoding="utf-8")
    usadas = set(re.findall(r"\$\{([A-Z_]+)\}", plantilla))
    nginx = (RAIZ / "infra/docker-compose.nginx.yml").read_text(encoding="utf-8")
    definidas = set(re.findall(r"^      ([A-Z_]+): ", nginx, re.M))
    assert usadas <= definidas, usadas - definidas
    letsencrypt = (RAIZ / "infra/docker-compose.letsencrypt.yml").read_text(encoding="utf-8")
    for variable in ("NGINX_DOMINIO", "NGINX_CERTIFICADO", "NGINX_LLAVE"):
        assert "      %s: " % variable in letsencrypt
    assert "${DOMINIO:?" in letsencrypt
    assert "/etc/letsencrypt/live/${DOMINIO}/fullchain.pem" in letsencrypt
