import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from microservicios.importacion import lectura

RAIZ = Path(__file__).resolve().parents[3]
SCRIPT = RAIZ / "datos/scripts/build_serie_observada.py"
MIGRACION = RAIZ / "datos/postgres/migraciones/061_serie_observada.sql"
CSV = RAIZ / "datos/observados/covid19_nl_2020_semanal.csv"


def _script():
    spec = importlib.util.spec_from_file_location("build_serie_observada", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# Como las semillas en backend_web/tests/test_archivos_sql.py: si alguien edita la 061 y no el
# script o el CSV, la siguiente regeneración borraría el cambio sin que nada fallara.
def test_la_061_sale_igual_de_su_script():
    entorno = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    salida = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, check=True, env=entorno).stdout
    assert salida == MIGRACION.read_bytes()


def test_el_csv_se_puede_importar_tal_cual():
    filas, fallas = lectura.lee(CSV.read_bytes(), "text/csv")
    puntos, fallas, resumen = lectura.revisa(filas, "semana")
    assert fallas == []
    assert all(dia.weekday() == 6 for dia, _ in puntos)  # semanas del SINAVE: de domingo a sábado


def test_la_ventana_es_la_de_la_regla_y_pasa_la_revision():
    script = _script()
    meta, semanas = script.lee_csv()
    puntos, pico = script.ventana(semanas)
    assert (str(puntos[0][0]), str(pico), str(puntos[-1][0]), len(puntos)) == ("2020-03-01", "2020-07-05", "2020-07-26", 22)
    assert meta["ventana"] == "2020-03-01 a 2020-07-26 (22 semanas)"
    filas = [("Semana %d" % i, str(d), v) for i, (d, v) in enumerate(puntos, 1)]
    _, fallas, resumen = lectura.revisa(filas, "semana")
    assert fallas == [] and resumen["total"] == 22259
    for dia, valor in puntos:
        assert "('%s', %d)" % (dia, valor) in MIGRACION.read_text(encoding="utf-8")
