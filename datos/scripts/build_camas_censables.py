# Las camas censables de Nuevo León por municipio: el denominador de la capacidad hospitalaria
# utilizada del tablero (D57, RF-G07).
#
#   python datos/scripts/build_camas_censables.py agrega <Recursos_Salud_Sectorial_2025.zip>
#       Suma, del cierre anual de Recursos en Salud Sectorial de la DGIS, las camas del área de
#       hospitalización (las censables) de los establecimientos de Nuevo León por municipio y
#       escribe datos/capacidad/camas_censables_nl.csv, con la fuente, el corte y la huella del
#       zip en su encabezado. El zip no entra al repositorio.
#
# Los municipios son los 51 de datos/geo/nl_municipios.geojson; los que no tienen camas quedan en
# cero. Una clave de municipio que no sea de esos 51 detiene el script.
import csv
import hashlib
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CSV = RAIZ / "datos" / "capacidad" / "camas_censables_nl.csv"
GEO = RAIZ / "datos" / "geo" / "nl_municipios.geojson"

URL = ("http://www.dgis.salud.gob.mx/descargas/datosabiertos/recursosSalud/"
       "Recursos_Salud_Sectorial_2025.zip")
PAGINA = "http://www.dgis.salud.gob.mx/contenidos/basesdedatos/da_recursos_gobmx.html"
FUENTE = ("Secretaría de Salud, Dirección General de Información en Salud (DGIS). Recursos en Salud "
          "Sectorial, cierre anual 2025")
LICENCIA = "Datos abiertos, Decreto DOF del 20-02-2015, art. 5, fr. III: libre uso, citando la fuente"
CORTE = "2025-12-31"
PUBLICADO = "2026-09-23"
ALCANCE = ("Sector público: Secretaría de Salud, IMSS, ISSSTE, Servicios de Salud IMSS-Bienestar, "
           "DIF, servicios estatales, municipales y universitarios, y los demás que reporta la DGIS. "
           "No incluye hospitales privados.")
ENTIDAD = "19"
COLUMNA_CAMAS = "TOTAL CAMAS AREA HOSPITALIZACIÓN"
CAMPOS = ("region_code", "municipio", "establecimientos", "con_camas", "camas_censables")


def municipios():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    return {f["properties"]["region_code"]: f["properties"]["name"] for f in geo["features"]}


def suma(filas, nombres):
    """{region_code: [establecimientos, con camas, camas censables]} de las filas de Nuevo León."""
    por = defaultdict(lambda: [0, 0, 0])
    for fila in filas:
        if fila["Clave Estado"].strip() != ENTIDAD:
            continue
        codigo = ENTIDAD + fila["Clave Municipio"].strip().zfill(3)
        if codigo not in nombres:
            raise SystemExit("La clave de municipio %s no es de Nuevo León." % codigo)
        camas = int(float(fila[COLUMNA_CAMAS] or 0))
        por[codigo][0] += 1
        por[codigo][1] += 1 if camas else 0
        por[codigo][2] += camas
    return por


def agrega(ruta_zip):
    huella = hashlib.sha256(Path(ruta_zip).read_bytes()).hexdigest()
    with zipfile.ZipFile(ruta_zip) as z:
        nombre = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        texto = z.read(nombre).decode("latin-1")
    nombres = municipios()
    por = suma(csv.DictReader(io.StringIO(texto, newline="")), nombres)
    total = sum(v[2] for v in por.values())
    encabezado = [
        "Camas censables (área de hospitalización) de los establecimientos del sector público de "
        "Nuevo León, por municipio.",
        "",
        "fuente: " + FUENTE,
        "url: " + URL,
        "pagina: " + PAGINA,
        "archivo: " + nombre,
        "licencia: " + LICENCIA,
        "corte: " + CORTE,
        "publicado: " + PUBLICADO,
        "sha256: " + huella,
        "consultado: 2026-11-23",
        "filtro: Clave Estado = 19; camas censables = «%s» (el descriptor de la DGIS las llama "
        "censables)" % COLUMNA_CAMAS,
        "alcance: " + ALCANCE,
        "total: %d" % total,
        "",
        "Lo genera datos/scripts/build_camas_censables.py: no se edita a mano.",
    ]
    salida = io.StringIO()
    for linea in encabezado:
        salida.write(("# " + linea).rstrip() + "\n")
    escritor = csv.writer(salida, lineterminator="\n")
    escritor.writerow(CAMPOS)
    for codigo in sorted(nombres):
        establecimientos, con_camas, camas = por.get(codigo, (0, 0, 0))
        escritor.writerow((codigo, nombres[codigo], establecimientos, con_camas, camas))
    CSV.parent.mkdir(parents=True, exist_ok=True)
    CSV.write_text(salida.getvalue(), encoding="utf-8", newline="\n")
    print("%s: %d camas censables en %d municipios" % (CSV.name, total,
                                                       sum(1 for v in por.values() if v[2])))


def main():
    if sys.argv[1:2] == ["agrega"] and len(sys.argv) == 3:
        agrega(sys.argv[2])
    else:
        raise SystemExit(__doc__ or "Uso: build_camas_censables.py agrega <zip>")


if __name__ == "__main__":
    main()
