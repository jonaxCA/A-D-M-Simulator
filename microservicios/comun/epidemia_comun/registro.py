import logging

FORMATO = "%(asctime)s %(servicio)s %(levelname)s %(correlation_id)s %(message)s"


class _Contexto(logging.Filter):
    def __init__(self, servicio):
        super().__init__()
        self.servicio = servicio

    def filter(self, record):
        from flask import g, has_request_context
        record.servicio = self.servicio
        record.correlation_id = (getattr(g, "correlation_id", None) if has_request_context() else None) or "-"
        return True


def configurar(servicio):
    raiz = logging.getLogger()
    for h in raiz.handlers:
        if getattr(h, "_epidemia", False):
            raiz.removeHandler(h)
    h = logging.StreamHandler()
    h._epidemia = True
    h.setFormatter(logging.Formatter(FORMATO, "%Y-%m-%dT%H:%M:%S%z"))
    h.addFilter(_Contexto(servicio))
    raiz.addHandler(h)
    raiz.setLevel(logging.INFO)
