> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-B: Catálogos

Función de soporte: los catálogos alimentan el formulario de la móvil (paso 1.3) y el editor de escenarios (paso 2.2). Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- RF-A (sesión y roles).
- PostgreSQL: `diseases`, `regions`, `intervention_types`.
- Servicios: `enfermedades`, `parametros`, `regiones`, `poblacion`, `tipos-intervencion`, `intervenciones` (solo el costo).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-B01 | Alta, edición y baja lógica de enfermedades. Las fijan EPIDEMIOLOGO y ADMINISTRADOR (D1); los demás roles solo consultan | Una enfermedad dada de baja no se borra (RN-07) y deja de ofrecerse en formularios nuevos. Cada cambio queda en la auditoría | Soporte, 1.3, 2.2 | Web, Microservicios | Alta | Hecho |
| RF-B02 | Catálogo de regiones: Nuevo León y sus 51 municipios, de solo lectura. El ADMINISTRADOR corrige la población y las bandas de edad | `regiones` lista los municipios. Una corrección de población queda en la auditoría | Soporte, 1.3, 2.2 | Web, Microservicios | Alta | Hecho |
| RF-B03 | Catálogo de tipos de intervención, de solo lectura, con el esquema de sus parámetros (`param_schema`) | El formulario de una intervención se arma con el esquema de su tipo (RF-D02) | 2.2, 2.4 | Microservicios | Alta | Hecho |
| RF-B09 | Cada parámetro de enfermedad y cada costo lleva su fuente o la marca de supuesto | `parametros` informa qué parámetros no tienen fuente ni marca. Si falta un dato, el sistema se niega a simular (RN-33) | Soporte | Microservicios, Web | Alta | Hecho |
| RF-B10 | Los parámetros se validan contra lo que acepta el motor | Un valor fuera de rango se rechaza con un mensaje que dice cuál y por qué (`validacion`) | 2.5 | Microservicios | Alta | Hecho |
| RF-B11 | EPIDEMIOLOGO y ADMINISTRADOR fijan el costo unitario de cada tipo de intervención, con su fuente o marca de supuesto | El costo nuevo entra al cálculo del paso 3.5. El cambio queda en la auditoría | Soporte | Web, Microservicios | Alta | Hecho |
| RF-B12 | La web exporta el catálogo de enfermedades a CSV | El archivo trae las enfermedades que se ven en la pantalla | Soporte | Web | Baja | Hecho |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-B08 | Importar datos del censo en CSV o JSON | La población del Censo 2020 llega con las semillas de la base (`datos/postgres/semillas/`). La carga de archivos en la web es otra brecha (RF-G16) |
