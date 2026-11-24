> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RNF-L: Restricciones de implementación

Lo que la materia o las decisiones del equipo ya fijaron. La lista de la materia está en [`tecnologia_requerida.txt`](../../rubrica/tecnologia_requerida.txt). Cómo leer la tabla: [`README.md`](../README.md).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Componente | Estado |
|---|---|---|---|---|
| RNF-L01 | El código de Python corre en Python 3.12 (D60) | Ruff con `target-version = "py312"` y CI en 3.12 y 3.13 | Microservicios, Web, Escritorio | Hecho |
| RNF-L02 | La web y los microservicios son de Flask | La web es un monolito; cada microservicio es una app pequeña | Web, Microservicios | Hecho |
| RNF-L04 | La app Android es de Kotlin | Usa Room para lo local y WorkManager para sincronizar | Móvil | Hecho |
| RNF-L05 | La app de escritorio es de Python con PySide6 | — | Escritorio | Hecho |
| RNF-L06 | La base relacional es PostgreSQL | — | Bases de datos | Hecho |
| RNF-L07 | La base no relacional es MongoDB | Ver RNF-K03 | Bases de datos | Hecho (D-1) |
| RNF-L08 | Redis lleva las sesiones, la caché, los candados y las colas | — | Bases de datos | Hecho |
| RNF-L09 | La nube es Google Cloud | Compute Engine y Cloud Storage | Infraestructura | Falta (N1, D-3) |
| RNF-L10 | Todo corre en contenedores de Docker | — | Infraestructura | Hecho |
| RNF-L11 | La entrada es nginx | Ver RNF-H16 | Infraestructura | Falta (S6) |
| RNF-L12 | Las gráficas de la web son de Highcharts | Ver RF-G02 | Web | Hecho |
| RNF-L13 | La API se documenta con OpenAPI | Ver RNF-F03 | Microservicios | Hecho |
| RNF-L14 | Las pruebas de carga son con Locust | Ver RNF-A16 | Infraestructura | Falta (A4) |
| RNF-L16 | El modelo de agentes en GPU usa FLAME GPU 2 (D23) | `abm-gpu` corre en el contenedor `simulador-gpu`, con las piezas de CUDA | Microservicios | Hecho |
| RNF-L17 | Los motores de referencia son de Python | `seir-ref` es el control experimental y `abm-ref` el modelo de agentes en CPU (D2, D22). El motor no importa Flask ni toca la base | Microservicios | Hecho |
| RNF-L19 | La app Android usa al menos dos capacidades del teléfono | Usa seis: cámara, GPS, lector de QR y de código de barras, notificaciones, almacenamiento local y sincronización | Móvil | Hecho |
| RNF-L20 | El modelo de agentes simula a Nuevo León completo | 5 784 442 habitantes, un agente por habitante, medido en `abm-gpu` | Microservicios | Hecho |
| RNF-L21 | El alcance geográfico es Nuevo León y sus 51 municipios | — | Bases de datos | Hecho |
| RNF-L27 | La población sale del Censo 2020 | El factor de escala es habitantes del censo entre agentes simulados (D6) | Bases de datos | Hecho |
| RNF-L28 | `seir-ref` se calibra contra una ola real (D50, reabierto) | Con la serie pública agregada de la 061 (COVID-19 en Nuevo León, 2020), nunca con registros por persona ni con `cases` (063). El método, la pérdida, las métricas y la tolerancia de validación están en la §19 de la ficha | Microservicios | Hecho (E7): calibrado el 2026-11-23 (`docs/pruebas/calibracion/2026-11-23`); la cobertura de validación (71 %) no alcanza la tolerancia (80 %) |
| RNF-L29 | Hay tres clientes: web, Android y escritorio | Android y escritorio atienden procesos distintos y el escritorio no copia a la web | Web, Móvil, Escritorio | Hecho |
| RNF-L30 | Son 31 microservicios, cada uno con una sola tarea (D27, D50, D53) | El catálogo está en [`microservicios.md`](../../arquitectura/microservicios.md) | Microservicios | Hecho |
| RNF-L31 | La web no lleva SQL en `frontend_web` | Los datos se piden a `backend_web` | Web | Hecho |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RNF-L03 | Plantillas Jinja2 | Viene con Flask (RNF-L02) |
| RNF-L15 | GitHub Actions | No hay integración continua (RNF-F07) |
| RNF-L18 | Room, Retrofit y WorkManager | Se cubre con RNF-L04 |
| RNF-L22 | Catorce semanas | Es un dato del proyecto, no un requerimiento |
| RNF-L23 | Equipo de estudiantes | Igual que RNF-L22 |
| RNF-L24 | Sin convenio institucional | Igual que RNF-L22 |
| RNF-L25 | Solo datos de prueba | Pasa a RNF-I15 |
| RNF-L26 | Doble propósito | Igual que RNF-L22 |
