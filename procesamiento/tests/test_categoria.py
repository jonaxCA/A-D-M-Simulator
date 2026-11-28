import re
from pathlib import Path

from procesamiento import categoria as cat

RAIZ = Path(__file__).resolve().parents[1]


def test_toda_version_de_motor_tiene_su_estado():
    # Se lee del código para no importar abm_gpu (necesita pyflamegpu).
    for archivo in ("motor/modelo.py", "abm/modelo.py", "abm_gpu/modelo.py"):
        version = re.search(r'^ENGINE_VERSION = "([^"]+)"', (RAIZ / archivo).read_text(encoding="utf-8"),
                            re.M).group(1)
        assert version in cat.ESTADO, archivo


def test_hoy_todo_es_exploratorio_y_verificado():
    r = cat.categoria("seir-ref-0.1", [{"parametro": "r0", "estado": "supuesto"}], "COVID", "19")
    assert r["categoria"] == "exploratoria" and r["modelo_verificado"]
    assert cat.categoria("desconocida-9")["modelo_verificado"] is False


def test_las_tres_categorias(monkeypatch):
    nl = {"enfermedad": "COVID", "region": "19"}
    monkeypatch.setitem(cat.ESTADO, "x-1", {"verificado": True, "calibrado": [nl], "validado": []})
    con_fuente = [{"parametro": "r0", "estado": "con_fuente"}]
    assert cat.categoria("x-1", con_fuente, "COVID", "19")["categoria"] == "prediccion"
    assert cat.categoria("x-1", [{"parametro": "r0", "estado": "supuesto"}], "COVID", "19")["categoria"] == "exploratoria"
    assert cat.categoria("x-1", con_fuente, "COVID", "20")["categoria"] == "exploratoria"
    monkeypatch.setitem(cat.ESTADO, "x-1", {"verificado": True, "calibrado": [nl], "validado": [nl]})
    assert cat.categoria("x-1", con_fuente, "COVID", "19")["categoria"] == "validada"
