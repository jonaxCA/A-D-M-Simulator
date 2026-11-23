import os
from functools import wraps

from flask import current_app, request

from . import redis_compartido
from .errores import ErrorAPI
from .llaves import limite

# Supuestos de ingeniería (D31 no da cifras): peticiones / segundos, por usuario y ruta.
# Se ajustan con LIMITE_<PERFIL>="peticiones/segundos" tras las pruebas de carga.
PERFILES = {"normal": (120, 60), "permisivo": (600, 60), "estricto": (10, 60), "publico": (10, 60)}
PERFIL_POR_SERVICIO = {"casos": "permisivo", "sincronizacion": "permisivo"}
ESCRITURAS = ("POST", "PUT", "PATCH", "DELETE")
# Lanzar corridas o calibraciones ocupa al simulador: el límite estricto (D31, D50).
SOLO_ESCRITURAS_ESTRICTAS = ("corridas", "calibracion")


def perfil_de(servicio, metodo):
    if servicio in SOLO_ESCRITURAS_ESTRICTAS:
        return "estricto" if metodo in ESCRITURAS else "normal"
    return PERFIL_POR_SERVICIO.get(servicio, "normal")


def cifras(perfil):
    valor = os.environ.get("LIMITE_" + perfil.upper())
    if valor:
        try:
            maximo, ventana = valor.split("/")
            return int(maximo), int(ventana)
        except ValueError:
            pass
    return PERFILES[perfil]


def consumir(usuario=None, perfil=None, cantidad=1, ruta=None):
    # Ventana fija. Con Redis caído no se limita: la sesión ya habría dado 503 y,
    # en las rutas públicas, el límite es una mejora, no un control de acceso.
    # `cantidad` y `ruta` son para una petición que vale por varias: un lote de casos descuenta
    # un caso por cada caso, de la misma cuenta que POST /cases (F4).
    quien = "ip-" + str(request.remote_addr) if usuario is None else str(usuario)
    ruta = ruta or "%s:%s" % (request.method, request.url_rule.rule if request.url_rule else request.path)
    perfil = perfil or perfil_de(current_app.config.get("NOMBRE_SERVICIO"), request.method)
    maximo, ventana = cifras(perfil)
    llave = limite(quien, ruta)

    def contar(r):
        p = r.pipeline()
        p.set(llave, 0, nx=True, ex=ventana)
        p.incrby(llave, cantidad)
        p.ttl(llave)
        return p.execute()

    resultado = redis_compartido.opcional("limite de consumo", contar)
    if resultado is None:
        return
    cuenta, restante = resultado[1], resultado[2]
    if cuenta > maximo:
        espera = restante if restante and restante > 0 else ventana
        raise ErrorAPI(429, "LIMITE_EXCEDIDO",
                       "Demasiadas peticiones; intenta de nuevo en %d segundos." % espera,
                       {"Retry-After": str(espera)})


def limitar(perfil="publico"):
    def decorador(funcion):
        @wraps(funcion)
        def ejecutar(*args, **kwargs):
            consumir(perfil=perfil)
            return funcion(*args, **kwargs)
        return ejecutar
    return decorador
