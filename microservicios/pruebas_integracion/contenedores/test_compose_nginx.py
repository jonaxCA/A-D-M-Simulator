"""nginx como única entrada (D25, D26), de punta a punta: prefijo por servicio, HTTPS, las URL
del directorio, servicios sin puerto publicado, límites por IP y tiempo máximo (RNF-C10).

Solo corre con python infra/pruebas_integracion.py --nginx, que suma
infra/docker-compose.nginx.yml y pone EPIDEMIA_PRUEBAS_NGINX; sin eso, se salta. El
certificado de infra/nginx/certs/ puede ser autofirmado, así que no se verifica aquí.
"""
import os
import re
import socket
import time

import pytest

from microservicios.estado_servicios.sondeo import SERVICIOS

NGINX = os.environ.get("EPIDEMIA_PRUEBAS_NGINX")
pytestmark = pytest.mark.skipif(not NGINX, reason="Sin --nginx: los servicios no están detrás de nginx.")


def pide(metodo, ruta, **opciones):
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    opciones.setdefault("timeout", 20)
    opciones.setdefault("verify", False)
    return requests.request(metodo, NGINX + ruta, **opciones)


def test_http_redirige_a_https():
    import requests
    r = requests.get("http://localhost/estado-servicios/health", allow_redirects=False, timeout=10)
    assert r.status_code == 301
    assert r.headers["Location"] == "https://localhost:443/estado-servicios/health"


def test_cada_servicio_responde_bajo_su_prefijo():
    for nombre in SERVICIOS:
        r = pide("GET", "/%s/health?format=json" % nombre)
        assert r.status_code == 200, (nombre, r.status_code, r.text[:200])
        assert r.json()["servicio"] == nombre


def test_el_prefijo_sin_barra_final_redirige():
    r = pide("GET", "/auth", allow_redirects=False)
    assert r.status_code == 301
    assert r.headers["Location"].endswith("/auth/")


def test_swagger_y_su_contrato_funcionan_bajo_el_prefijo():
    docs = pide("GET", "/escenarios/docs")
    assert docs.status_code == 200
    assert '"/escenarios/openapi.json"' in docs.text
    # El «Try it out» de Swagger llama a la URL pública, no al puerto del servicio.
    contrato = pide("GET", "/escenarios/openapi.json").json()
    assert contrato["servers"] == [{"url": "https://localhost/escenarios"}]


def test_el_directorio_da_las_urls_de_nginx():
    servicios = pide("GET", "/estado-servicios/api/v1/services?format=json").json()["servicios"]
    assert {s["nombre"]: s["url"] for s in servicios} == {
        nombre: "https://localhost/%s" % nombre for nombre in SERVICIOS}


def test_los_servicios_no_publican_su_puerto():
    for puerto in (5201, 5221, 5231, 5241, 5251, 5260, 5262):
        with socket.socket() as s:
            s.settimeout(0.5)
            assert s.connect_ex(("127.0.0.1", puerto)) != 0, puerto


def test_una_ruta_protegida_pasa_por_nginx_con_su_token(analista):
    ruta = "/escenarios/api/v1/scenarios?format=json"
    assert pide("GET", ruta).status_code == 401
    r = pide("GET", ruta, headers={"Authorization": "Bearer " + analista["access"]})
    assert r.status_code == 200, r.text[:300]


def _ips_de_nginx():
    import subprocess
    proyecto = os.environ.get("EPIDEMIA_PRUEBAS_PROYECTO", "epidemia-pruebas")
    salida = subprocess.run(["docker", "inspect", "-f",
                             "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}",
                             "%s-nginx-1" % proyecto], capture_output=True, text=True, check=True)
    return set(salida.stdout.split())


def test_el_limite_cuenta_la_ip_real_y_no_se_puede_falsear(entorno):
    """El servicio ve la IP del cliente, no la de nginx (si no, el límite por IP sería uno
    para todos), y nginx sobrescribe X-Forwarded-For: los 15 intentos cuentan para la misma IP
    real y el límite del login (10 cada 60 s, D31) responde 429."""
    import redis
    codigos = [pide("POST", "/auth/api/v1/auth/login?format=json",
                    json={"username": "nadie", "password": "x", "captcha_id": "x", "captcha": "x"},
                    headers={"X-Forwarded-For": "203.0.113.%d" % i}).status_code
               for i in range(15)]
    assert 429 in codigos, codigos

    r = redis.Redis(host="127.0.0.1", port=int(entorno["REDIS_PUERTO_LOCAL"]),
                    password=entorno["REDIS_PASSWORD"], decode_responses=True)
    patron = re.compile(r"^ratelimit:ip-(.+):POST:/api/v1/auth/login$")
    ips = {m.group(1) for m in map(patron.match, r.scan_iter("ratelimit:ip-*")) if m}
    assert len(ips) == 1, ips
    assert not ips & _ips_de_nginx(), (ips, _ips_de_nginx())
    assert not any(ip.startswith("203.0.113.") for ip in ips), ips


def test_nginx_corta_una_peticion_colgada(compose):
    """Con un servicio congelado, nginx responde 504 al cumplirse su tiempo máximo, que en las
    pruebas es de 8 s (NGINX_TIEMPO_MAXIMO)."""
    compose("pause", "zonas")
    try:
        inicio = time.monotonic()
        r = pide("GET", "/zonas/health?format=json", timeout=30)
        transcurrido = time.monotonic() - inicio
    finally:
        compose("unpause", "zonas")
    assert r.status_code == 504
    assert 7 <= transcurrido < 15, transcurrido
