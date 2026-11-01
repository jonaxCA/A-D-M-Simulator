Estado: Obsoleto. Requiere actualizarse

# RF-E: Simulación y Procesamiento

## Dependencias

- RF-A (autenticación)
- RF-D (escenarios)
- Redis (cola)
- Motor de simulación

### RF-E01 Lanzamiento de simulación

El analista debe poder lanzar una corrida o ensamble de corridas desde la app de escritorio o web
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-E02 Encolamiento asíncrono

El sistema debe encolar trabajos de simulación sin bloquear la respuesta HTTP
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-E03 Número de réplicas

El sistema debe permitir configurar el número de réplicas por escenario (default: 30-50)
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-E04 Asignación de semillas

Cada réplica debe recibir una semilla aleatoria derivada de semilla maestra
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-E05 Monitoreo de progreso

El sistema debe mostrar porcentaje de avance de cada corrida (día simulado / días totales)
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-E06 Cancelación de trabajo

El usuario autorizado debe poder cancelar un trabajo en cola o en ejecución
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-E07 Reintento automático

El sistema debe reintentar automáticamente corridas fallidas por error transitorio (máx. 3\)
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-E08 Prioridad en cola

El sistema debe permitir marcar trabajos como alta prioridad
Criterio de aceptación: pendiente de definir
Prioridad: Baja

### RF-E09 Lanzamiento por lotes

La app de escritorio debe permitir encolar decenas de escenarios simultáneamente
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-E10 Comparación posterior

El sistema debe permitir comparar resultados de múltiples escenarios completados
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-E11 Notificación de término

El sistema debe notificar al usuario cuando su corrida termina (web \+ push)
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-E12 Reproductibilidad

Toda corrida debe ser reproducible: escenario \+ semilla \+ versión de motor registrados
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-E13 Límite de corridas concurrentes

El sistema debe limitar el número de corridas simultáneas según recursos disponibles
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-E14 Estimación de tiempo

El sistema debe mostrar tiempo estimado de finalización basado en corridas previas
Criterio de aceptación: pendiente de definir
Prioridad: Baja

### RF-E15 Selección de motor

El sistema debe permitir seleccionar motor de referencia (Python) o acelerado (CUDA)
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-E16 Validación de recursos

El sistema debe rechazar corridas que excedan capacidad de memoria disponible
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-E17 Ejecución calibración

El sistema debe permitir ejecutar barrido de calibración sobre parámetros seleccionados
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-E18 Resultados intermedios

El sistema debe guardar resultados parciales para recuperación ante fallo
Criterio de aceptación: pendiente de definir
Prioridad: Media

#### CU-E01: Lanzamiento de ensamble de simulación

* **Actor:** Analista  
* **Precondición:** Escenario validado y publicado  
* **Flujo principal:**

  1\. Analista selecciona escenario en app de escritorio

  2\. Configura 40 réplicas, motor CUDA, prioridad normal

  3\. App envía POST /api/v1/simulations

  4\. simulation-service valida escenario y recursos

  5\. simulation-service crea registro en simulation\_runs (PostgreSQL) con estado "encolado"

  6\. simulation-service envía trabajo a cola Redis

  7\. simulation-service responde job\_id inmediatamente

  8\. Worker del motor toma trabajo, actualiza estado a "ejecutando"

  9\. Worker actualiza progreso en Redis cada 10 días simulados

  10\. Worker escribe resultados en MongoDB al terminar

  11\. simulation-service marca trabajo como "completado"

  12\. Sistema envía notificación al analista

* **Postcondición:** Resultados disponibles para análisis
