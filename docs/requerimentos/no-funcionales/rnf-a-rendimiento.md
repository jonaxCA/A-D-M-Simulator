> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RNF-A: Rendimiento

Las metas de tiempo de respuesta son las que el equipo fijó desde el primer parcial; ninguna está medida todavía, así que se confirman o se ajustan con las pruebas de Locust (A4, A5). Los tiempos del simulador sí están medidos, en [`ficha_simulador.md`](../../arquitectura/ficha_simulador.md) (§12). Cómo leer la tabla: [`README.md`](../README.md).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Componente | Estado |
|---|---|---|---|---|
| RNF-A01 | Las rutas de consulta de los servicios responden rápido | Meta: p95 de 500 ms o menos, por confirmar con Locust | Microservicios | Falta medir (A4) |
| RNF-A02 | El tiempo de una corrida de cada motor se mide y se reporta | `python -m procesamiento.mediciones` repite la tabla de segundos y memoria pico. Referencia medida para Nuevo León completo: 7.7 s por corrida en `abm-gpu` y de 80 a 90 s en `abm-ref` | Microservicios | Hecho |
| RNF-A04 | El tiempo de un lote de 30 réplicas se conoce antes de lanzarlo en la demostración | Referencia medida para Nuevo León completo: unos 4 minutos en `abm-gpu` y unos 45 en `abm-ref` | Microservicios | Hecho |
| RNF-A05 | `sincronizacion` y `casos` aguantan a muchos teléfonos enviando a la vez | Meta: 100 casos por segundo, por confirmar con Locust (perfil de la móvil) | Microservicios | Falta medir (A4) |
| RNF-A06 | La web aguanta a varias personas consultando a la vez | Meta: 50 usuarios concurrentes sin errores, por confirmar con Locust (perfil de consulta) | Web | Falta medir (A4) |
| RNF-A07 | El tablero carga rápido | Meta: 3 s o menos, por confirmar con Locust | Web | Falta medir (A4) |
| RNF-A08 | Un lote de 100 casos se sincroniza sin que el capturista espere de más | Meta: 30 s o menos, por confirmar con Locust | Móvil, Microservicios | Falta medir (A4) |
| RNF-A09 | Los resultados de una corrida se consultan rápido, con y sin la caché de Redis | Meta: 2 s o menos. Se mide con y sin caché (D29) | Microservicios | Hecho: la serie de una corrida, 4.8 ms sin caché y 1.1 ms con ella, con 10 000 corridas en la colección; medido con las funciones de `resultados`, sin el HTTP del servicio ([`docs/pruebas/volumen/2026-11-18`](../../pruebas/volumen/2026-11-18/LEEME.md)) |
| RNF-A13 | Cada motor tiene su simulador, así que una corrida lenta de un motor no detiene a las de otro | Hay una cola por motor (`queue:simulaciones:<motor>`) y cada simulador toma solo la suya | Microservicios | Hecho |
| RNF-A14 | Lanzar un lote responde de inmediato | `POST /api/v1/runs` responde 202 sin esperar la corrida. Meta: 1 s o menos, por confirmar con Locust | Microservicios | Hecho; falta medir (A4) |
| RNF-A16 | Hay pruebas de carga con Locust, con un perfil por uso real | Perfiles: consulta de la web, la móvil sincronizando y subiendo fotos, el escritorio comparando, administradores en el panel y procesos automáticos. Se reportan usuarios concurrentes, peticiones por segundo, tiempo medio, p95, p99, errores, saturación, recuperación y los endpoints más lentos | Infraestructura | Falta (A4, A5) |
| RNF-A17 | El sistema se mide con un conjunto de datos de alto volumen (D29) | Unas 10 000 corridas de 180 días, alrededor de 1.8 millones de documentos en `series_corridas`. Se miden el tiempo de inserción, las consultas con y sin índice y con y sin Redis, y el uso de CPU, memoria y disco. La cifra se confirma con el profesor | Bases de datos | Hecho (D-6) el 2026-11-18 con `datos/scripts/volumen_mongo.py` ([`docs/pruebas/volumen/2026-11-18`](../../pruebas/volumen/2026-11-18/LEEME.md)); la cifra sigue por confirmar |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RNF-A03 | 100 000 agentes en menos de 15 minutos en el motor de referencia | Lo sustituyen las mediciones de RNF-A02 |
| RNF-A10 | Exportar series completas en menos de 10 s | La exportación es local, en el escritorio |
| RNF-A11 | Mapa en menos de 5 s | Se cubre con RNF-A07 |
| RNF-A12 | Búsquedas en catálogos en menos de 300 ms | Se cubre con RNF-A01 |
| RNF-A15 | Curvas en caché en menos de 200 ms | Se cubre con RNF-A09 |
