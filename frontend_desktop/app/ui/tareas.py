from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

_vivas = set()
manejador_errores = None


class _Senales(QObject):
    listo = Signal(object)
    fallo = Signal(object)
    avance = Signal(int, str)


class _Tarea(QRunnable):
    def __init__(self, fn, args, kwargs, senales):
        super().__init__()
        self.fn, self.args, self.kwargs, self.senales = fn, args, kwargs, senales

    def run(self):
        try:
            resultado = self.fn(*self.args, **self.kwargs)
        except Exception as exc:
            self.senales.fallo.emit(exc)
        else:
            self.senales.listo.emit(resultado)


def en_hilo(fn, *args, listo=None, fallo=None, avance=None):
    senales = _Senales()
    _vivas.add(senales)
    kwargs = {}
    if avance:
        senales.avance.connect(avance)
        kwargs["avance"] = senales.avance.emit
    if listo:
        senales.listo.connect(listo)
    senales.fallo.connect(fallo or manejador_errores or (lambda exc: None))
    senales.listo.connect(lambda *_: _vivas.discard(senales))
    senales.fallo.connect(lambda *_: _vivas.discard(senales))
    QThreadPool.globalInstance().start(_Tarea(fn, args, kwargs, senales))
