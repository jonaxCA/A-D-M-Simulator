from frontend_desktop.app import resumen


def esc(nombre, minimo, maximo):
    return {
        "nombre": nombre,
        "impacto": {"p5": minimo, "p95": maximo},
    }


def test_bandas_solapadas():
    avisos = resumen.avisos_bandas([
        esc("Escenario A", 10, 20),
        esc("Escenario B", 15, 25),
    ])
    assert len(avisos) == 1
    assert "se enciman" in avisos[0]


def test_bandas_separadas():
    assert resumen.avisos_bandas([
        esc("A", 10, 20),
        esc("B", 21, 30),
    ]) == []


def test_bandas_que_se_tocan():
    assert len(resumen.avisos_bandas([
        esc("A", 10, 20),
        esc("B", 20, 30),
    ])) == 1


def test_sin_intervalo_no_hay_aviso():
    assert resumen.avisos_bandas([
        {"nombre": "A", "impacto": None},
        esc("B", 10, 20),
    ]) == []
