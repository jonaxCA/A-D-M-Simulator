import re

RE_CODIGO = re.compile(r"^[A-Z][A-Z0-9_]{2,29}$")


def valida_enfermedad(code, name):
    # code VARCHAR(30) único y name VARCHAR(120) (004).
    errores = []
    if not code:
        errores.append("El código es obligatorio.")
    elif not RE_CODIGO.match(code):
        errores.append("El código debe empezar con letra y llevar entre 3 y 30 "
                       "caracteres (solo A-Z, 0-9 y guion bajo).")
    if not name:
        errores.append("El nombre es obligatorio.")
    elif len(name) > 120:
        errores.append("El nombre no puede pasar de 120 caracteres.")
    return errores
