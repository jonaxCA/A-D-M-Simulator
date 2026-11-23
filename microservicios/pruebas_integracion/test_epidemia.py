"""`epidemia.py up` levanta los perfiles de dominio del compose, ni uno más (sin `gpu` ni `web`)."""
import importlib.util
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
espec = importlib.util.spec_from_file_location("epidemia", RAIZ / "epidemia.py")
SCRIPT = importlib.util.module_from_spec(espec)
espec.loader.exec_module(SCRIPT)


def test_los_perfiles_son_los_de_dominio_del_compose():
    texto = (RAIZ / "infra/docker-compose.yml").read_text(encoding="utf-8")
    perfiles = set(re.findall(r"^    profiles: \[(\w+)\]", texto, re.M))
    assert set(SCRIPT.PERFILES) == perfiles - {"gpu", "web"}


def test_up_no_arrastra_gpu_y_down_si_baja_todo(monkeypatch):
    llamadas = []
    monkeypatch.setattr(SCRIPT, "correr", lambda cmd: llamadas.append(cmd) or 0)
    SCRIPT.compose("up")
    SCRIPT.compose("down", todos=True)
    assert "*" not in llamadas[0] and "gpu" not in llamadas[0]
    assert llamadas[1][-3:] == ["--profile", "*", "down"]
