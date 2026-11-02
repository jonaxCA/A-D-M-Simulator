# D23 - Tecnología del ABM: CPU o GPU

Fecha: — · Estado: Pendiente

## Contexto
El motor no importa Flask ni toca la base: recibe y regresa diccionarios (regla 2). `decisiones/todo.md` propone FLAME GPU con el motor de Python como respaldo.

## Opciones consideradas
- Opción A: Python con NumPy o Numba en CPU.
- Opción B: FLAME GPU 2 en GPU, con el motor de Python como respaldo.

Pregunta abierta para B: si hay GPU disponible en GCP y quién la paga.

## Decisión
Pendiente. Se registra aquí cuando se tome.

## Consecuencias
Define la imagen del contenedor de `simulador`, el tipo de máquina en Compute Engine y el costo. Depende de D22 y de la respuesta del profesor sobre créditos de GCP.

Depende de: D22
