# abm-gpu: el ABM en FLAME GPU 2

> **Estado: Vigente** · 2026-11-14 · D23. El modelo es el de `abm-ref` (`procesamiento/abm/`);
> cómo funciona por dentro está en [`docs/arquitectura/ficha_simulador.md`](../../docs/arquitectura/ficha_simulador.md).

`abm-gpu` corre en una GPU de NVIDIA el mismo modelo basado en agentes que `abm-ref`, con el
mismo contrato (`docs/contratos/motor/README.md`). Cada persona es un agente de FLAME GPU 2 con
su grupo de edad, su hogar y, según su edad, su salón o su centro de trabajo.

## Qué es igual a abm-ref y qué no

- **Igual:**
  - el escenario y su validación (`resolver`);
  - las probabilidades diarias y la fuerza de infección por hogar, salón, trabajo y comunidad;
  - el reparto de vacunas por grupo de edad;
  - la forma de la salida.
- **La misma población inicial:** NumPy arma los grupos de contacto, la escala de contactos y
  los infectados iniciales con el mismo código y la misma semilla que `abm-ref`
  (`procesamiento/abm/poblacion.py`). Llegan a la GPU en un archivo binario, de un solo jalón.
- **Otro azar:** la epidemia usa el generador de FLAME GPU (cuRAND, sembrado con la semilla). Con
  la misma semilla las dos corridas empiezan igual, pero no siguen el mismo camino. Por eso se
  comparan promedios de varias semillas, no corridas.
- **Reproducible en la misma GPU:** la misma semilla da la misma salida en la misma GPU y con la
  misma versión de FLAME GPU. Los conteos usan sumas atómicas de enteros, que no dependen del
  orden, y los agentes que se vacunan se eligen con un ordenamiento estable.
- **Precisión simple:** las probabilidades de cada agente se calculan con `float` de 32 bits.

## Un día en la GPU

| Capa | Dónde | Qué hace |
|---|---|---|
| `prepara_dia` | host | Pesos del día por capa con las intervenciones activas; pone en cero los conteos |
| `cuenta` | agentes | Infecciosos y vivos de cada hogar, salón y centro de trabajo (el día 1, antes, cada agente toma sus datos de la población) |
| `avanza` | agentes | S → E, E → I, I → H/D/R, H → D/R |
| `reparte_vacunas` | host | Dosis por grupo de edad, como en `abm-ref`; ordena a los agentes por grupo y al azar entre los que se pueden vacunar |
| `vacuna` | agentes | La campaña *c* vacuna los lugares [`corte_lo`, `corte_hi`) del bloque de su grupo |
| fin del día | host | Cuenta los estados para la fila de la serie |

Las dos capas de vacunación solo existen si el escenario tiene campañas. Las funciones de agente
están en `agentes.cu`, y FLAME GPU las compila con NVRTC al armar el modelo. Si un cambio altera
los números, sube `ENGINE_VERSION` en `modelo.py`.

La primera corrida de cada tamaño de población tarda unos 9 s más, porque el número de agentes
fija el tamaño de las propiedades macro y FLAME GPU compila esas funciones. Lo compilado queda en
caché (`FLAMEGPU_TMP_DIR`), así que las réplicas de una versión compilan una sola vez.

## Requisitos

- Una GPU de NVIDIA que soporte CUDA 13 (Turing o más nueva) y su driver. Se probó en una
  GeForce RTX 4050 Laptop (6 GB) con el driver 621.14.
- `pyflamegpu` 2.0.0rc5 compilado con CUDA 13.0. No está en PyPI: sale de las releases de
  FLAME GPU 2 en GitHub (`requerimientos.txt`).
- NVRTC, nvJitLink y los encabezados de CUDA, cuRAND y CCCL. Pueden venir de un CUDA Toolkit
  13.0 instalado (`CUDA_PATH`) o de los paquetes de NVIDIA de pip; `entorno.py` encuentra
  cualquiera de los dos.

**FLAME GPU manda por omisión estadísticas de uso anónimas a TelemetryDeck.** `entorno.py` las
apaga siempre antes de importar `pyflamegpu`, y `test_abm_gpu.py` revisa que sigan apagadas. Si
importas `pyflamegpu` por tu cuenta, pon antes `FLAMEGPU_SHARE_USAGE_STATISTICS=False`.

## Probarlo en Windows sin instalar el CUDA Toolkit

Un venv aparte, que ve el NumPy del sistema (unos 250 MB de descargas):

```bash
python -m venv --system-site-packages C:/Temp/flamegpu
```

```bash
C:/Temp/flamegpu/Scripts/python.exe -m pip install -r procesamiento/abm_gpu/requerimientos.txt
```

Desde la raíz del repositorio:

```bash
C:/Temp/flamegpu/Scripts/python.exe -m pytest procesamiento
```

Con ese Python, las pruebas de conformidad también corren `abm-gpu`. Con el Python normal se
saltan y lo reportan.

Para un chequeo rápido (corre el escenario de ejemplo, revisa el contrato y que la telemetría
esté apagada; sale con 1 si algo falla):

```bash
C:/Temp/flamegpu/Scripts/python.exe -m procesamiento.abm_gpu
```

## En el contenedor

`microservicios/simulador/gpu.Dockerfile` agrega estos requerimientos a la imagen base, y el
servicio `simulador-gpu` del compose la corre con `SIMULADOR_MOTOR=abm-gpu`. Necesita NVIDIA
Container Toolkit en el host (en Windows, Docker Desktop con WSL 2), así que va en su propio
perfil:

```bash
docker compose --profile simulacion --profile gpu up -d
```

`corridas` acepta corridas de `abm-gpu` solo si `MOTORES_HABILITADOS` lo nombra, por ejemplo
`abm-ref,abm-gpu`. Un simulador de `abm-gpu` sin `pyflamegpu` no arranca
(`motores.del_nombre`).

Construir la imagen y probarla con la GPU, sin levantar PostgreSQL ni Redis:

```bash
docker compose -f infra/docker-compose.yml --profile gpu build simulador-gpu
```

```bash
docker compose -f infra/docker-compose.yml --profile gpu run --rm --no-deps simulador-gpu python -m procesamiento.abm_gpu
```

De punta a punta (`corridas` → cola → `simulador-gpu` → `resultados`), en el compose de pruebas
y con su propia base:

```bash
python infra/pruebas_integracion.py --gpu -- -k gpu
```

Sin `--gpu`, ese compose no levanta `simulador-gpu` y la prueba se salta: así corre en una PC sin
GPU de NVIDIA.
