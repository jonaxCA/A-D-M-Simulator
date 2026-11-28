# El simulador de abm-gpu (D23): el mismo servicio que Dockerfile, más FLAME GPU 2 y las
# piezas de CUDA que usa para compilar las funciones de agente. No trae el CUDA Toolkit ni el
# driver: el driver lo pone el host con NVIDIA Container Toolkit (en el compose, `gpus`), y lo
# demás llega por pip (procesamiento/abm_gpu/requerimientos.txt).
FROM epidemia/base-simulacion
USER root
COPY procesamiento/abm_gpu/requerimientos.txt /tmp/requerimientos/abm_gpu.txt
RUN pip install --no-cache-dir -r /tmp/requerimientos/abm_gpu.txt \
    && mkdir -p /var/cache/flamegpu && chown epidemia /var/cache/flamegpu

# Las bibliotecas de CUDA de pip se cargan al importar pyflamegpu, así que van en la ruta del
# enlazador desde que arranca el proceso. FLAME GPU guarda ahí lo que compila: con el volumen
# del compose, un contenedor nuevo no vuelve a compilar los tamaños de población que ya vio.
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cu13/lib:/usr/local/lib/python3.12/site-packages/nvidia/cu13/lib/x86_64 \
    FLAMEGPU_TMP_DIR=/var/cache/flamegpu \
    FLAMEGPU_SHARE_USAGE_STATISTICS=False \
    SIMULADOR_MOTOR=abm-gpu

COPY microservicios/simulador/ /app/microservicios/simulador/
COPY docs/contratos/simulador/ /app/docs/contratos/simulador/
USER epidemia
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health?format=json',timeout=3)" || exit 1
CMD ["python", "-m", "microservicios.simulador"]
