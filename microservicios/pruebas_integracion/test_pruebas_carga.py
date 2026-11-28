"""La forma de escalones y el resumen de las pruebas de carga (F4), con datos inventados: sin
Locust ni contenedores."""
import csv
import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _modulo(nombre):
    sys.path.insert(0, str(RAIZ / "pruebas_carga"))
    try:
        espec = importlib.util.spec_from_file_location(nombre, RAIZ / "pruebas_carga" / (nombre + ".py"))
        modulo = importlib.util.module_from_spec(espec)
        espec.loader.exec_module(modulo)
        return modulo
    finally:
        sys.path.pop(0)


AJUSTES = {"USUARIOS_PASO": "10", "SEGUNDOS_PASO": "60", "USUARIOS_MAX": "30",
           "SEGUNDOS_RECUPERACION": "60"}


def test_los_escalones_suben_bajan_y_terminan():
    escalones = _modulo("escalones")
    a = escalones.ajustes(AJUSTES)
    assert [escalones.usuarios_en(t, a) for t in (0, 59, 60, 179)] == [10, 10, 20, 30]
    # Después de subir, la recuperación con USUARIOS_BASE (por omisión, un escalón), y fin.
    assert escalones.usuarios_en(180, a) == 10 and escalones.usuarios_en(239, a) == 10
    assert escalones.usuarios_en(240, a) is None


def _escribe(carpeta, filas, t0=1000.0):
    with open(carpeta / "usuarios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t", "total", "ConsultaWeb"])
        for s in range(240):
            w.writerow([t0 + s, 0, 4 if s < 60 else 8 if s < 120 else 12 if s < 180 else 4])
    with open(carpeta / "cronologia.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t", "tipo", "nombre", "estado", "ms", "bytes", "excepcion"])
        w.writerows(filas)


def test_el_resumen_encuentra_la_saturacion_y_la_recuperacion(tmp_path):
    t0, filas = 1000.0, []
    for s in range(240):
        escalon = min(s // 60, 3)
        # 10, 20 y 30 peticiones por segundo; el tercer escalón tiene 10 % de errores y la
        # recuperación (desde el segundo 180) vuelve a 100 ms sin errores.
        n = (10, 20, 30, 10)[escalon]
        for i in range(n):
            error = 1 if escalon == 2 and i < 3 else 0
            filas.append([t0 + s + i / n, "GET", "web: GET /dashboard", 500 if error else 200,
                          100 if escalon != 2 else 900, 0, error])
        filas.append([t0 + s, "CASOS", "movil: casos guardados", 0, 0, 5, 0])
    _escribe(tmp_path, filas, t0)
    texto = _modulo("analiza").analiza(str(tmp_path), AJUSTES)
    assert "**Saturación:** a los 30 usuarios (errores ≥ 1 %)" in texto
    assert "El último escalón sano fue el de 20 usuarios" in texto
    assert "**Recuperación:** al bajar a 10 usuarios, el p95 volvió a su nivel inicial en 10 s" in texto
    assert "| web | " in texto and "| RNF-A07 el tablero carga | ≤ 3 s |" in texto
    # 5 casos guardados por segundo; la web tuvo 8 personas sin errores (el escalón de 20).
    assert "hasta 5.0 casos/s" in texto and "hasta 8 en la web sin errores" in texto
    assert (tmp_path / "resumen.md").read_text(encoding="utf-8") == texto
