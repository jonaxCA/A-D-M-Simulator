"""
Quien hace una operacion y desde donde.

Es lo unico que la capa de datos necesita saber de la peticion HTTP: el
usuario, su IP y su navegador, para la bitacora. Viaja como parametro para que
backend_web no dependa de Flask: la misma funcion sirve desde una ruta, desde
el hilo que corre una simulacion o, mas adelante, desde un microservicio que
arme el contexto a partir del JWT y de los encabezados de la peticion.

El sitio web lo arma con frontend_web.app.permisos.contexto_de_peticion().
"""
from dataclasses import dataclass

# Lo que queda en audit_log.user_agent cuando no hay peticion detras.
AGENTE_SIN_PETICION = "hilo de simulacion (sin peticion HTTP)"


@dataclass(frozen=True)
class Contexto:
    user_id: int | None        # None: nadie inicio sesion (p. ej. un login fallido)
    ip: str | None             # None: no hubo peticion HTTP
    user_agent: str            # ya recortado a 255, el tamanio de la columna

    @classmethod
    def sin_peticion(cls, user_id):
        """Para lo que corre fuera de una peticion, como el hilo de una corrida."""
        return cls(user_id, None, AGENTE_SIN_PETICION)
