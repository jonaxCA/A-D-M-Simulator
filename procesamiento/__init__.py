"""Componente de procesamiento: el motor de simulacion de referencia.

Existe como paquete para que la aplicacion web pueda importarlo desde la raiz
del repositorio (`from procesamiento.motor import validar_escenario`) sin tocar
sys.path. Las pruebas y la linea de comandos tambien se corren desde la raiz
(`python -m pytest procesamiento/tests`, `python -m procesamiento.motor`): el
motor se importa siempre como `procesamiento.motor`, nunca como `motor`.
"""
