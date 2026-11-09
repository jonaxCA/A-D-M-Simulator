Estado: Obsoleto. Requiere actualizarse

# RF-F: Resultados y Análisis

## Dependencias

- RF-E (simulación completada)
- MongoDB (resultados)

### RF-F01 Curvas diarias

El sistema debe generar curvas de: casos nuevos, casos activos, hospitalizados, fallecidos acumulados
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-F02 Desglose por grupo etario

Resultados deben desglosarse por grupos: 0-17, 18-29, 30-59, 60+
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-F03 Desglose geográfico

Resultados deben desglosarse por municipio
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-F04 Indicadores resumen

Cada corrida debe reportar: pico máximo, día del pico, tasa de ataque, días-cama acumulados
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-F05 Estimación de costo

El sistema debe calcular días-persona de actividad económica perdida por escenario
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-F06 Mediana y banda

El sistema debe reportar mediana y banda de incertidumbre (percentiles 25-75) para ensambles
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-F07 Frontera de eficiencia

El sistema debe construir gráfica muertes vs. costo con frontera de Pareto
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-F08 Superposición de curvas

El sistema debe graficar múltiples escenarios superpuestos para comparación
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-F09 Exportación de datos

El sistema debe permitir exportar series en CSV y JSON
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-F10 Exportación gráfica

El sistema debe permitir exportar gráficas en PNG y PDF
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-F11 Reporte automático

El sistema debe generar reporte PDF con hallazgos principales de un análisis
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-F12 Análisis de sensibilidad

El sistema debe permitir visualizar efecto de variar un parámetro manteniendo otros constantes
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-F13 Comparación con datos reales

El sistema debe permitir superponer curva simulada con serie histórica real para validación
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-F14 Métricas de calibración

El sistema debe calcular error cuadrático medio y R² entre simulación y datos reales
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-F15 Mapa de incidencia

El sistema debe mostrar mapa 2D con incidencia por zona geográfica
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-F16 Animación temporal

El sistema debe permitir animar la evolución diaria sobre el mapa
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-F17 Compartición de resultados

El analista debe poder compartir vista de resultados con tomadores de decisión
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-F18 Favoritos

El usuario debe poder marcar resultados como favoritos para acceso rápido
Criterio de aceptación: pendiente de definir
Prioridad: Baja

#### CU-F01: Construcción de frontera de eficiencia

* **Actor:** Analista, Tomador de decisiones  
* **Precondición:** Al menos 3 escenarios completados  
* **Flujo principal:**

  1\. Usuario selecciona escenarios a comparar

  2\. Sistema recupera resultados de MongoDB

  3\. Sistema calcula mediana de muertes y costo por escenario

  4\. Sistema identifica puntos no dominados (frontera de Pareto)

  5\. Sistema genera gráfica interactiva

  6\. Usuario explora trade-offs

  7\. Usuario exporta gráfica o datos

* **Postcondición:** Decisión informada disponible
