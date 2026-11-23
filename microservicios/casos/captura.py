"""Lo que necesita la captura de un caso: los catálogos, la validación de sus campos y si el
dispositivo puede capturar.

Copia de las de backend_web.queries: la web todavía las usa (D36) y la regla es de este
servicio (E8, docs/arquitectura/duenos_de_reglas.md). Mientras las dos existan deben ser
iguales: microservicios/comun/tests/test_copias_del_monolito.py lo revisa.

estado_para_captura es una lectura de `devices`, cuyo dueño es `dispositivos`
(microservicios/dispositivos/almacen.py); la misma prueba revisa que sea igual a la de allá.
"""
from datetime import date

from epidemia_comun.bd import query

from . import conversion

NL_ESTADO_CODE = "19"


SEXOS = {"M": "Masculino", "F": "Femenino", "O": "Otro"}

RESULTADOS = {"positivo": "Positivo", "negativo": "Negativo",
              "pendiente": "Pendiente", "sin_prueba": "Sin prueba"}

SEVERIDADES = {"asintomatico": "Asintomático", "leve": "Leve",
               "grave": "Grave", "fallecido": "Fallecido"}


def get_enfermedades_para_captura():
    """Catalogo de enfermedades para el selector del reporte.

    NO se reutiliza get_enfermedades_catalogo(): esa hace JOIN contra `cases`
    y por lo tanto solo devuelve enfermedades que YA tienen casos. Para
    capturar serviria de poco -- una enfermedad recien dada de alta nunca
    podria recibir su primer reporte. Aqui van todas las del catalogo que
    esten vigentes (is_active), tengan casos o no.
    """
    return query(
        """
        SELECT id, name, code FROM diseases
        WHERE is_active
        ORDER BY name
        """
    )


def valida_caso(form, enfermedades, municipios):
    """Valida el formulario contra los CHECK reales de `cases`.

    Devuelve (datos_limpios, errores). Los dominios cerrados (sexo, resultado,
    severidad) se comparan contra los diccionarios de arriba: lo que no este
    ahi se descarta, no se manda a la base.

    `enfermedades` y `municipios` son los catalogos que ofrece el formulario
    (get_enfermedades_para_captura y get_municipios_catalogo). Un id que no
    este ahi se rechaza aqui y no al insertar: una enfermedad inactiva o el
    estado pasarian la llave foranea, y un id que no cabe en la columna
    (diseases.id es smallint) hacia que el INSERT respondiera 500.
    """
    errores = []
    datos = {
        "disease_id": conversion.entero(
            form.get("disease_id"), errores, etiqueta="La enfermedad", minimo=1,
            maximo=2**31, miles=False),
        "region_id": conversion.entero(
            form.get("region_id"), errores, etiqueta="El municipio", minimo=1,
            maximo=2**31, miles=False),
        "report_date": conversion.fecha(
            form.get("report_date"), errores, etiqueta="La fecha de reporte"),
        "onset_date": conversion.fecha(
            form.get("onset_date"), errores, etiqueta="La fecha de inicio de síntomas",
            obligatorio=False),
        "age": conversion.entero(
            form.get("age"), errores, etiqueta="La edad", minimo=0, maximo=120,
            obligatorio=False, miles=False),
        "latitude": conversion.decimal(
            form.get("latitude"), errores, etiqueta="La latitud", minimo=-90, maximo=90),
        "longitude": conversion.decimal(
            form.get("longitude"), errores, etiqueta="La longitud", minimo=-180, maximo=180),
    }
    if datos["disease_id"] is not None and \
            datos["disease_id"] not in {e["id"] for e in enfermedades}:
        errores.append("Esa enfermedad no está activa en el catálogo.")
    if datos["region_id"] is not None and \
            datos["region_id"] not in {m["id"] for m in municipios}:
        errores.append("Ese municipio no está en el catálogo de Nuevo León.")

    for campo, dominio, etiqueta in (
        ("sex", SEXOS, "El sexo"),
        ("test_result", RESULTADOS, "El resultado de prueba"),
        ("severity", SEVERIDADES, "La severidad"),
    ):
        valor = (form.get(campo) or "").strip()
        if valor and valor not in dominio:
            errores.append(f"{etiqueta} no es un valor del catálogo.")
            valor = ""
        datos[campo] = valor or None

    # ck_cases_rezago: no se puede reportar un caso antes de que empiecen los
    # sintomas.
    if datos["onset_date"] and datos["report_date"] and datos["onset_date"] > datos["report_date"]:
        errores.append("El inicio de síntomas no puede ser posterior a la fecha de reporte.")

    # Esto no lo pide el esquema, pero un reporte con fecha futura no tiene
    # sentido y descuadraria las ventanas de 7/30/60 dias de las otras
    # pantallas, que cuentan hacia atras desde current_date.
    if datos["report_date"] and datos["report_date"] > date.today():
        errores.append("La fecha de reporte no puede estar en el futuro.")

    # ck_cases_coordenadas: la geolocalizacion viaja completa o no viaja.
    if (datos["latitude"] is None) != (datos["longitude"] is None):
        errores.append("La ubicación necesita latitud y longitud, o ninguna de las dos.")

    return datos, errores


def get_municipios_catalogo():
    """Municipios de Nuevo Leon para el selector geografico. Trae los 51, no
    solo los 10 con casos: filtrar por uno vacio es un resultado valido."""
    return query(
        """
        SELECT id, name FROM regions
        WHERE parent_region_id = (SELECT id FROM regions WHERE code = %s)
        ORDER BY name
        """,
        (NL_ESTADO_CODE,),
    )


def estado_para_captura(device_id, user_id):
    """Si casos puede aceptar un caso de ese dispositivo para esa persona: "ok",
    "ajeno" (no existe o es de otra cuenta) o "revocado"."""
    fila = query("SELECT user_id, is_revoked FROM devices WHERE id = %s", (device_id,), one=True)
    if fila is None or fila["user_id"] != user_id:
        return "ajeno"
    return "revocado" if fila["is_revoked"] else "ok"
