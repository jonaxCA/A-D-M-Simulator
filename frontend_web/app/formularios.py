"""Lectura de la peticion web: campos que solo existen por como funciona la
pagina (el control de concurrencia, la semilla en blanco, la lista de casillas).

La conversion de texto a numero o fecha que tambien necesitaria otra entrada
(una API, la app de escritorio) vive en backend_web/conversion.py.
"""
import random

# Semilla aleatoria por defecto cuando el formulario de "Ejecutar simulacion"
# la deja en blanco. simulation_runs.seed es BIGINT >= 0 (ck_simulation_runs_seed);
# 2**31-1 alcanza de sobra y coincide con lo que numpy acepta sin rodeos.
SEED_MAX = 2**31 - 1


def esperado(form, nombre):
    """Lee uno de los campos ocultos con el valor que el formulario traia al
    abrirse, para el control de concurrencia.

    Devuelve (valor, valido). Hay que distinguir tres casos, porque colapsarlos
    en "None = invalido" dejaria sin editar a todo municipio con la columna en
    NULL: el formulario se rechazaria siempre y el mensaje pediria recargar, lo
    que no arregla nada.

      - campo ausente o con basura -> (None, False): el POST no viene de
        nuestro formulario, o llego incompleto.
      - campo presente y vacio     -> (None, True): la columna estaba en NULL,
        que es un estado legitimo.
      - campo con un entero        -> (int, True).
    """
    if nombre not in form:
        return None, False
    crudo = form[nombre].strip()
    if crudo == "":
        return None, True
    try:
        return int(crudo), True
    except ValueError:
        return None, False


def semilla(valor):
    """Semilla opcional del formulario: vacio => aleatoria; con valor => debe
    ser un entero >= 0 (ck_simulation_runs_seed). Devuelve (seed, error)."""
    crudo = (valor or "").strip()
    if not crudo:
        return random.randint(0, SEED_MAX), None
    try:
        seed = int(crudo)
    except ValueError:
        return None, "La semilla debe ser un número entero."
    if seed < 0:
        return None, "La semilla debe ser un número entero mayor o igual a 0."
    return seed, None


def ids_de(valores):
    """Los enteros de una lista de texto (las casillas marcadas), sin repetir y
    en el orden en que llegaron. Lo que no es un entero se ignora."""
    ids = []
    for valor in valores:
        try:
            n = int(valor)
        except (TypeError, ValueError):
            continue
        if n not in ids:
            ids.append(n)
    return ids
