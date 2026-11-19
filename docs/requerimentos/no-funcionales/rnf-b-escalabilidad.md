> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RNF-B: Escalabilidad

Qué tan lejos llega el sistema con un solo `docker-compose` en una máquina, que es el despliegue decidido ([`arquitectura_v3.md`](../../arquitectura/arquitectura_v3.md), §8). Cómo leer la tabla: [`README.md`](../README.md).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Componente | Estado |
|---|---|---|---|---|
| RNF-B01 | Los servicios no guardan estado en su contenedor | Lo que un servicio necesita recordar va a PostgreSQL, Redis, MongoDB o el bucket | Microservicios | En parte: `evidencias` guarda los archivos en un volumen propio hasta que exista el bucket (D-3) |
| RNF-B02 | Las corridas se reparten por motor | Cada simulador consume solo la cola de su motor, y un simulador cuyo motor no corre en esa máquina no arranca | Microservicios | Hecho |
| RNF-B04 | Los límites del sistema están escritos | 100 réplicas por versión (D8), 100 casos por lote de sincronización, 50 corridas por llamada a `comparacion` y `pareto`, y 5 millones de habitantes por escenario en el XSD. El tamaño máximo de un archivo está por definir | Microservicios | En parte: falta el tamaño máximo de archivo (D30) |
| RNF-B05 | Cuando algo falla, lo que no depende de eso sigue | La web sigue aunque los servicios estén caídos (D20). Sin Redis, las rutas públicas y la analítica siguen contra PostgreSQL | Web, Microservicios | Hecho |
| RNF-B09 | La máquina con GPU se enciende solo cuando hay corridas de `abm-gpu` | Sin GPU encendida, `abm-ref` sigue atendiendo y ningún otro componente se entera | Infraestructura | Falta (N1) |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RNF-B03 | Partición de tablas por fecha o región | El volumen de D29 no lo pide |
| RNF-B06 | Resultados que se agregan sin reescribir | Se cubre con un documento por día en `series_corridas` (RNF-K03) |
| RNF-B07 | Índices para 10 millones de casos | Los índices que se miden son los de D29 (RNF-K14) |
| RNF-B08 | Cola con prioridades y reparto entre usuarios | La cola atiende en orden de llegada (ver RF-E08) |
| RNF-B10 | Redis con réplicas y particiones | Redis no guarda nada que no se pueda reconstruir (D19); una sola instancia basta |
