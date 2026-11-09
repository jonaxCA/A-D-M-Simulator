Estado: Obsoleto. Requiere actualizarse

# RNF-B: Escalabilidad

### RNF-B01 Escalado horizontal de servicios

Los microservicios deben ser escalables horizontalmente sin estado local
Criterio de aceptación: pendiente de definir

### RNF-B02 Escalado del motor

El motor debe permitir múltiples workers consumiendo la misma cola
Criterio de aceptación: pendiente de definir

### RNF-B03 Partición de datos

La base de datos debe soportar partición por fecha o región para crecimiento futuro
Criterio de aceptación: pendiente de definir

### RNF-B04 Límites definidos

El sistema debe definir y documentar límites máximos: agentes, corridas concurrentes, tamaño de archivo
Criterio de aceptación: pendiente de definir

### RNF-B05 Degradación elegante

Ante sobrecarga, el sistema debe degradar características no críticas antes que críticas
Criterio de aceptación: pendiente de definir

### RNF-B06 Almacenamiento incremental

Los resultados de simulación deben permitir adición sin reescritura completa
Criterio de aceptación: pendiente de definir

### RNF-B07 Índices para crecimiento

Los índices de bases de datos deben diseñarse para datasets de ≥ 10M de casos
Criterio de aceptación: pendiente de definir

### RNF-B08 Cola priorizada

La cola de trabajo debe soportar prioridades y fairness entre usuarios
Criterio de aceptación: pendiente de definir

### RNF-B09 Autoescalado

La infraestructura debe permitir encender/apagar workers según demanda
Criterio de aceptación: pendiente de definir

### RNF-B10 Caché distribuida

Redis debe configurarse para soportar réplicas y particionamiento
Criterio de aceptación: pendiente de definir
