# D23 - Tecnología del ABM: CPU o GPU

Fecha: 2026-11-08 · Estado: Aceptada

## Contexto
El motor no importa Flask ni toca la base: recibe y regresa diccionarios (regla 2). `decisiones/todo.md` propone FLAME GPU con el motor de Python como respaldo.

## Opciones consideradas
- Opción A: Python con NumPy o Numba en CPU.
- Opción B: FLAME GPU 2 en GPU, con el motor de Python como respaldo.

La pregunta abierta para B era si hay GPU disponible en GCP y quién la paga. El equipo respondió: sí hay, con los créditos que Google dio para la clase. Cada integrante tiene 100 USD desde el inicio del semestre.

## Decisión
Opción B: el ABM corre en FLAME GPU 2, con el motor de Python como respaldo. Es la misma decisión que D2 (opción A) ya pide para los motores `abm-gpu` y `abm-ref`. Se paga con los créditos de clase.

## Consecuencias
- La imagen de `simulador` necesita soporte para CUDA, y la máquina de Compute Engine necesita GPU.
- El costo no está estimado todavía. Hay que compararlo con los créditos disponibles: según `AGENTS.md` somos seis integrantes, unos 600 USD en total.
- La implementación de CUDA y FLAME GPU queda para el tercer parcial: están fuera de alcance del segundo.
- Los cambios que siguen de esta decisión están en [`todo.md`](todo.md), sección «Cambios pendientes por D23».
- Implementado el 2026-11-14 como `abm-gpu` (`procesamiento/abm_gpu/`), con `abm-ref` como respaldo. La imagen no necesita una base de CUDA: `pyflamegpu` y las piezas de CUDA que usa para compilar llegan por pip (`microservicios/simulador/gpu.Dockerfile`), y el driver lo pone el host. Se probó de punta a punta en Docker Desktop con WSL 2. En una RTX 4050 corre un millón de agentes a 180 días en 1.2 s, contra 13.6 s de `abm-ref` (ver [`ficha_simulador.md`](../arquitectura/ficha_simulador.md)).
- FLAME GPU manda por omisión estadísticas de uso anónimas a un servicio externo. El motor las apaga siempre.

Depende de: D22
