"""Las camas censables de Nuevo León (D57): el archivo del repositorio y el script que lo genera."""
import csv
import importlib.util
import io
import json
import zipfile
from pathlib import Path

from microservicios.indicadores import capacidad

RAIZ = Path(__file__).resolve().parents[3]
SCRIPT = RAIZ / "datos/scripts/build_camas_censables.py"


def _script():
    spec = importlib.util.spec_from_file_location("build_camas_censables", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _encabezado(texto):
    return dict(l[2:].partition(": ")[::2] for l in texto.splitlines() if l.startswith("# ") and ": " in l)


def test_el_archivo_trae_los_51_municipios_y_su_total_cuadra():
    texto = capacidad.ARCHIVO.read_text(encoding="utf-8")
    filas = list(csv.DictReader(io.StringIO("\n".join(l for l in texto.splitlines() if not l.startswith("#")))))
    geo = json.loads((RAIZ / "datos/geo/nl_municipios.geojson").read_text(encoding="utf-8"))
    assert {f["region_code"] for f in filas} == {f["properties"]["region_code"] for f in geo["features"]}
    encabezado = _encabezado(texto)
    assert sum(int(f["camas_censables"]) for f in filas) == int(encabezado["total"])
    assert all(int(f["con_camas"]) <= int(f["establecimientos"]) for f in filas)


def test_el_encabezado_dice_de_donde_sale():
    encabezado = _encabezado(capacidad.ARCHIVO.read_text(encoding="utf-8"))
    assert encabezado["url"].startswith("http://www.dgis.salud.gob.mx/descargas/datosabiertos/recursosSalud/")
    assert encabezado["corte"] == "2025-12-31" and len(encabezado["sha256"]) == 64
    assert "No incluye hospitales privados" in encabezado["alcance"]


def test_el_servicio_lee_el_total_y_la_fuente():
    total, fuente = capacidad.camas_censables()
    assert total == int(_encabezado(capacidad.ARCHIVO.read_text(encoding="utf-8"))["total"])
    assert set(fuente) == {"documento", "url", "licencia", "corte", "alcance", "sha256"}
    assert fuente["documento"].startswith("Secretaría de Salud, Dirección General de Información en Salud")


def test_el_script_suma_las_camas_censables_de_nuevo_leon_por_municipio(tmp_path, monkeypatch):
    script = _script()
    filas = [
        # Monterrey, dos establecimientos; uno sin camas. Otro estado no cuenta.
        {"Clave Estado": "19", "Clave Municipio": "039", "TOTAL CAMAS AREA HOSPITALIZACIÓN": "120"},
        {"Clave Estado": "19", "Clave Municipio": "39", "TOTAL CAMAS AREA HOSPITALIZACIÓN": ""},
        {"Clave Estado": "19", "Clave Municipio": "026", "TOTAL CAMAS AREA HOSPITALIZACIÓN": "30"},
        {"Clave Estado": "15", "Clave Municipio": "039", "TOTAL CAMAS AREA HOSPITALIZACIÓN": "999"},
    ]
    salida = io.StringIO()
    escritor = csv.DictWriter(salida, fieldnames=list(filas[0]))
    escritor.writeheader()
    escritor.writerows(filas)
    zip_falso = tmp_path / "Recursos.zip"
    with zipfile.ZipFile(zip_falso, "w") as z:
        z.writestr("BD ABIERTOS SECTORIAL 2025.csv", salida.getvalue().encode("latin-1"))
    monkeypatch.setattr(script, "CSV", tmp_path / "camas.csv")

    script.agrega(zip_falso)

    total, fuente = capacidad.lee((tmp_path / "camas.csv").read_text(encoding="utf-8"))
    assert total == 150 and len(fuente["sha256"]) == 64
    texto = (tmp_path / "camas.csv").read_text(encoding="utf-8")
    monterrey = next(l for l in texto.splitlines() if l.startswith("19039,"))
    assert monterrey.endswith(",2,1,120")
    assert sum(1 for l in texto.splitlines() if l.startswith("19")) == 51
