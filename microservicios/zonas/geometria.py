"""Geometría oficial de los municipios de Nuevo León y ubicar un punto en ella (F7).

La geometría sale de datos/geo/nl_municipios.geojson, que genera
datos/scripts/build_municipios_inegi.py desde la capa municipal del Marco Geoestadístico 2024 de
INEGI: reproyectada a lon/lat y simplificada a 0.0012 grados (unos 130 m). Es la misma que dibuja
el mapa de la web.

- GET /zones/geometry la sirve tal cual (GeoJSON), con su ETag: un cliente la descarga una vez.
- GET /zones/locate dice en qué municipio cae un punto. Sin PostGIS: cada municipio guarda su
  recuadro (bbox), que descarta casi todos antes de la prueba de punto en polígono (rayo, con
  huecos). Como la geometría está simplificada, entre dos fronteras quedan rendijas de algunos
  metros: un punto que cae ahí se asigna al municipio más cercano dentro de TOLERANCIA y sale
  como `aproximado`.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from epidemia_comun.bd import query

ARCHIVO = Path(__file__).resolve().parents[2] / "datos/geo/nl_municipios.geojson"
# Un poco más que la simplificación (0.0012 grados): lo que puede separar un punto de su municipio.
TOLERANCIA = 0.0015
PRECISION_METROS = 130


@lru_cache(maxsize=1)
def crudo():
    return ARCHIVO.read_bytes()


@lru_cache(maxsize=1)
def etag():
    return '"%s"' % hashlib.sha256(crudo()).hexdigest()[:32]


@lru_cache(maxsize=1)
def _datos():
    return json.loads(crudo().decode("utf-8"))


def fuente():
    return _datos()["fuente"]


def ids_de_municipios():
    """Clave INEGI -> regions.id de los municipios de Nuevo León."""
    return {f["code"]: f["id"] for f in query(
        "SELECT id, code FROM regions WHERE parent_region_id = "
        "(SELECT id FROM regions WHERE code = %s)", ("19",))}


@lru_cache(maxsize=1)
def _indice():
    """[(bbox, polígonos, propiedades)]; cada polígono es [exterior, huecos...] en lon/lat."""
    indice = []
    for f in _datos()["features"]:
        g = f["geometry"]
        poligonos = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        xs = [p[0] for poligono in poligonos for p in poligono[0]]
        ys = [p[1] for poligono in poligonos for p in poligono[0]]
        indice.append(((min(xs), min(ys), max(xs), max(ys)), poligonos, f["properties"]))
    return indice


def _en_anillo(x, y, anillo):
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def _en_poligono(x, y, poligono):
    return _en_anillo(x, y, poligono[0]) and not any(_en_anillo(x, y, h) for h in poligono[1:])


def _al_segmento(x, y, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    largo = dx * dx + dy * dy
    t = 0.0 if largo == 0 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / largo))
    px, py = a[0] + t * dx, a[1] + t * dy
    return ((x - px) ** 2 + (y - py) ** 2) ** 0.5


def _al_borde(x, y, poligonos):
    return min(_al_segmento(x, y, anillo[i - 1], anillo[i])
               for poligono in poligonos for anillo in poligono for i in range(1, len(anillo)))


def localiza(lat, lon):
    """(propiedades del municipio, aproximado) o (None, False) si el punto está fuera de NL."""
    cercanos = []
    for (x0, y0, x1, y1), poligonos, propiedades in _indice():
        if x0 <= lon <= x1 and y0 <= lat <= y1 and any(_en_poligono(lon, lat, p) for p in poligonos):
            return propiedades, False
        if x0 - TOLERANCIA <= lon <= x1 + TOLERANCIA and y0 - TOLERANCIA <= lat <= y1 + TOLERANCIA:
            cercanos.append((poligonos, propiedades))
    distancias = [(_al_borde(lon, lat, poligonos), propiedades) for poligonos, propiedades in cercanos]
    distancias = [d for d in distancias if d[0] <= TOLERANCIA]
    if distancias:
        return min(distancias, key=lambda d: d[0])[1], True
    return None, False
