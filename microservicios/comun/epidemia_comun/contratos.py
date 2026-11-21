def proyectar(fila, campos):
    return {campo: fila.get(campo) for campo in campos}
