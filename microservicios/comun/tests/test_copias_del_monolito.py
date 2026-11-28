"""Las copias que los servicios de F guardan de reglas que la web todavía lee de backend_web (E8).

La regla es del servicio (docs/arquitectura/duenos_de_reglas.md); la copia del monolito se va
cuando la web consuma el servicio (D36). Mientras existan las dos deben ser iguales: si una
cambia, se cambia la otra en el mismo commit, o se quita de esta lista cuando la web ya no la use.
"""
import inspect
from pathlib import Path

import pytest

from backend_web import queries
from microservicios.casos import captura
from microservicios.dispositivos import almacen as dispositivos
from microservicios.indicadores import consultas as indicadores
from microservicios.series import consultas as series
from microservicios.vacunas import lotes
from microservicios.zonas import consultas as zonas

RAIZ = Path(__file__).resolve().parents[3]

COPIAS = [
    (indicadores, queries, ("NL_ESTADO_CODE", "_pct_change", "_clasifica_tendencia",
                            "get_resumen_indicadores", "get_resumen_situacion")),
    (series, queries, ("NL_ESTADO_CODE", "_pct_change", "get_enfermedad", "GRUPOS_EDAD",
                       "_GRUPO_EDAD_SQL", "_monitoreo_where", "_poblacion_ambito", "get_monitoreo_serie",
                       "get_monitoreo_edad", "get_monitoreo_sexo", "get_monitoreo_totales", "SEXOS",
                       "get_region_municipio")),
    (zonas, queries, ("NL_ESTADO_CODE", "_pct_change", "_clasifica_tendencia", "get_enfermedad",
                      "BUCKETS", "_bucket", "get_mapa_municipios", "get_tendencia_zona",
                      "get_mapa_serie_temporal", "ORDEN_ZONAS", "get_monitoreo_zonas",
                      "get_region_municipio")),
    (captura, queries, ("NL_ESTADO_CODE", "SEXOS", "RESULTADOS", "SEVERIDADES",
                        "get_enfermedades_para_captura", "valida_caso", "get_municipios_catalogo")),
    # La lectura de devices que hace casos: la regla es de dispositivos.
    (captura, dispositivos, ("estado_para_captura",)),
    (lotes, queries, ("ZONA_HORARIA",)),
]


def _parejas():
    for copia, original, nombres in COPIAS:
        for nombre in nombres:
            yield pytest.param(copia, original, nombre,
                               id="%s.%s" % (copia.__name__.replace("microservicios.", ""), nombre))


@pytest.mark.parametrize("copia,original,nombre", list(_parejas()))
def test_la_copia_es_igual_a_la_original(copia, original, nombre):
    de_la_copia, del_original = getattr(copia, nombre), getattr(original, nombre)
    if inspect.isfunction(del_original):
        assert inspect.getsource(de_la_copia) == inspect.getsource(del_original)
    else:
        assert de_la_copia == del_original


def test_la_conversion_de_casos_es_la_del_monolito():
    assert ((RAIZ / "microservicios/casos/conversion.py").read_bytes()
            == (RAIZ / "backend_web/conversion.py").read_bytes())


def test_la_conversion_de_la_biblioteca_es_la_del_monolito():
    # Leer números del texto de un formulario es técnico: la usan intervenciones y validacion (E8).
    assert ((RAIZ / "microservicios/comun/epidemia_comun/conversion.py").read_bytes()
            == (RAIZ / "backend_web/conversion.py").read_bytes())
