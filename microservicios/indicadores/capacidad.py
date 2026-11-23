"""Las camas censables de Nuevo León (D57): el denominador de la capacidad hospitalaria utilizada.

Salen de datos/capacidad/camas_censables_nl.csv (DGIS, Recursos en Salud Sectorial), que la
imagen copia y que genera datos/scripts/build_camas_censables.py; su encabezado trae la fuente,
el corte y la huella del archivo de la DGIS. Si el archivo no está, la capacidad sale sin valor.
"""
import csv
import functools
import io
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parents[2] / "datos" / "capacidad" / "camas_censables_nl.csv"
# Del encabezado, lo que el indicador muestra como su fuente.
CAMPOS_FUENTE = {"fuente": "documento", "url": "url", "licencia": "licencia", "corte": "corte",
                 "alcance": "alcance", "sha256": "sha256"}


def lee(texto):
    """(total de camas censables, fuente) de un archivo con el formato de camas_censables_nl.csv."""
    fuente, filas = {}, []
    for linea in texto.splitlines():
        if linea.startswith("#"):
            clave, _, valor = linea[1:].strip().partition(": ")
            if clave in CAMPOS_FUENTE and valor:
                fuente[CAMPOS_FUENTE[clave]] = valor
        elif linea.strip():
            filas.append(linea)
    total = sum(int(f["camas_censables"]) for f in csv.DictReader(io.StringIO("\n".join(filas))))
    return total, {campo: fuente.get(campo) for campo in CAMPOS_FUENTE.values()}


@functools.lru_cache(maxsize=1)
def camas_censables():
    """(total, fuente) de Nuevo León, o (None, None) si la imagen no trae el archivo."""
    if not ARCHIVO.exists():
        return None, None
    return lee(ARCHIVO.read_text(encoding="utf-8"))
