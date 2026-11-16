> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RNF-J: Observabilidad

Cómo se sabe qué pasó dentro del sistema. El panel y el historial están en [RF-K](../funcionales/rf-k-monitoreo.md). Cómo leer la tabla: [`README.md`](../README.md).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Componente | Estado |
|---|---|---|---|---|
| RNF-J01 | Cada petición lleva un identificador de correlación | `X-Correlation-ID` se propaga de un servicio a otro y queda en la auditoría | Microservicios, Monitoreo | Hecho |
| RNF-J05 | Cada servicio responde su salud | Ver RF-K10 | Microservicios, Monitoreo | En parte (N3) |
| RNF-J06 | Los registros de cada servicio se pueden leer y buscar | Cada línea trae la fecha, el servicio, el nivel y el identificador de correlación | Microservicios, Monitoreo | Hecho |
| RNF-J12 | De cada corrida se sabe con qué se hizo | Se guardan la versión del motor, la versión congelada del escenario y la semilla (RF-E12) | Microservicios, Bases de datos | Hecho |
| RNF-J13 | Los registros se centralizan en la nube | Ver RF-K08 | Monitoreo, Infraestructura | Falta (N6) |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RNF-J02 | Rastrear una operación por todos los servicios | Se cubre con RNF-J01 |
| RNF-J03 | Métricas de negocio | No lo pide la rúbrica |
| RNF-J04 | CPU, memoria, disco y red por servicio | Se miden en las pruebas de volumen y de carga (RNF-A16, RNF-A17) |
| RNF-J07 | Alertas por umbral | Ver RF-K06 |
| RNF-J08 | Panel de monitoreo | Pasa a RF-K02 |
| RNF-J09 | Historial de incidentes | Pasa a RF-K03 |
| RNF-J10 | Origen de cada dato | Se cubre con la auditoría (RF-A06) y con las fuentes de los parámetros (RF-B09) |
| RNF-J11 | Métricas de simulación | Se cubre con RNF-A02 |
