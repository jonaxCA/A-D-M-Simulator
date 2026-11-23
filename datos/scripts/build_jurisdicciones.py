"""
Genera datos/geo/nl_jurisdicciones_sanitarias.json: a qué jurisdicción sanitaria pertenece cada
municipio de Nuevo León, para la agrupación territorial de `zonas` (F7).

Fuente: Reglamento Interior de "Servicios de Salud de Nuevo León" Organismo Público
Descentralizado, artículo 27 (Periódico Oficial del Estado núm. 130, 12 de octubre de 2004;
última reforma P.O. 4 de marzo de 2009), en la Compilación Legislativa del Estado publicada por
la Normateca federal:
http://www.ordenjuridico.gob.mx/Documentos/Estatal/Nuevo%20Leon/wo119338.pdf (consultado el
2026-11-21). TRANSCRIPCION copia la lista de cada jurisdicción tal como la escribe el
reglamento; ALIAS traduce los nombres que no son los del catálogo INEGI.

Pendiente: confirmar con la Secretaría de Salud de Nuevo León que la división siga vigente; los
diagnósticos de 2025 también hablan de 8 jurisdicciones (4 urbanas y 4 rurales).

Monterrey se reparte entre las jurisdicciones 1 (poniente), 2 (norte y oriente) y 3 (sur). Con
casos por municipio no se puede partir, así que queda en `compartidos`.

Cada corrida valida y falla en vez de escribir un archivo con huecos: cada nombre corresponde a
un municipio del catálogo, y los 51 aparecen una sola vez (en una jurisdicción o compartidos).

    python datos/scripts/build_jurisdicciones.py
"""
import json
import os
import sys

DATOS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOGO = os.path.join(DATOS, "geo", "nl_catalogo_oficial.json")
SALIDA = os.path.join(DATOS, "geo", "nl_jurisdicciones_sanitarias.json")
ESTADO = "19"

FUENTE = {
    "documento": "Reglamento Interior de \"Servicios de Salud de Nuevo León\" Organismo Público "
                 "Descentralizado, artículo 27",
    "publicacion": "Periódico Oficial del Estado núm. 130, 12 de octubre de 2004; última reforma "
                   "P.O. 4 de marzo de 2009",
    "url": "http://www.ordenjuridico.gob.mx/Documentos/Estatal/Nuevo%20Leon/wo119338.pdf",
    "consultado": "2026-11-21",
    "nota": "Pendiente de confirmar con la Secretaría de Salud de Nuevo León que siga vigente. "
            "Monterrey se reparte entre las jurisdicciones 1, 2 y 3; con casos por municipio no "
            "se puede partir y va en compartidos.",
}

# (número, circunscripción, municipios completos como los escribe el reglamento)
TRANSCRIPCION = [
    (1, "Poniente del municipio de Monterrey", []),
    (2, "Norte y oriente del municipio de Monterrey y los municipios de Abasolo, el Carmen, "
        "Ciénega de Flores, General Mariano Escobedo, General Zuazua, Mina, Salinas Victoria, "
        "San Nicolás de los Garza e Hidalgo",
     ["Abasolo", "el Carmen", "Ciénega de Flores", "General Mariano Escobedo", "General Zuazua",
      "Mina", "Salinas Victoria", "San Nicolás de los Garza", "Hidalgo"]),
    (3, "Sur de Monterrey y los municipios de Villa de García, San Pedro Garza García y "
        "Santa Catarina",
     ["Villa de García", "San Pedro Garza García", "Santa Catarina"]),
    (4, "Municipios de Apodaca, Guadalupe y Benito Juárez",
     ["Apodaca", "Guadalupe", "Benito Juárez"]),
    (5, "Municipios de Agualeguas, Anáhuac, Bustamante, General Treviño, Lampazos, Parás, "
        "Sabinas Hidalgo, Vallecillo y Villaldama",
     ["Agualeguas", "Anáhuac", "Bustamante", "General Treviño", "Lampazos", "Parás",
      "Sabinas Hidalgo", "Vallecillo", "Villaldama"]),
    (6, "Municipios de Los Aldama, Cadereyta Jiménez, Cerralvo, China, Dr. Coss, Dr. González, "
        "General Bravo, Los Herrera, Higueras, Marín, Melchor Ocampo, Pesquería y Los Ramones",
     ["Los Aldama", "Cadereyta Jiménez", "Cerralvo", "China", "Dr. Coss", "Dr. González",
      "General Bravo", "Los Herrera", "Higueras", "Marín", "Melchor Ocampo", "Pesquería",
      "Los Ramones"]),
    (7, "Municipios de Allende, General Terán, Hualahuises, Linares, Montemorelos, Los Rayones "
        "y Santiago",
     ["Allende", "General Terán", "Hualahuises", "Linares", "Montemorelos", "Los Rayones",
      "Santiago"]),
    (8, "Municipios de Aramberri, Dr. Arroyo, Galeana, General Zaragoza, Mier y Noriega e "
        "Iturbide",
     ["Aramberri", "Dr. Arroyo", "Galeana", "General Zaragoza", "Mier y Noriega", "Iturbide"]),
]
COMPARTIDOS = {"Monterrey": [1, 2, 3]}

# Nombre del reglamento -> nombre del catálogo INEGI (nl_catalogo_oficial.json).
ALIAS = {
    "el Carmen": "El Carmen",
    "General Mariano Escobedo": "General Escobedo",
    "Villa de García": "García",
    "Benito Juárez": "Juárez",
    "Lampazos": "Lampazos de Naranjo",
    "Los Aldama": "Los Aldamas",
    "Dr. Coss": "Doctor Coss",
    "Dr. González": "Doctor González",
    "Los Herrera": "Los Herreras",
    "Los Rayones": "Rayones",
    "Dr. Arroyo": "Doctor Arroyo",
}


def construir(catalogo):
    por_nombre = {nombre: ESTADO + clave for clave, nombre in catalogo.items()}

    def clave(nombre):
        oficial = ALIAS.get(nombre, nombre)
        if oficial not in por_nombre:
            raise ValueError("%r no está en el catálogo INEGI" % nombre)
        return por_nombre[oficial]

    jurisdicciones = [{"numero": n, "nombre": "Jurisdicción Sanitaria No. %d" % n,
                       "circunscripcion": texto, "municipios": [clave(m) for m in municipios]}
                      for n, texto, municipios in TRANSCRIPCION]
    compartidos = {clave(m): numeros for m, numeros in COMPARTIDOS.items()}
    vistos = [c for j in jurisdicciones for c in j["municipios"]] + list(compartidos)
    repetidos = sorted({c for c in vistos if vistos.count(c) > 1})
    faltan = sorted(set(por_nombre.values()) - set(vistos))
    if repetidos or faltan or len(vistos) != len(catalogo):
        raise ValueError("Repetidos: %s; faltan: %s" % (repetidos, faltan))
    return {"fuente": FUENTE, "jurisdicciones": jurisdicciones, "compartidos": compartidos}


def texto(datos):
    return json.dumps(datos, ensure_ascii=False, indent=2) + "\n"


def main():
    with open(CATALOGO, encoding="utf-8") as archivo:
        datos = construir(json.load(archivo))
    with open(SALIDA, "w", encoding="utf-8", newline="\n") as archivo:
        archivo.write(texto(datos))
    print("Escrito %s: %d jurisdicciones, %d municipios"
          % (os.path.relpath(SALIDA), len(datos["jurisdicciones"]),
             sum(len(j["municipios"]) for j in datos["jurisdicciones"]) + len(datos["compartidos"])))


if __name__ == "__main__":
    sys.exit(main())
