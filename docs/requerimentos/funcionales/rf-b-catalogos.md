Estado: Obsoleto. Requiere actualizarse

# RF-B: Catálogos y Configuración

## Dependencias

_Sin dependencias registradas en dependencias.md._

### RF-B01 Catálogo de enfermedades

CRUD de enfermedades con parámetros base: transmisibilidad, periodo de incubación, duración de infecciosidad, letalidad por grupo etario, fracción asintomática
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-B02 Catálogo de regiones

CRUD de zonas geográficas: municipios, AGEBs, con datos poblacionales y capacidad hospitalaria asociada
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-B03 Catálogo de intervenciones

CRUD de tipos de intervención con parámetros modificables: cierre escolar, aforo, cubrebocas, vacunación, testeo
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-B08 Importación masiva

El sistema debe permitir importar datos censales (INEGI) en formato CSV/JSON para poblar regiones
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-B09 Fuente de parámetros

Cada parámetro debe incluir referencia a su fuente (documento, estudio, supuesto)
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-B10 Validación de rangos

El sistema debe validar que los parámetros ingresados estén dentro de rangos biológicamente plausibles
Criterio de aceptación: pendiente de definir
Prioridad: Alta

#### CU-B01: Alta de enfermedad

* **Actor:** Epidemiólogo, Administrador  
* **Flujo principal:**

  1\. Usuario ingresa datos de la enfermedad

  2\. Sistema valida rangos biológicos

  3\. Sistema valida completitud de parámetros obligatorios

  4\. Sistema guarda con versión inicial

  5\. Sistema registra en bitácora de auditoría

* **Postcondición:** Enfermedad disponible para escenarios
