Estado: Obsoleto. Requiere actualizarse

# RNF-A: Rendimiento

### RNF-A01 Tiempo de respuesta API

Las peticiones API estándar deben responder en \< 500 ms (p95)
Criterio de aceptación: ≤ 500 ms

### RNF-A02 Simulación 1M agentes

El motor acelerado debe simular 1 año con 1M de agentes en \< 5 minutos
Criterio de aceptación: ≤ 5 min

### RNF-A03 Simulación 100K agentes

El motor de referencia debe simular 100K agentes en \< 15 minutos
Criterio de aceptación: ≤ 15 min

### RNF-A04 Ensamble de 50 réplicas

Un ensamble de 50 réplicas debe completarse en \< 1 hora (motor acelerado)
Criterio de aceptación: ≤ 60 min

### RNF-A05 Throughput de ingesta

El sistema debe soportar ≥ 100 casos concurrentes por segundo
Criterio de aceptación: ≥ 100 req/s

### RNF-A06 Usuarios concurrentes web

El sistema web debe soportar ≥ 50 usuarios concurrentes sin degradación
Criterio de aceptación: ≥ 50 usuarios

### RNF-A07 Carga de tablero

El tablero principal debe cargar en \< 3 segundos con datos cacheados
Criterio de aceptación: ≤ 3 s

### RNF-A08 Sincronización móvil

Un lote de 100 casos debe sincronizarse en \< 30 segundos
Criterio de aceptación: ≤ 30 s

### RNF-A09 Consulta de resultados

Los resultados de simulación deben consultarse en \< 2 segundos
Criterio de aceptación: ≤ 2 s

### RNF-A10 Exportación de datos

Exportar series completas (365 días × 10 métricas) en \< 10 segundos
Criterio de aceptación: ≤ 10 s

### RNF-A11 Generación de mapa

El mapa de incidencia debe renderizar en \< 5 segundos
Criterio de aceptación: ≤ 5 s

### RNF-A12 Búsqueda en catálogos

Búsquedas con filtros en catálogos deben responder en \< 300 ms
Criterio de aceptación: ≤ 300 ms

### RNF-A13 Cola de trabajos

El sistema debe procesar al menos 4 corridas concurrentes
Criterio de aceptación: ≥ 4 workers

### RNF-A14 Tiempo de encolado

POST /simulations debe responder en \< 1 segundo (solo encola)
Criterio de aceptación: ≤ 1 s

### RNF-A15 Caché de curvas

Curvas cacheadas deben servirse en \< 200 ms
Criterio de aceptación: ≤ 200 ms
