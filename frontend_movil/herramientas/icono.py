"""Genera el ícono de EPIDEMIA: un pin de ubicación (un caso en campo) con una partícula de virus.

Una sola geometría, en el lienzo de 108 de los íconos adaptativos, da los tres vectoriales (fondo,
frente y monocromo, en drawable/) y los WebP de Android 7 (mipmap-*dpi/). Necesita Pillow.

    python herramientas/icono.py app/src/main/res [carpeta para la vista previa]
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

RES = Path(sys.argv[1])
VISTAS = Path(sys.argv[2]) if len(sys.argv) > 2 else None

FONDO = "#0B4F5C"
PIN = "#FFFFFF"
VIRUS = "#E4572E"

# El pin: cabeza de radio R centrada en C y punta abajo. Todo cabe en el círculo seguro de 66.
C = (54.0, 47.0)
R = 21.0
PUNTA = (54.0, 81.0)
# El virus, en la cabeza del pin.
NUCLEO = 7.5
ESPIGAS = 8
RADIO_PERILLA = 12.5
PERILLA = 2.6
TALLO = (7.0, 11.0, 2.0)  # de, hasta, ancho


def tangentes():
    d = PUNTA[1] - C[1]
    cos_f, sin_f = R / d, math.sqrt(1 - (R / d) ** 2)
    return (C[0] - R * sin_f, C[1] + R * cos_f), (C[0] + R * sin_f, C[1] + R * cos_f)


def f(x):
    return ("%.2f" % x).rstrip("0").rstrip(".")


def circulo(cx, cy, r):
    return "M%s,%s a%s,%s 0 1,0 %s,0 a%s,%s 0 1,0 %s,0 Z" % (f(cx - r), f(cy), f(r), f(r), f(2 * r), f(r), f(r), f(-2 * r))


def angulos():
    return [math.radians(22.5 + i * 360 / ESPIGAS) for i in range(ESPIGAS)]


def tallo(a):
    de, hasta, ancho = TALLO
    ux, uy = math.cos(a), math.sin(a)
    px, py = -uy * ancho / 2, ux * ancho / 2
    return [
        (C[0] + ux * de + px, C[1] + uy * de + py), (C[0] + ux * hasta + px, C[1] + uy * hasta + py),
        (C[0] + ux * hasta - px, C[1] + uy * hasta - py), (C[0] + ux * de - px, C[1] + uy * de - py),
    ]


def poligono(puntos):
    return "M" + " L".join("%s,%s" % (f(x), f(y)) for x, y in puntos) + " Z"


def pin_path():
    (ix, iy), (dx, dy) = tangentes()
    return "M%s,%s L%s,%s A%s,%s 0 1,1 %s,%s Z" % (f(PUNTA[0]), f(PUNTA[1]), f(ix), f(iy), f(R), f(R), f(dx), f(dy))


def perillas():
    return [(C[0] + math.cos(a) * RADIO_PERILLA, C[1] + math.sin(a) * RADIO_PERILLA) for a in angulos()]


def virus_path():
    partes = [circulo(C[0], C[1], NUCLEO)]
    partes += [poligono(tallo(a)) for a in angulos()]
    partes += [circulo(x, y, PERILLA) for x, y in perillas()]
    return " ".join(partes)


def vector(comentario, cuerpo):
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!-- %s Lo genera herramientas/icono.py. -->\n'
            '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
            '    android:width="108dp"\n    android:height="108dp"\n'
            '    android:viewportWidth="108"\n    android:viewportHeight="108">\n%s</vector>\n') % (comentario, cuerpo)


def escribir_vectores():
    dibujo = RES / "drawable"
    (dibujo / "ic_launcher_background.xml").write_text(vector(
        "Fondo del ícono: verde azulado.",
        '    <path\n        android:fillColor="%s"\n        android:pathData="M0,0h108v108h-108z" />\n' % FONDO,
    ), encoding="utf-8", newline="\n")
    (dibujo / "ic_launcher_foreground.xml").write_text(vector(
        "Frente del ícono: el pin de un caso en campo con una partícula de virus.",
        '    <path\n        android:fillColor="%s"\n        android:pathData="%s" />\n'
        '    <path\n        android:fillColor="%s"\n        android:pathData="%s" />\n' % (PIN, pin_path(), VIRUS, virus_path()),
    ), encoding="utf-8", newline="\n")
    # Para los íconos temáticos (Android 13): un solo color, con el virus calado en el pin. Sin los
    # tallos, que se encimarían con el núcleo y las perillas.
    calado = " ".join([pin_path(), circulo(C[0], C[1], NUCLEO)] + [circulo(x, y, PERILLA) for x, y in perillas()])
    (dibujo / "ic_launcher_monochrome.xml").write_text(vector(
        "Ícono temático (Android 13): el pin con el virus calado.",
        '    <path\n        android:fillColor="#FF000000"\n        android:fillType="evenOdd"\n        android:pathData="%s" />\n' % calado,
    ), encoding="utf-8", newline="\n")


def dibujar(lado, escala, desplazamiento, sobre=None, monocromo=None, hueco=(0, 0, 0, 0)):
    """El frente en una imagen RGBA de `lado`; una unidad del lienzo = `escala` píxeles."""
    img = sobre or Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def p(x, y):
        return (desplazamiento[0] + x * escala, desplazamiento[1] + y * escala)

    def disco(cx, cy, r, color):
        x, y = p(cx, cy)
        d.ellipse([x - r * escala, y - r * escala, x + r * escala, y + r * escala], fill=color)

    (ix, iy), (dx, dy) = tangentes()
    color_pin = monocromo or PIN
    disco(C[0], C[1], R, color_pin)
    d.polygon([p(*PUNTA), p(ix, iy), p(dx, dy)], fill=color_pin)
    color_virus = hueco if monocromo else VIRUS
    disco(C[0], C[1], NUCLEO, color_virus)
    if not monocromo:
        for a in angulos():
            d.polygon([p(*q) for q in tallo(a)], fill=color_virus)
    for x, y in perillas():
        disco(x, y, PERILLA, color_virus)
    return img


def legado(lado, redondo):
    # Como los de la plantilla: la forma ocupa 44 de 48, y lo visible del lienzo adaptativo (72 de
    # 108) cabe en ella.
    grande = lado * 8
    img = Image.new("RGBA", (grande, grande), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margen = grande * 2 / 48
    caja = [margen, margen, grande - margen, grande - margen]
    if redondo:
        d.ellipse(caja, fill=FONDO)
    else:
        d.rounded_rectangle(caja, radius=grande * 8 / 48, fill=FONDO)
    escala = (grande - 2 * margen) / 72
    centro = grande / 2
    dibujar(grande, escala, (centro - 54 * escala, centro - 54 * escala), sobre=img)
    return img.resize((lado, lado), Image.LANCZOS)


def escribir_legado():
    for carpeta, lado in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
        for nombre, redondo in (("ic_launcher", False), ("ic_launcher_round", True)):
            legado(lado, redondo).save(RES / ("mipmap-" + carpeta) / (nombre + ".webp"), "WEBP", lossless=True)


def vista_previa():
    """Cómo se ve con las máscaras de los launchers, en monocromo y en chico."""
    lado = 432
    escala = lado / 108
    adaptativo = Image.new("RGBA", (lado, lado), FONDO)
    dibujar(lado, escala, (0, 0), sobre=adaptativo)
    lienzo = Image.new("RGB", (lado * 4 + 150, lado + 40), "#F2F2F2")
    visible = 72 * escala
    corte = (lado - visible) / 2
    for i, forma in enumerate(("circulo", "squircle", "monocromo")):
        mascara = Image.new("L", (lado, lado), 0)
        md = ImageDraw.Draw(mascara)
        caja = [corte, corte, lado - corte, lado - corte]
        if forma == "squircle":
            md.rounded_rectangle(caja, radius=visible * 0.3, fill=255)
        else:
            md.ellipse(caja, fill=255)
        if forma == "monocromo":
            tema = Image.new("RGBA", (lado, lado), "#DCE5F0")
            dibujar(lado, escala, (0, 0), sobre=tema, monocromo="#3A4A63", hueco="#DCE5F0")
            fuente = tema
        else:
            fuente = adaptativo
        lienzo.paste(fuente.convert("RGB"), (20 + i * (lado + 30), 20), mascara)
    for j, chico in enumerate((48, 72, 96)):
        icono = legado(chico, redondo=True)
        lienzo.paste(icono, (20 + 3 * (lado + 30), 40 + j * 130), icono)
    lienzo.save(VISTAS / "icono_vista.png")


escribir_vectores()
escribir_legado()
if VISTAS:
    vista_previa()
print("listo")
