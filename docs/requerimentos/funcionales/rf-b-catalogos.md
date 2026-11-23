> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-B: Catálogos

Función de soporte: los catálogos alimentan el formulario de la móvil (paso 1.3) y el editor de escenarios (paso 2.2). Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- RF-A (sesión y roles).
- PostgreSQL: `diseases`, `regions`, `intervention_types`, `case_definitions`, `disease_parameter_versions`, `health_areas`, `health_area_municipalities`, `census_population`, `population_versions`, `intervention_effectiveness`.
- Servicios: `enfermedades`, `parametros`, `regiones`, `poblacion`, `tipos-intervencion`, `intervenciones` (solo el costo).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-B01 | Alta, edición y baja lógica de enfermedades. Las fijan EPIDEMIOLOGO y ADMINISTRADOR (D1); los demás roles solo consultan | Una enfermedad dada de baja no se borra (RN-07) y deja de ofrecerse en formularios nuevos. Cada cambio queda en la auditoría | Soporte, 1.3, 2.2 | Web, Microservicios | Alta | Hecho |
| RF-B02 | Catálogo de regiones: Nuevo León y sus 51 municipios, de solo lectura. El ADMINISTRADOR corrige la población y las bandas de edad | `regiones` lista los municipios. Una corrección de población queda en la auditoría | Soporte, 1.3, 2.2 | Web, Microservicios | Alta | Hecho |
| RF-B03 | Catálogo de tipos de intervención, de solo lectura, con el esquema de sus parámetros (`param_schema`) | El formulario de una intervención se arma con el esquema de su tipo (RF-D02) | 2.2, 2.4 | Microservicios | Alta | Hecho |
| RF-B08 | Importar conjuntos de datos autorizados (CSV, JSON o XML), validarlos y registrar su fuente y su versión. Reabierto por la retroalimentación (gestión de datos del escritorio) | `importacion` (D53) recibe una serie agregada, la revisa (solo `periodo_inicio` y `valor`, periodos seguidos, metadatos de fuente, licencia y corte) y la guarda como la versión siguiente de su clave; `/validate` revisa sin guardar. Importan EPIDEMIOLOGO, ANALISTA y ADMINISTRADOR (`datasets.upload`) | Soporte | Microservicios, Escritorio | Media | Hecho (D53). La pantalla del escritorio es de A (A4) |
| RF-B09 | Cada parámetro de enfermedad y cada costo lleva su fuente o la marca de supuesto | `parametros` informa qué parámetros no tienen fuente ni marca. Si falta un dato, el sistema se niega a simular (RN-33) | Soporte | Microservicios, Web | Alta | Hecho |
| RF-B10 | Los parámetros se validan contra lo que acepta el motor | Un valor fuera de rango se rechaza con un mensaje que dice cuál y por qué (`validacion`) | 2.5 | Microservicios | Alta | Hecho |
| RF-B11 | EPIDEMIOLOGO y ADMINISTRADOR fijan el costo unitario de cada tipo de intervención, con su fuente o marca de supuesto | El costo nuevo entra al cálculo del paso 3.5. El cambio queda en la auditoría | Soporte | Web, Microservicios | Alta | Hecho |
| RF-B12 | La web exporta el catálogo de enfermedades a CSV | El archivo trae las enfermedades que se ven en la pantalla | Soporte | Web | Baja | Hecho |
| RF-B13 | Cada enfermedad tiene su clasificación (vía de transmisión y códigos CIE-10, con fuente) y su definición operacional de caso, versionada (retroalimentación, `enfermedades`) | La definición se edita como borrador y al publicarla pasa a vigente y la anterior a retirada; lo publicado no cambia. Una vigente por enfermedad. EPIDEMIOLOGO y ADMINISTRADOR la escriben; leer es público. La 042 trae las de la DGE de 2021 y 2023 (D56) | Soporte, 1.3 | Microservicios, Bases de datos | Media | Hecho en `enfermedades` (042) |
| RF-B14 | Cada parámetro puede llevar su intervalo de incertidumbre y cada cambio de los parámetros es una versión (retroalimentación, `parametros`) | El intervalo (min, max y tipo IC95, RIC o rango) contiene el valor y cabe en los límites del parámetro; `/parameters/status` lo muestra. Cada cambio guarda la versión completa con su motivo (D56) | Soporte | Microservicios, Bases de datos | Media | Hecho en `parametros` (042) |
| RF-B15 | Jerarquía territorial, jurisdicciones sanitarias y búsqueda territorial (retroalimentación, `regiones`) | `regiones` da los hijos de una región, las 8 jurisdicciones sanitarias de NL con sus municipios (Monterrey en tres, en parte) y busca estado, municipios y jurisdicciones sin importar acentos. La geometría y los mapas siguen en `zonas` (D56) | Soporte | Microservicios, Bases de datos | Media | Hecho en `regiones` (043) |
| RF-B16 | La población tiene versiones y periodos de referencia (retroalimentación, `poblacion`) | Cada ajuste guarda la versión siguiente de la región y, si cambió, la del estado, con su fuente, su periodo y su motivo; la serie de censos y conteos de INEGI 1990-2020 se consulta por región (D56) | Soporte | Microservicios, Bases de datos | Media | Hecho en `poblacion` (043) |
| RF-B17 | Cada tipo de intervención documenta sus supuestos de efectividad (retroalimentación, `tipos-intervencion`) | Valor de referencia, rango, fuente y marca de supuesto, general o por enfermedad; EPIDEMIOLOGO y ADMINISTRADOR los cambian. No cambian lo que se simula (D56) | Soporte, 2.4 | Microservicios, Bases de datos | Media | Hecho en `tipos-intervencion` (042) |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
