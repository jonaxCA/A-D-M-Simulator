"""Carga pyflamegpu sin telemetría y con las piezas de CUDA que necesita para compilar.

FLAME GPU compila las funciones de agente con NVRTC al armar el modelo, así que además de la
GPU necesita NVRTC, nvJitLink y los encabezados de CUDA, cuRAND y CCCL. Se buscan en este orden:

1. Un CUDA Toolkit instalado (CUDA_PATH o CUDA_HOME), como en la imagen del contenedor.
2. Los paquetes de NVIDIA de pip (nvidia-cuda-nvrtc, nvidia-nvjitlink, nvidia-cuda-runtime,
   nvidia-curand y nvidia-cuda-cccl), que dejan todo en site-packages/nvidia/cu13. Sirve para
   probar en una PC sin instalar el Toolkit; ver procesamiento/abm_gpu/README.md.

FLAME GPU manda por omisión estadísticas de uso anónimas a un servicio externo (TelemetryDeck).
Aquí se apagan siempre, antes de importar pyflamegpu.
"""
import os
import pathlib
import sys

_CARGADO = None
_ERROR = None


class SinFlameGPU(RuntimeError):
    """No hay pyflamegpu, o no encuentra CUDA. El mensaje dice qué falta."""


def _cuda_de_pip():
    try:
        import nvidia
    except ImportError:
        return None
    for base in getattr(nvidia, "__path__", []):
        raiz = pathlib.Path(base) / "cu13"
        if (raiz / "include" / "cuda_runtime.h").exists():
            return raiz
    return None


def _prepara_cuda():
    if os.environ.get("CUDA_PATH") or os.environ.get("CUDA_HOME"):
        return
    raiz = _cuda_de_pip()
    if raiz is None:
        return
    os.environ["CUDA_PATH"] = str(raiz)
    cccl = raiz / "include" / "cccl"
    if cccl.exists() and "FLAMEGPU_RTC_INCLUDE_DIRS" not in os.environ:
        os.environ["FLAMEGPU_RTC_INCLUDE_DIRS"] = str(cccl)
    binarios = raiz / "bin" / "x86_64" if sys.platform == "win32" else raiz / "lib"
    if binarios.exists():
        os.environ["PATH"] = str(binarios) + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(binarios))


def carga():
    """El módulo pyflamegpu, listo para usarse. Levanta SinFlameGPU si no se puede."""
    global _CARGADO, _ERROR
    if _CARGADO is not None:
        return _CARGADO
    if _ERROR is not None:
        raise SinFlameGPU(_ERROR)
    os.environ["FLAMEGPU_SHARE_USAGE_STATISTICS"] = "False"
    _prepara_cuda()
    try:
        import pyflamegpu
    except ImportError as exc:
        _ERROR = "abm-gpu necesita pyflamegpu (FLAME GPU 2) y una GPU de NVIDIA: %s" % exc
        raise SinFlameGPU(_ERROR) from exc
    pyflamegpu.Telemetry.disable()
    pyflamegpu.Telemetry.suppressNotice()
    _CARGADO = pyflamegpu
    return pyflamegpu


def disponible():
    """(True, None) si se puede importar pyflamegpu; (False, motivo) si no. No revisa la GPU:
    sin ella, la corrida falla al crear la simulación."""
    try:
        carga()
    except SinFlameGPU as exc:
        return False, str(exc)
    return True, None
