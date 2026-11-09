Estado: Obsoleto. Requiere actualizarse

# RF-C: Vigilancia Epidemiológica (Captura de Campo)

## Dependencias

- RF-A (autenticación)
- RF-B (catálogos: regiones)
- PostgreSQL (cases)
- GCS (evidencias)

### RF-C01 Registro de caso

La app móvil debe permitir capturar: folio, edad, sexo, municipio, AGEB, fecha de inicio de síntomas, cuadro clínico, resultado de laboratorio
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C02 Georreferenciación

La app debe capturar automáticamente coordenadas GPS del lugar de captura
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C03 Evidencia fotográfica

La app debe permitir adjuntar fotografías al caso usando CameraX
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-C04 Escaneo de QR

La app debe leer códigos QR de lotes de vacuna usando ML Kit
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C05 Escaneo de código de barras

La app debe leer códigos de barras de kits de prueba diagnóstica
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-C06 Validación local

La app debe validar en el dispositivo: campos obligatorios, rangos de edad, formatos de fecha
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C07 Modo sin conexión

La app debe almacenar casos localmente en Room cuando no hay conectividad
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C08 Sincronización posterior

La app debe reenviar automáticamente casos pendientes usando WorkManager
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C09 Deduplicación

El sistema debe evitar duplicados usando folio local generado por dispositivo
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C10 Folio de servidor

El sistema debe asignar folio único de servidor al recibir cada caso
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C11 Edición de caso

El usuario autorizado debe poder corregir datos de un caso ya registrado
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-C12 Validación semántica

El sistema debe validar coherencia: fecha de síntomas ≤ fecha de captura, edad en rango válido
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C13 Registro de vacunación

El sistema debe permitir registrar dosis aplicadas asociadas a lote escaneado
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C14 Estado de sincronización

La app debe mostrar claramente qué registros están pendientes de envío
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C15 Eliminación con justificación

El usuario debe poder marcar un caso como erróneo con motivo documentado
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-C16 Importación de datos históricos

El sistema debe permitir cargar series históricas desde archivos para calibración
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C17 Consolidación por AGEB

El sistema debe agregar casos por AGEB para alimentar el modelo
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-C18 Umbral de publicación

El sistema no debe publicar datos de AGEB con menos de N casos (protección de privacidad)
Criterio de aceptación: pendiente de definir
Prioridad: Alta

#### CU-C01: Captura de caso en campo sin conexión

* **Actor:** Capturista  
* **Precondición:** Dispositivo sin conectividad  
* **Flujo principal:**

  1\. Capturista abre formulario de nuevo caso

  2\. App valida campos obligatorios

  3\. App genera folio local (UUID \+ timestamp)

  4\. App captura coordenadas GPS

  5\. App guarda en Room con estado "pendiente"

  6\. WorkManager detecta reconexión

  7\. App envía caso al servidor

  8\. Servidor asigna folio oficial

  9\. App actualiza estado a "sincronizado"

* **Flujos alternativos:**  
  * Envío duplicado → servidor deduplica por folio local  
  * Error de validación → app muestra errores y permite corrección  
* **Postcondición:** Caso registrado en sistema con trazabilidad completa
