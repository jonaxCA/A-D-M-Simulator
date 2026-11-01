Estado: Obsoleto. Requiere actualizarse

# RNF-C: Disponibilidad y Confiabilidad

### RNF-C01 Disponibilidad del sistema

El sistema web debe estar disponible ≥ 99.5% del tiempo
Criterio de aceptación: 99.5%

### RNF-C02 Resiliencia de servicios

La caída de un microservicio no debe afectar a los demás
Criterio de aceptación: Aislamiento total

### RNF-C03 Recuperación de trabajos

Un trabajo fallido por error transitorio debe reintentarse automáticamente
Criterio de aceptación: Hasta 3 reintentos

### RNF-C04 Persistencia de cola

Los trabajos encolados no deben perderse ante reinicio de Redis
Criterio de aceptación: Persistencia configurada

### RNF-C05 Respaldo programado

PostgreSQL debe respaldarse diariamente
Criterio de aceptación: RPO ≤ 24 h

### RNF-C06 Recuperación ante desastre

El sistema debe poder restaurarse desde respaldo en \< 4 horas
Criterio de aceptación: RTO ≤ 4 h

### RNF-C07 Datos no críticos en caché

La pérdida de Redis no debe implicar pérdida de datos críticos
Criterio de aceptación: Sin datos críticos en Redis

### RNF-C08 Modo degradado

Si MongoDB cae, la captura de casos debe seguir funcionando (usando PostgreSQL)
Criterio de aceptación: Degradación parcial

### RNF-C09 Verificación de integridad

El sistema debe verificar integridad de archivos almacenados
Criterio de aceptación: Hash SHA-256

### RNF-C10 Circuit breaker

Los servicios deben implementar circuit breaker para dependencias externas
Criterio de aceptación: Tolerancia a fallos

### RNF-C11 Health checks continuos

Todos los servicios deben responder health checks continuamente
Criterio de aceptación: Cada 30 s

### RNF-C12 Tiempo de recuperación

Un servicio caído debe recuperarse en \< 2 minutos tras detección
Criterio de aceptación: MTTR ≤ 2 min

### RNF-C13 Idempotencia

Las operaciónes de sincronización deben ser idempotentes
Criterio de aceptación: Retry seguro

### RNF-C14 Sin punto único de fallo

Nginx, base de datos y cola deben tener réplica o failover
Criterio de aceptación: Alta disponibilidad

### RNF-C15 Registro estructurado

Todos los servicios deben emitir logs estructurados en JSON
Criterio de aceptación: Formato uniforme
