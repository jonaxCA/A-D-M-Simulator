from .errores import ErrorAPI
from .http import llamar


def permitidas(datos):
    # None es sin límite regional: una cuenta nacional o una que solo tiene alcance por institución,
    # que ningún servicio aplica todavía (D43); no se le niegan los datos regionales.
    return set(datos["regiones_cubiertas"]) if not datos["nacional"] and datos["regiones_cubiertas"] else None


def regiones_permitidas():
    # D43: el alcance es de `roles`; se pide en cada petición porque no va en el token.
    respuesta = llamar("roles", "GET", "/api/v1/scopes/me")
    if respuesta.status_code != 200:
        raise ErrorAPI(503, "SERVICIO_NO_DISPONIBLE", "No se pudo consultar el alcance de la cuenta.")
    datos = respuesta.json()
    return permitidas(datos)


def exige_region(region_id):
    permitidas = regiones_permitidas()
    if permitidas is not None and region_id not in permitidas:
        raise ErrorAPI(403, "PERMISO_INSUFICIENTE", "El dato está fuera del alcance de tu cuenta.")


def exige_region_de(obtener):
    # Para cuando conocer la región cuesta una consulta: una cuenta nacional no la hace.
    permitidas = regiones_permitidas()
    if permitidas is None:
        return
    region = obtener()
    if region is not None and region not in permitidas:
        raise ErrorAPI(403, "PERMISO_INSUFICIENTE", "El dato está fuera del alcance de tu cuenta.")
