Estado: Obsoleto. Requiere actualizarse

# RF-D: Gestión de Escenarios

## Dependencias

- RF-A (autenticación)
- RF-B (catálogos: enfermedades, intervenciones)
- PostgreSQL (scenarios)

### RF-D01 Creación de escenario

El sistema debe permitir crear escenarios con: enfermedad, población objetivo, región, calendario de intervenciones
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-D02 Intervenciones programadas

Cada intervención debe tener: tipo, fecha de inicio, fecha de fin, intensidad, grupo objetivo
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-D03 Validación de escenario

El sistema debe validar: fechas coherentes, intensidades en rango 0-100%, al menos una intervención definida
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-D04 Versionado

Cada edición crea nueva versión con autor, fecha y comentario obligatorio
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-D05 Comparación de versiones

El sistema debe mostrar diferencias entre versiones de un escenario
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-D06 Exportación XML

El sistema debe exportar el escenario en XML conforme al esquema definido (scenario.xsd)
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-D07 Importación XML

El sistema debe permitir importar escenarios desde archivo XML validado
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-D08 Duplicación

El sistema debe permitir duplicar un escenario como punto de partida para variante
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-D09 Publicación

El epidemiólogo debe poder marcar un escenario como "publicado" para el sitio público
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-D10 Etiquetado

El sistema debe permitir etiquetar escenarios (ej: "agresivo", "moderado", "reactivo")
Criterio de aceptación: pendiente de definir
Prioridad: Baja

### RF-D11 Clonación entre entornos

El sistema debe permitir exportar escenario de prueba a producción
Criterio de aceptación: pendiente de definir
Prioridad: Baja

### RF-D12 Desactivación

El usuario debe poder desactivar escenarios sin eliminarlos físicamente
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-D13 Restricción por rol

Solo analistas y epidemiólogos pueden crear/editar escenarios
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-D14 Plantillas

El sistema debe ofrecer plantillas de escenarios predefinidos (ej: "cierre total", "apertura gradual")
Criterio de aceptación: pendiente de definir
Prioridad: Media

#### Formato XML de escenario (scenario.xsd):

\<?xml version="1.0" encoding="UTF-8"?\>  
\<scenario version="1.0"\>  
  \<metadata\>  
    \<id\>uuid\</id\>  
    \<name\>Escenario de cierre escolar\</name\>  
    \<author\>usuario\_id\</author\>  
    \<created\>2026-08-27T10:00:00Z\</created\>  
    \<version\>3\</version\>  
    \<comment\>Se ajusta aforo a 50%\</comment\>  
  \</metadata\>  
  \<disease\>  
    \<id\>covid-19\</id\>  
    \<params\>  
      \<beta\>0.35\</beta\>  
   
   
   
      \<incubation\_mean\>5.2\</incubation\_mean\>  
      \<incubation\_sd\>1.8\</incubation\_sd\>  
      \<infectious\_mean\>7.0\</infectious\_mean\>  
      \<infectious\_sd\>2.1\</infectious\_sd\>  
    \</params\>  
  \</disease\>  
  \<population\>  
    \<region\>zmm-monterrey\</region\>  
    \<target\>1000000\</target\>  
    \<seed\_initial\_infected\>100\</seed\_initial\_infected\>  
    \<compliance\_mean\>0.72\</compliance\_mean\>  
  \</population\>  
  \<interventions\>  
    \<intervention id="1"\>  
      \<type\>school\_closure\</type\>  
      \<start\_day\>7\</start\_day\>  
      \<end\_day\>45\</end\_day\>  
      \<intensity\>1.0\</intensity\>  
      \<target\_group\>all\_students\</target\_group\>  
    \</intervention\>  
    \<intervention id="2"\>  
      \<type\>capacity\_reduction\</type\>  
      \<start\_day\>14\</start\_day\>  
      \<end\_day\>60\</end\_day\>  
      \<intensity\>0.5\</intensity\>  
      \<target\_group\>community\</target\_group\>  
    \</intervention\>  
    \<intervention id="3"\>  
      \<type\>vaccination\</type\>  
      \<start\_day\>30\</start\_day\>  
      \<end\_day\>120\</end\_day\>  
      \<intensity\>0.85\</intensity\>  
      \<target\_group\>age\_60\_plus\</target\_group\>  
      \<priority\>1\</priority\>  
    \</intervention\>  
  \</interventions\>  
\</scenario\>
