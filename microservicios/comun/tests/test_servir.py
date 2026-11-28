"""epidemia_comun.servir: waitress confía en nginx solo con DETRAS_DE_PROXY=1 (D25, D31)."""
import re
from pathlib import Path

from epidemia_comun import servir

RAIZ = Path(__file__).resolve().parents[3]


def test_sin_proxy_no_confia_en_cabeceras(monkeypatch):
    monkeypatch.delenv("DETRAS_DE_PROXY", raising=False)
    assert servir.opciones() == {"listen": "0.0.0.0:8000"}


def test_detras_de_nginx_confia_en_un_solo_proxy(monkeypatch):
    monkeypatch.setenv("DETRAS_DE_PROXY", "1")
    opciones = servir.opciones("127.0.0.1:5262")
    assert opciones["listen"] == "127.0.0.1:5262"
    assert opciones["trusted_proxy_count"] == 1
    assert opciones["trusted_proxy_headers"] == {"x-forwarded-for", "x-forwarded-host",
                                                 "x-forwarded-proto"}


def test_las_opciones_son_validas_para_waitress(monkeypatch):
    from waitress.adjustments import Adjustments
    monkeypatch.setenv("DETRAS_DE_PROXY", "1")
    ajustes = Adjustments(**servir.opciones())
    assert ajustes.trusted_proxy == "*" and ajustes.clear_untrusted_proxy_headers


def test_cada_servicio_arranca_con_el_arrancador_comun():
    """Con waitress-serve directo, detrás de nginx el servicio perdería la IP del cliente."""
    for dockerfile in sorted(RAIZ.glob("microservicios/*/Dockerfile")):
        cmd = [l for l in dockerfile.read_text(encoding="utf-8").splitlines() if l.startswith("CMD")]
        assert cmd, dockerfile
        propio = re.fullmatch(r'CMD \["python", "-m", "microservicios\.[a-z_]+"\]', cmd[0])
        comun = re.fullmatch(r'CMD \["python", "-m", "epidemia_comun\.servir", '
                             r'"microservicios\.%s\.app:app"\]' % dockerfile.parent.name, cmd[0])
        assert propio or comun, (dockerfile, cmd[0])
    for principal in ("estado_servicios", "simulador"):
        texto = (RAIZ / "microservicios" / principal / "__main__.py").read_text(encoding="utf-8")
        assert "from epidemia_comun.servir import" in texto and "waitress" not in texto
