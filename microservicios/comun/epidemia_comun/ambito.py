"""Filtros de enfermedad, municipio y periodo que comparten series y zonas.

Son los mismos de la pantalla de Monitoreo y del mapa del monolito, pero aquí un
valor fuera de dominio es un 422 en vez de caer al valor por omisión, y una
enfermedad o un municipio que no existe es un 404 en vez de una serie en ceros.
"""
from .errores import ErrorAPI
from .validaciones import entero_positivo


def _opcional(args, campo):
    valor = args.get(campo)
    if valor is None or valor == "":
        return None
    return entero_positivo(valor, campo)


def filtros_ambito(args, periodos, por_omision=30, con_region=True):
    from backend_web import queries
    disease_id = _opcional(args, "disease_id")
    region_id = _opcional(args, "region_id") if con_region else None
    dias = por_omision
    if args.get("days") not in (None, ""):
        dias = entero_positivo(args.get("days"), "days")
        if dias not in periodos:
            raise ErrorAPI(422, "DATOS_INVALIDOS",
                           "days debe ser uno de: %s." % ", ".join(str(p) for p in periodos))
    if disease_id is not None and queries.get_enfermedad(disease_id) is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe la enfermedad.")
    if region_id is not None and queries.get_region_municipio(region_id) is None:
        raise ErrorAPI(404, "NO_ENCONTRADO", "No existe el municipio en Nuevo León.")
    return {"disease_id": disease_id, "region_id": region_id, "dias": dias}


def clave_ambito(filtros):
    """Parte de la llave de caché: siempre en el mismo orden."""
    return "d=%s:r=%s:dias=%s" % (filtros["disease_id"], filtros["region_id"], filtros["dias"])
