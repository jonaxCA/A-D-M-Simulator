import hashlib

MAXIMO = 20 * 1024 * 1024


def valida_pdf(datos):
    if not datos:
        return None, ["Elige el PDF del reporte."]
    if len(datos) > MAXIMO:
        return None, ["El reporte pasa de 20 MB."]
    if not datos.startswith(b"%PDF-"):
        return None, ["El archivo no es un PDF."]
    return hashlib.sha256(datos).hexdigest(), []
