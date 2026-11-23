import json
from datetime import date
from pathlib import Path

import pytest

from epidemia_comun.errores import ErrorAPI
from microservicios.importacion import lectura

EJEMPLOS = Path(__file__).resolve().parents[3] / "docs/contratos/importacion/ejemplos"
SEMANAS = [("2020-03-01", 7), ("2020-03-08", 38), ("2020-03-15", 40), ("2020-03-22", 18)]
META = {"code": "COVID19_NL_2020_SINTOMAS", "name": "Serie", "disease": "SARS_COV_2_ANCESTRAL",
        "region": "19", "metric": "casos_confirmados", "period": "semana", "source": "DGE",
        "license": "Datos abiertos", "url": "https://example.org/serie.zip", "cutoff": "2021-10-31"}
HOY = date(2026, 11, 22)


def csv_de(puntos, cabecera="periodo_inicio,valor"):
    return ("# comentario\n" + cabecera + "\n" + "".join("%s,%s\n" % p for p in puntos)).encode()


def revisa(datos, tipo="text/csv", periodo="semana"):
    filas, fallas = lectura.lee(datos, tipo)
    assert fallas == []
    return lectura.revisa(filas, periodo)


@pytest.mark.parametrize("archivo,tipo", [("entrada_serie.csv", "text/csv"),
                                          ("entrada_serie.json", "application/json"),
                                          ("entrada_serie.xml", "application/xml")])
def test_los_tres_formatos_dan_la_misma_serie(archivo, tipo):
    puntos, fallas, resumen = revisa((EJEMPLOS / archivo).read_bytes(), tipo)
    assert fallas == []
    assert puntos == [(date.fromisoformat(d), v) for d, v in SEMANAS]
    assert resumen == {"puntos": 4, "inicio": date(2020, 3, 1), "fin": date(2020, 3, 22), "total": 103,
                       "maximo": 40, "periodos_en_cero": 0}


def test_el_orden_del_archivo_no_importa():
    puntos, fallas, _ = revisa(csv_de(reversed(SEMANAS)))
    assert fallas == [] and puntos[0] == (date(2020, 3, 1), 7)


@pytest.mark.parametrize("datos,tipo", [
    (csv_de(SEMANAS, "periodo_inicio,valor,edad"), "text/csv"),
    (json.dumps({"puntos": [{"periodo_inicio": "2020-03-01", "valor": 7, "sexo": "M"}]}).encode(), "application/json"),
])
def test_una_columna_de_mas_es_un_registro_y_se_rechaza(datos, tipo):
    assert lectura.lee(datos, tipo) == ([], [lectura.SOLO_AGREGADOS])


def test_el_xml_se_revisa_contra_su_xsd():
    xml = (b"<serie_observada><puntos><punto><periodo_inicio>2020-03-01</periodo_inicio>"
           b"<valor>7</valor><edad>40</edad></punto></puntos></serie_observada>")
    filas, fallas = lectura.lee(xml, "application/xml")
    assert filas == [] and len(fallas) == 1 and "edad" in fallas[0]


@pytest.mark.parametrize("datos,tipo", [(b"<roto", "application/xml"), (b"{roto", "application/json"),
                                        (b"\xff\xfe", "text/csv")])
def test_un_archivo_que_no_se_lee_es_400(datos, tipo):
    with pytest.raises(ErrorAPI) as error:
        lectura.lee(datos, tipo)
    assert error.value.estado == 400


def test_cada_punto_malo_dice_donde_esta():
    malos = [("2020-03-01", 7), ("2020-3-8", 38), ("2020-03-15", -4), ("2020-03-22", "x"), ("2020-03-01", 9)]
    _, fallas, resumen = revisa(csv_de(malos))
    assert resumen is None
    assert fallas == ["Línea 4: periodo_inicio debe ser una fecha AAAA-MM-DD.",
                      "Línea 5: valor debe ser un entero no negativo.",
                      "Línea 6: valor debe ser un entero no negativo.",
                      "Línea 7: el periodo 2020-03-01 está repetido."]


def test_un_hueco_se_reporta_y_pide_el_cero():
    _, fallas, _ = revisa(csv_de(SEMANAS[:2] + SEMANAS[3:] + [("2020-03-29", 3), ("2020-04-05", 1)]))
    assert fallas == ["Faltan 1 periodos entre 2020-03-08 y 2020-03-22: un periodo sin casos se escribe con 0."]


def test_las_semanas_empiezan_el_mismo_dia():
    _, fallas, _ = revisa(csv_de(SEMANAS[:3] + [("2020-03-23", 18)]))
    assert len(fallas) == 1 and fallas[0].startswith("El periodo 2020-03-23 no está a 7 días")


def test_una_serie_diaria():
    dias = [("2020-03-0%d" % d, d) for d in range(1, 6)]
    puntos, fallas, resumen = revisa(csv_de(dias), periodo="dia")
    assert fallas == [] and resumen["puntos"] == 5


def test_de_4_a_5000_puntos():
    _, fallas, _ = revisa(csv_de(SEMANAS[:3]))
    assert fallas == ["La serie debe tener de 4 a 5000 puntos; trae 3."]


def test_los_metadatos_completos_pasan():
    meta, fallas = lectura.revisa_metadatos(META, HOY)
    assert fallas == [] and meta["cutoff"] == date(2021, 10, 31)


def test_los_metadatos_que_faltan_o_estan_mal():
    malos = dict(META, code="covid", source="", license=" ", url="ftp://x", metric="muertes",
                 period="mes", cutoff="2027-01-01")
    _, fallas = lectura.revisa_metadatos(malos, HOY)
    assert fallas == ["Falta source.", "Falta license.",
                      "code va en mayúsculas, dígitos y guion bajo (3 a 60).",
                      "url debe empezar con http:// o https://.",
                      "metric debe ser casos_confirmados, hospitalizaciones, defunciones.",
                      "period debe ser semana o dia.", "cutoff no puede ser una fecha futura."]
