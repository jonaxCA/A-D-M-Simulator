> **Estado: Borrador** · 2026-11-18 · Reestructurado con la retroalimentación del segundo parcial · Por validar en equipo

# EPIDEMIA — Checklist del tercer parcial y la entrega final

Objetivo: dejar el sistema **funcionalmente completo** y desplegado en GCP, con lo que pide la retroalimentación del profesor sobre el segundo parcial. La demostración integrada y los tres procesos de [`procesos_v3.md`](../../arquitectura/procesos_v3.md) tienen que correr de punta a punta, con MongoDB, Cloud Storage, nginx con HTTPS, límites de consumo, monitoreo y pruebas de carga.

Este documento son las tareas. No repite los requerimientos: cada casilla cita su origen.

- Los ID `RF-…` y `RNF-…` están en [`requerimentos/`](../../requerimentos/README.md).
- Las brechas (`I1`, `D-1`, `S6`, `N3`…) están en [`brechas_v3.md`](../../arquitectura/brechas_v3.md).
- Las decisiones (`D1` a `D35`) están en [`decisiones.md`](../../decisiones/decisiones.md), y sus pendientes en [`decisiones/todo.md`](../../decisiones/todo.md).
- `[Retro: …]` cita la retroalimentación del segundo parcial por su tema.

> Propuesta para repartir. Cada casilla debería ser un issue, una rama y un Pull Request.

## Qué manda

1. **La retroalimentación del segundo parcial** ([`RETROALIMENTACION_SEGUNDO_PARCIAL.txt`](RETROALIMENTACION_SEGUNDO_PARCIAL.txt)): son instrucciones del profesor para este proyecto.
2. **Las decisiones** (D1 a D35). Las que chocan con la retroalimentación se revisan: ver [«Lo que la retroalimentación reabre»](#lo-que-la-retroalimentación-reabre).
3. **La rúbrica general** ([`trabajo_por_parcial.txt`](../../rubrica/trabajo_por_parcial.txt)), la misma para todos los equipos de la clase.

## Alcance acordado

Respuestas del equipo sobre la retroalimentación (2026-11-18):

- **Entra todo lo que pide la retroalimentación**, salvo lo que ella misma llama propuesta o recomendación. Eso incluye que ningún cliente se conecte directo a PostgreSQL, MongoDB ni Redis, y que los servicios dejen de depender del monolito.
- **Calibración:** obligatoria. La validación y la fuente de datos las investigamos nosotros.
- **Casos:** se editan y se les da seguimiento.
- **Instituciones y regiones:** se modelan.
- **Corridas:** con prioridades, tiempo estimado y reintentos seguros.
- **Escritorio:** todos los módulos que lista la retroalimentación. La auditoría consulta quién creó, modificó, revisó o aprobó cada escenario.
- **Grupos:** cada salón entrega lo que le tocó.
- **Lo que no entra:** ver [«Fuera de alcance»](#fuera-de-alcance).

## Orden de trabajo

La retroalimentación pide primero completar la integración y demostrar un proceso de punta a punta, y después ampliar.

| Fase             | Qué                                                                                                                                                                                                         | Dónde                                             |
|------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------|
| 1. Integrar      | La [demostración integrada](#demostración-integrada-obligatoria) corre en local. Incluye las tres limitaciones que señala el profesor: MongoDB, la web que consume los servicios y la validación científica | D1, C6, E9 y «Validación científica» del bloque 0 |
| 2. Ampliar       | Los módulos que pide la retroalimentación para cada cliente y cada servicio, y lo de la rúbrica general: nube, bucket, nginx, volumen y Locust                                                              | A4, B4, C7, D2 a D7, E7, E8 y F                   |
| 3. Entrega final | Corregir, probar y documentar. No se terminan módulos                                                                                                                                                       | Todos                                             |

## Criterios de aceptación

Lo que el profesor pide demostrar. Una fase se cierra cuando sus pasos corren, no cuando sus casillas están marcadas.

### Demostración integrada obligatoria

[Retro: «Demostración integrada obligatoria»]. Primero en local y después en la nube.

| #  | Paso                                                                                                   | Cliente          | Bloques |
|----|--------------------------------------------------------------------------------------------------------|------------------|---------|
| 1  | Un analista inicia sesión y obtiene un JWT validado con Redis                                          | Escritorio       | A, E    |
| 2  | Elige enfermedad, región, población y parámetros epidemiológicos                                       | Escritorio       | A, D    |
| 3  | Crea dos escenarios: uno sin intervención y otro con medidas sanitarias                                | Escritorio       | A, D    |
| 4  | El sistema los valida y los registra en PostgreSQL                                                     | —                | D       |
| 5  | Un epidemiólogo aprueba las versiones                                                                  | Web              | C, D    |
| 6  | Se piden dos corridas y las procesa el motor                                                           | Escritorio       | A, E    |
| 7  | Los resultados extensos van a MongoDB, ligados a las corridas de PostgreSQL                            | —                | D       |
| 8  | El usuario consulta curvas, indicadores y resultados en la web                                         | Web              | C, E    |
| 9  | Se comparan las alternativas por sus consecuencias epidemiológicas y sus costos                        | Escritorio y web | A, C, E |
| 10 | Se presenta la frontera de Pareto                                                                      | Escritorio y web | A, C, E |
| 11 | Se prueban las API con JSON y XML, Swagger y XSD                                                       | Consola          | E       |
| 12 | Se fuerza el fallo de un servicio y se recupera sin duplicar corridas ni perder resultados confirmados | —                | D, E, F |

### Pruebas de aceptación

[Retro: «Para poder tener el sistema aceptable»].

| Prueba                     | Qué se comprueba                                                 | Bloques    |
|----------------------------|------------------------------------------------------------------|------------|
| Captura móvil              | Casos de prueba desde Android, con datos válidos e inválidos     | B, F       |
| Sincronización offline     | Lo guardado sin Internet se sincroniza sin duplicados            | B, F       |
| Integración del portal web | Una operación de la web consume realmente una API                | C, D, E, F |
| Autorización               | Un capturista no modifica escenarios de otra institución         | E, C       |
| Escenario de referencia    | Crear y versionar un escenario sin intervención                  | A          |
| Escenario alternativo      | Intervenciones con fechas, intensidad y duración                 | A          |
| Validación matemática      | Se rechazan parámetros epidemiológicos imposibles o incoherentes | D, 0       |
| Reproducibilidad           | Una corrida determinista repetida da el mismo resultado          | 0          |
| Modelo estocástico         | La misma semilla y la misma versión dan la misma corrida         | 0          |
| Sensibilidad               | Al variar los parámetros, el modelo responde como se espera      | 0, A       |
| Persistencia               | Los resultados se recuperan ligados entre PostgreSQL y MongoDB   | D          |
| Comparación                | Escenarios con la misma línea base y las mismas métricas         | A, E       |
| Incertidumbre              | Intervalos o distribuciones, con su interpretación               | 0, A, E    |
| Fallo de worker            | Una corrida interrumpida se recupera sin duplicar resultados     | E, D       |
| Contratos                  | Android consume JSON, y el escritorio, XML validado con XSD      | A, B       |

La prueba de usuarios queda fuera (ver «Fuera de alcance»).

## Lo que la retroalimentación reabre

Decisiones y «Fuera de alcance» que chocan con la retroalimentación. Cada fila pide una decisión nueva (bloque 0) o vuelve a meter el requerimiento; sus casillas están en los bloques que se indican.

| Hoy                                                                                                             | La retroalimentación pide                                                                                                                         | Bloques       |
|-----------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|---------------|
| La web va directo a PostgreSQL (D20) y a Redis (D33), e importa `backend_web` y `epidemia_comun`                | Ninguna aplicación cliente se conecta directo a PostgreSQL, MongoDB ni Redis                                                                      | 0, C, D, E, F |
| 28 de los 29 servicios importan `backend_web`, y la regla 2 de `microservicios/AGENTS.md` lo manda              | Dueños claros de las reglas de negocio, contratos de dominio separados y despliegues independientes; `epidemia_comun` solo con funciones técnicas | 0, D, E, F    |
| Sin calibración (D24); RF-C16, RF-F13, RF-F14 y RF-G14 fuera                                                    | Calibración, y validación contra observaciones                                                                                                    | 0, A, D       |
| Sin análisis de sensibilidad (RF-F12 fuera)                                                                     | Sensibilidad                                                                                                                                      | 0, A          |
| Los casos no se editan ni se rechazan (D32; RF-C11, RF-C15 y RF-I12 fuera)                                      | Actualización y seguimiento de casos, sin sobrescribir en silencio lo que cambió otro profesional, y avisos de registros rechazados               | 0, F, B       |
| Cuatro roles; `users` no tiene institución ni región                                                            | Seis perfiles; permisos por recurso, región, institución y operación                                                                              | 0, E          |
| Solo el ADMINISTRADOR lee la auditoría (D1)                                                                     | El escritorio consulta quién creó, modificó, revisó o aprobó cada escenario                                                                       | D, E, A       |
| Sin límite de sesiones (RF-A08 fuera) ni MFA                                                                    | MFA para perfiles críticos, sesiones concurrentes y dispositivos autorizados                                                                      | 0, E          |
| La cola atiende en orden de llegada, sin tiempo estimado ni reintentos (RF-E07, RF-E08, RF-E14 y RNF-B08 fuera) | Prioridades, tiempo estimado y reintentos seguros                                                                                                 | E             |
| Una corrida interrumpida se cierra como fallida (RNF-C03)                                                       | Recuperarla sin duplicar resultados                                                                                                               | 0, E, D       |
| El escritorio no tiene mapa (RF-H12 fuera) ni importa datos (RF-B08 fuera)                                      | Mapas regionales y gestión de datos                                                                                                               | A, D          |
| Los escenarios no se archivan (RF-D12 fuera)                                                                    | Archivado                                                                                                                                         | D, A          |
| Las réplicas se resumen solo en el escritorio (D8)                                                              | `resultados` con intervalos de incertidumbre                                                                                                      | E             |
| Sin ocupación hospitalaria (RF-G07 fuera: no hay fuente)                                                        | `indicadores` con capacidad utilizada                                                                                                             | 0, F          |

---

## Reparto

Somos siete, en dos salones. Cada salón tiene un rol, y dentro del salón cada persona lleva un bloque.

| Salón          | Rol del salón | Bloque | Persona         | Tema                                                                                                             | Revisa a |
|----------------|---------------|--------|-----------------|------------------------------------------------------------------------------------------------------------------|----------|
| 1 (3 personas) | **Clientes**  | **A**  | _por llenar_    | App de escritorio                                                                                                | B        |
| 1 (3 personas) | **Clientes**  | **B**  | Luz             | App Android                                                                                                      | C        |
| 1 (3 personas) | **Clientes**  | **C**  | _por llenar_    | Sistema web                                                                                                      | A        |
| 2 (4 personas) | **Backend**   | **0**  | Rolando (líder) | Coordinación y validación científica: decisiones, validación del modelo, calibración, integración y demostración | Todos    |
| 2 (4 personas) | **Backend**   | **D**  | Rolando         | Datos: MongoDB, Cloud Storage, volumen y los servicios de catálogos y escenarios                                 | E        |
| 2 (4 personas) | **Backend**   | **E**  | Enrique         | Microservicios y seguridad: los servicios de identidad y simulación, y separarlos del monolito                   | F        |
| 2 (4 personas) | **Backend**   | **F**  | Jonathan        | Nube, monitoreo, pruebas de carga y los servicios de vigilancia, analítica y plataforma                          | D        |

- **Salón 1, Clientes:** todo lo que ve el usuario. La app de escritorio (XML), la app Android (JSON) y el sistema web. No toca `microservicios/` ni `infra/`; si necesita un cambio ahí, lo pide al bloque dueño.
- **Salón 2, Backend:** todo lo que está detrás. Los microservicios, las bases de datos, los archivos, la nube y las pruebas de carga. No toca las pantallas de los clientes.
- **La revisión es dentro del salón,** para que se pueda hacer en clase.
- **El líder está en el salón 2.** El salón 1 nombra un enlace que le lleva las dudas y el avance. Propuesta: quien lleve el bloque C, que es quien más depende del backend.
- Cada quien escribe las pruebas y actualiza los documentos de lo que toca. Es parte de la definición de terminado, no un bloque aparte.
- **Cada salón entrega lo que le tocó** [Retro: participación]: el salón 1, los tres clientes; el salón 2, el backend. La matriz de autoría dice qué hizo cada persona.

### Dueños de los servicios

Cada servicio tiene un bloque dueño: completa lo que pide la retroalimentación para ese servicio (D7, E7 y F7), le quita las importaciones de `backend_web` (E8) y le agrega las rutas que necesite la web (E9).

| Bloque | Dominio                            | Servicios                                                                                                                                                                |
|--------|------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| D      | Catálogos y escenarios             | `enfermedades`, `parametros`, `regiones`, `poblacion`, `tipos-intervencion`, `escenarios`, `intervenciones`, `aprobacion`, `validacion`, `escenarios-xml` y `evidencias` |
| E      | Identidad y simulación             | `auth`, `sesiones`, `usuarios`, `roles`, `corridas`, `simulador`, `resultados`, `comparacion` y `pareto`                                                                 |
| F      | Vigilancia, analítica y plataforma | `casos`, `sincronizacion`, `dispositivos`, `vacunas`, `indicadores`, `series`, `zonas`, `notificaciones` y `estado-servicios`                                            |

## Dependencias entre salones

Lo que un bloque no puede terminar sin otro. El que entrega avisa en cuanto esté listo en la rama de integración.

| Espera  | De      | Qué                                                                                             |
|---------|---------|-------------------------------------------------------------------------------------------------|
| A       | D       | El bucket y la URL firmada, para subir el reporte (RF-F17)                                      |
| A       | E       | Que `corridas` acepte `abm-gpu` donde haya GPU (RF-H20)                                         |
| A       | D       | Proyectos de investigación, historial y archivado de escenarios (D7)                            |
| A       | E       | Las rutas de calibración y sensibilidad (E7)                                                    |
| A       | D       | Importar conjuntos de datos (D6)                                                                |
| A       | 0       | El método de calibración y el de sensibilidad                                                   |
| B       | D       | `evidencias` en el bucket, para las fotos (RF-C03)                                              |
| B       | E       | El aviso por lote de `sincronizacion` (RF-C19)                                                  |
| B       | F       | Editar casos con control de conflictos, y formularios por enfermedad (F7)                       |
| B       | E       | Institución y región de cada cuenta (E7)                                                        |
| C       | D       | MongoDB con `series_corridas` y el resumen en `simulation_runs` (RF-F21)                        |
| C       | E       | Cómo se identifica la web ante `resultados`, y los avisos de P2 (RF-D15, RF-D16)                |
| C       | D, E, F | Una ruta para cada cosa que la web hoy lee o escribe directo, cada bloque en sus servicios (E9) |
| A, B, C | F       | El dominio con HTTPS, para probar contra la nube                                                |
| E       | D       | El cliente de MongoDB y el del bucket en `epidemia_comun`, para `/health` (RF-K10)              |
| F       | D       | Los contenedores nuevos (MongoDB y el emulador del bucket) en el compose                        |
| F       | E       | Los servicios funcionando detrás de `/<servicio>` (D25)                                         |

**Ruta crítica:** las decisiones nuevas del bloque 0, la web que consume los servicios (C6 y E9) y nginx con el dominio (F). Mientras llegan, cada bloque avanza con lo que no depende de ellos.

## Definición de terminado

Una casilla se marca cuando:

- Tiene su prueba, y las pruebas de su carpeta pasan.
- Si es una ruta, lleva candado y se probó con un rol que entra y con uno que no.
- Si cambia datos, queda en la auditoría (`log_audit`).
- El contrato, el README o el manual que le toca está al día.
- El estado del requerimiento que cita se cambió a «Hecho».
- Cita su origen: la retroalimentación, la rúbrica, una decisión o un requerimiento.
- La revisó la pareja del salón y el Pull Request está integrado.

---

## 0. Coordinación y validación científica · Líder (salón 2)

### Decisiones que frenan a otros

Ninguna se implementa sin respuesta. Cada respuesta se anota en `decisiones/`. El detalle de las respuestas está en [`preguntas0.md`](preguntas0.md).

- [ ] Definir qué cambia en la interfaz del escritorio para que sea más intuitiva y usable. **Frena a A.** Delegada al bloque A (A1).
- [x] ¿El ADMINISTRADOR también captura casos? (D1). **Frena a C** y a la migración 034. No (D1).
- [x] ¿Qué hace la web si Redis no responde? (I3, RF-A12). **Frena a C.** Conserva las sesiones abiertas y no deja entrar (D33, validada el 2026-11-17).
- [x] ¿Cómo se identifica la web ante `resultados` para pedir las curvas? (D20). **Frena a C y a E.** Con el JWT de la sesión (D34, validada el 2026-11-17).
- [x] ¿El aviso de casos nuevos usa el tipo `SYSTEM` o lleva una migración con un tipo propio? (D32). **Frena a E.** Migración 037 con `NEW_CASES`, `SCENARIO_SUBMITTED` y `SCENARIO_REJECTED` (D32).
- [x] ¿«Validación del JWT» pide que el escritorio revise `exp`? (C10, RF-H23). **Frena a A.** Sí (D35).
- [x] ¿La serie diaria lleva el desglose por grupo de edad? (RF-F02, D28). **Frena a D.** No (D28).
- [ ] ¿Quién consigue el dominio y con qué proveedor? (D26). **Frena a F.** Delegada al bloque F (F2).
- [x] ¿Qué archivo recibe la web? (D-5, RF-G16). **Frena a C.** El reporte de una comparación (D35).
- [x] ¿Cómo entra la vacunación a la frontera de Pareto? (D3). Como fracción de día-persona por dosis (D3).
- [x] ¿Se retiran los roles `app_*` de la migración 009, y qué rol de base usa el monolito? (D18). No; la web sigue con `epidemia_app` (D18).
- [ ] Con el profesor: confirmar el volumen de D29 y si hay créditos para la GPU (brechas §8). **Frena a D y a F.** Créditos: sí (D23). Falta el volumen.

### Decisiones nuevas por la retroalimentación

Cada una reemplaza o amplía una decisión vigente (ver [«Lo que la retroalimentación reabre»](#lo-que-la-retroalimentación-reabre)) y se registra en `decisiones/` con número nuevo.

- [x] La web consume los servicios: en qué orden pasa cada módulo y qué ve el usuario cuando un servicio no responde. Reemplaza D20 y D33. **Frena a C y a E.** Opción B, sin respaldo en la base; orden de la demostración integrada (D36).
- [ ] Dueño de cada regla de negocio, y cómo dejan los servicios de importar `backend_web`. Cambia las reglas 2 y 14 de `microservicios/AGENTS.md`. **Frena a E.**
- [ ] Instituciones, regiones y los perfiles INVESTIGADOR y AUTORIDAD SANITARIA, con los permisos por recurso, región, institución y operación. Amplía D1. **Frena a E, B y C.**
- [ ] Editar y rechazar casos: qué se edita, quién lo hace y cómo se detecta un conflicto. Reemplaza lo de D32 sobre editar casos. **Frena a E y a B.**
- [ ] Calibración: método, función de pérdida, métricas de ajuste, datos y dónde corre. Reemplaza D24. **Frena a A.**
- [ ] Corridas interrumpidas: reencolarlas en lugar de cerrarlas como fallidas, y qué pasa con su serie en MongoDB (RNF-C03). **Frena a E y a D.**
- [ ] MFA: qué perfiles son críticos y con qué segundo factor. **Frena a E.**
- [ ] Qué son «campañas» y «seguimiento de intervenciones» en la web, y qué datos llevan. **Frena a C y a E.**
- [ ] Qué agrupa un proyecto de investigación del escritorio y dónde vive. **Frena a A y a E.**
- [ ] Reservar los números de migración para lo nuevo: instituciones y perfiles, casos, corridas, proyectos y calibración.

### Validación científica

[Retro: «Hace falta validación científica»]. Lo que no se valide se presenta como exploratorio.

- [ ] Ficha de cada modelo (`seir-ref`, `abm-ref` y `abm-gpu`): formulación matemática, población representada, variables, supuestos, fuentes de parámetros, límites de aplicación, versión del algoritmo, escenarios de prueba y resultados de validación. Se amplía [`ficha_simulador.md`](../../arquitectura/ficha_simulador.md).
- [ ] Investigar una fuente de datos observados para validar y calibrar: qué serie, de qué periodo y con qué licencia. Con D (D6).
- [ ] Validación contra resultados esperados: soluciones conocidas (por ejemplo, el tamaño final de un brote SEIR), casos límite y `abm-ref` contra `seir-ref` (ya medido en la ficha).
- [ ] Validación contra los datos observados.
- [ ] Análisis de sensibilidad: variar cada parámetro y comprobar que el modelo responde como se espera (RF-F12, reabierto). El escritorio lo muestra (A4).
- [ ] Calibración: el algoritmo en `procesamiento/`, con su función de pérdida, sus métricas de ajuste y sus versiones. El escritorio la muestra (A4) y un servicio la expone (E7).
- [ ] Reproducibilidad: la corrida determinista repetida, y la estocástica con la misma semilla y versión, dan lo mismo. Las pruebas existen (`test_contrato_motor.py`); falta la evidencia para la entrega.
- [ ] Incertidumbre: cada intervalo se muestra con su interpretación.
- [ ] Las pantallas distinguen simulación exploratoria, predicción y resultado validado. Hoy `AVISO_SIMULACION` solo dice que no es una predicción.

### Documentos

- [ ] Validar en equipo los requerimientos y pasarlos de Borrador a Aceptado.
- [ ] Validar la arquitectura v3 contra la rúbrica (brechas §9.5) y marcar la v2 como Obsoleta.
- [ ] Corregir en `procesos_v3.md` las referencias de sección que quedaron desfasadas con `brechas_v3.md`.
- [ ] Limpiar `decisiones/todo.md`: quitar lo hecho y las decisiones que ya no están pendientes.
- [ ] Llenar los nombres de la tabla de reparto de este documento.
- [ ] Llevar a los requerimientos lo que la retroalimentación reabre: sacarlo de «Fuera de alcance» y darle estado.
- [ ] Actualizar el `AGENTS.md` de la raíz y `microservicios/AGENTS.md` con las decisiones nuevas. Hoy dicen que la web no llama a los servicios, que los servicios reutilizan `backend_web` y que la calibración está fuera.

### Integración

- [ ] Crear un issue por casilla, con su bloque y su responsable.
- [x] Reservar los números de migración de cada bloque: tabla y reglas en [«Números reservados»](../../../datos/postgres/migraciones/README.md#números-reservados-tercer-parcial) (2026-11-17).
- [ ] Confirmar el número de cada migración antes de que alguien la cree, y agregar a esa tabla los que se pidan fuera de ella.
- [ ] Integrar las ramas de los dos salones al menos una vez por semana.
- [ ] Ensayar P1, P2 y P3 de punta a punta en la nube, con cada rol.
- [ ] Guion de la demostración integrada: los 12 pasos de [«Criterios de aceptación»](#criterios-de-aceptación), primero en local y después en la nube.

### Entrega final

- [ ] Expediente técnico con los apartados que lista la rúbrica. Se arma enlazando lo que ya hay en `docs/`.
- [ ] Wiki: miembros y roles, por dónde empiezo y glosario (`docs/todo.md`).
- [ ] Un README en cada carpeta de `docs/`.
- [ ] Video de demostración y presentación final.
- [ ] Matriz individual de autoría y participación: servicios, pruebas, integración, documentación, incidencias y correcciones de cada estudiante [Retro: participación].
- [ ] Qué entregó cada salón, por separado [Retro: participación].
- [ ] Toda la suite en una sola ejecución, sobre una base creada desde cero, con un solo resultado consolidado. Nada de juntar pruebas de distintas versiones [Retro: pruebas].
- [ ] Cada integrante ensaya ejecutar, explicar y modificar lo que le tocó, para la defensa técnica [Retro: participación].

---

# Salón 1 · Clientes

## A. App de escritorio · `frontend_desktop/`

Antes de empezar: `frontend_desktop/AGENTS.md`. La app solo habla XML.

### A1. Interfaz más intuitiva y usable

**Pendiente de definir** (bloque 0). Las casillas de implementación se escriben cuando exista la definición. La meta [Retro: usuarios finales]: un epidemiólogo o un analista entiende, configura, ejecuta y compara escenarios sin saber programar, y la app le muestra el progreso, errores que se entienden, resultados visuales, supuestos y limitaciones.

- [ ] Proponer los cambios, pantalla por pantalla, y acordarlos con el líder.
- [ ] Implementar los cambios acordados.
- [ ] Rehacer las capturas de `docs/manuales/manual_usuario_escritorio.md`.

### A2. Funciones que faltan

- [ ] Avisar cuando las bandas p5–p95 de dos escenarios se enciman (A3, RF-H22, RF-F23).
- [ ] Mostrar la escala que ya responde `resultados`: habitantes por agente (D6, RF-H21, RF-F20).
- [ ] Ofrecer `abm-gpu` en el selector de motor solo si `corridas` lo acepta (D23, RF-H20, RF-E15).
- [ ] Subir el reporte exportado al bucket y mostrar su URL firmada (D30, RF-F17). Espera a D.
- [ ] Leer `exp` del token sin verificar la firma y renovarlo antes de que venza (D35, RF-H23).
- [ ] La comparación dice «Personas-día» donde hoy dice «Costo», y muestra y exporta `costo_pesos` aparte, como «sin dato» cuando es nulo (D3, `ui/comparacion.py` y `exportar.py`). Desde el 2026-11-17 `pareto` ya manda personas-día en `costo`: hasta este cambio, la pantalla las rotula como costo.

### A3. Verificar

- [ ] Sin red, con un rechazo del servidor y con la sesión vencida, la app explica qué pasó sin mostrar la traza (RF-H24, RNF-E06).
- [ ] La app pasa la lista de la rúbrica para el escritorio: búsqueda, filtros, tabla de resultados, validación con XSD y exportación.
- [ ] La app funciona contra el dominio con HTTPS y con el directorio de `estado-servicios` detrás de nginx (D25, D26). Espera a F.
- [ ] `python -m pytest frontend_desktop` pasa.

### A4. Módulos que pide la retroalimentación

[Retro: «Aplicación de escritorio»]. Todos son obligatorios. Algunos ya existen en parte (el editor, la comparación y Pareto): la primera casilla es revisarlos.

- [ ] Revisar la app contra esta lista y marcar lo que ya cumple.
- [ ] Proyectos: crear una investigación con su región, su enfermedad, su periodo y sus modelos. Espera a la decisión (0) y a D (D7).
- [ ] Gestión de datos: importar conjuntos autorizados, verificar su calidad, examinar sus series y registrar versiones. Espera a D (D6).
- [ ] Configuración del modelo: elegir el modelo, ajustar parámetros y ver sus definiciones y unidades.
- [ ] Editor de escenarios: crear, duplicar, editar y versionar escenarios de referencia y de intervención.
- [ ] Intervenciones con fecha de inicio, duración, cobertura, intensidad y costos.
- [ ] Calibración: ajustar parámetros con series históricas y comparar el ajuste. Espera a 0 y a E.
- [ ] Validación: escenarios de prueba, análisis de sensibilidad y restricciones matemáticas. Espera a 0.
- [ ] Ejecución: iniciar, cancelar, monitorear y recuperar corridas asíncronas.
- [ ] Comparación: escenarios a la vez, diferencias, incertidumbre y métricas epidemiológicas.
- [ ] Análisis económico: costos bajo supuestos explícitos y costo-efectividad exploratoria (D3).
- [ ] Análisis de Pareto con objetivos comparables y documentados.
- [ ] Mapas regionales: distribución, intensidad e indicadores por zona (RF-H12, reabierto).
- [ ] Reportes: resultados, parámetros, versiones, gráficas, metodología y limitaciones.
- [ ] Reproducibilidad: guardar la semilla, la versión del modelo, los datos, los parámetros y las condiciones, y repetir la corrida.
- [ ] Auditoría: quién creó, modificó, revisó o aprobó cada escenario. Espera a D (D7).
- [ ] Cada curva lleva a su escenario, a sus supuestos y a su corrida, que se puede reproducir.
- [ ] Ninguna gráfica sin fuente, periodo, modelo, versión y unidades.

## B. App Android · `frontend_movil/`

La app solo habla JSON.

### B1. Funciones que faltan

- [ ] Indicador de conexión fijo, visible en todas las pantallas (C3, RF-I20, RNF-E11).
- [ ] Menú por rol: un rol distinto del CAPTURISTA no ve la captura (C8, RF-I19).
- [ ] Las fotos se suben y se bajan con la `evidencias` del bucket (D30, RF-C03). Espera a D.
- [ ] Probar que el aviso por lote no se repite cuando la app reintenta el mismo lote (D32, RF-C19). Espera a E.
- [ ] Mostrar los tipos de aviso de la migración 037 (`NEW_CASES`, `SCENARIO_SUBMITTED` y `SCENARIO_REJECTED`) en `Formato.kt` (D32).

### B2. Verificar

- [ ] Sin red, con un rechazo del servidor y con la sesión vencida, la app explica qué pasó sin cerrarse (RF-I22, RNF-E06).
- [ ] Los casos sin enviar se quedan al cerrar sesión y se mandan cuando esa cuenta vuelve a entrar (D19, RF-I21).
- [ ] La app pasa la lista de la rúbrica para Android: perfil, consulta, registro, actualización (dosis y avisos, D32) y borrado local de credenciales.
- [ ] La app funciona contra el dominio real con su certificado, de preferencia también en un Android 7.0 (D26). Espera a F.
- [ ] Las pruebas de `frontend_movil` pasan.

### B3. Entregables

- [ ] Manual de usuario de la app móvil en `docs/manuales/` (RNF-E08).
- [ ] APK de la demostración, apuntando al dominio de la nube.

### B4. Módulos que pide la retroalimentación

[Retro: «Aplicación móvil Android»]. Para capturistas, personal de vigilancia, supervisores regionales y responsables de campañas.

- [ ] Revisar la app contra esta lista y marcar lo que ya cumple.
- [ ] Panel del capturista: casos pendientes, formularios, registros incompletos, sincronizaciones pendientes y avisos.
- [ ] Seguimiento: actualizar el estado de un caso, con observaciones e historial (RF-I12, reabierto). Espera a F (F7).
- [ ] Formularios por enfermedad, con versiones, validaciones y campos obligatorios. Espera a F (F7).
- [ ] GPS, con selección manual cuando la captura automática no conviene.
- [ ] Cola local cifrada: hoy Room guarda los casos sin cifrar y solo los tokens van cifrados.
- [ ] Un caso no se muestra como recibido, validado o publicado hasta que el servidor lo confirma.
- [ ] La sincronización no sobrescribe en silencio lo que cambió otro profesional: el conflicto se muestra. Espera a F (F7).
- [ ] Consulta epidemiológica agregada por zona, periodo y enfermedad, según los permisos.
- [ ] Alertas: tareas nuevas, registros rechazados, campañas y eventos de vigilancia, desde `notificaciones`. Espera a F (F7).
- [ ] Control de calidad: avisa de campos incompletos, fechas incoherentes y posibles duplicados.
- [ ] Perfil con institución, región asignada y estado de conexión. Espera a E (E7).
- [ ] Menú para cada perfil de campo. Espera a la decisión de perfiles (0).

## C. Sistema web · `frontend_web/` y `backend_web/`

La web deja de ir directo a PostgreSQL y a Redis, y consume los servicios (C6; reemplaza D20). Mientras tanto, nada de SQL en `frontend_web`.

### C1. Permisos (D1)

- [ ] Migración 034: crea `scenarios.approve`, lo da a EPIDEMIOLOGO y ADMINISTRADOR, quita `audit.read` al EPIDEMIOLOGO (RF-L05) y quita `cases.create` al ADMINISTRADOR. También crea `reports.upload` para ANALISTA y ADMINISTRADOR (D35).
- [ ] Quitar la captura de casos de la web: `/reportes/nuevo`, sus enlaces y su plantilla.
- [ ] Guardar los permisos en la sesión y crear `requiere_permiso(codigo)`, que responde 403 y registra `PERMISSION_DENIED` (RF-A05).
- [ ] Cambiar el candado de cada ruta según la [matriz de permisos](../../requerimentos/matriz-permisos.md).
- [ ] El CAPTURISTA entra solo al tablero y al mapa; lo demás le responde 403 (RF-G11).
- [ ] Cuenta de prueba de CAPTURISTA en `datos/postgres/semillas/demo_datos_nl.sql`.
- [ ] Probar cada pantalla con un rol que entra y con uno que no (pruebas de roles).

### C2. Sesión y seguridad

- [x] La web registra y revisa su sesión en Redis; cerrar sesión deja el token sin valor (I3, RF-A12). Verificado el 2026-11-16: `demo_fallos.py web` y `redis` (`docs/pruebas/fallos/2026-11-16`).
- [ ] Protección contra CSRF en los formularios (RNF-D07).
- [ ] Encabezados de seguridad en las respuestas (RNF-D21).
- [ ] Verificar que ninguna consulta arma SQL con texto del usuario (RNF-D05) y que las plantillas escapan lo que muestran (RNF-D06).

### C3. Resultados y archivos

- [x] La corrida muestra su resumen desde `simulation_runs` y pide las curvas a `resultados`. Si `resultados` no responde, se ve el resumen sin curvas (D28, D20, RF-F21). Espera a D y a E.
- [x] La web deja de leer `simulation_results`. Hecho en D1 (2026-11-18), también en `/comparacion`.
- [ ] La web muestra la foto de un caso con una URL firmada que vence en minutos (D30, RF-C20). Espera a D.
- [ ] La web abre el reporte de una comparación con su URL firmada (RF-F17). Espera a D.
- [ ] La web recibe el reporte de una comparación (ANALISTA y ADMINISTRADOR, `reports.upload`), lo valida por su contenido, su tamaño y su huella, y lo manda al bucket con la misma tabla y la misma interfaz que el escritorio (D35, RF-G16). Espera a D.
- [ ] `/comparacion` dice personas-día en el eje y la tabla de la frontera, y muestra `costo_pesos` aparte (D3). Desde el 2026-11-17 `costo` ya viene en personas-día: hasta este cambio, la gráfica lo rotula «Costo total de intervención».
- [ ] `/comparacion/costos` permite fijar las personas-día por dosis de la vacunación, con fuente o marca de supuesto (D3, migración 040). Sin ese factor, la comparación de escenarios con vacunación se niega.

### C4. Avisos de P2

- [ ] Al aprobar o rechazar en la web se avisa al autor, en los dos casos (I1, RF-D16).
- [ ] El EPIDEMIOLOGO ve en la web los avisos de versiones por revisar y de casos nuevos (RF-D15, RF-C19).

### C5. Verificar y entregar

- [ ] El tablero y el mapa se leen en un teléfono (RNF-E03).
- [ ] Los errores se explican sin mostrar la traza (RNF-E06).
- [ ] Las pantallas de resultados conservan el aviso de que no es una predicción (`AVISO_SIMULACION`).
- [ ] Manual de usuario de la web en `docs/manuales/` (RNF-E08).

### C6. La web consume los servicios

[Retro: «Ninguna aplicación cliente deberá conectarse directamente a PostgreSQL, MongoDB o Redis»]. Va con la decisión que reemplaza D20 (bloque 0).

- [ ] Inventario: cada pantalla de la web y cada consulta de `backend_web` que usa, con el servicio que debe atenderla. Lo que no tenga servicio se le pide a su dueño (E9).
- [ ] Iniciar y cerrar sesión con `auth` y `sesiones`, sin leer Redis.
- [ ] Pasar cada módulo a su servicio, en el orden que fije la decisión.
- [ ] Cuando un servicio no responde, la pantalla lo explica y lo demás sigue.
- [ ] Al terminar, la web no tiene credenciales de PostgreSQL, MongoDB ni Redis, y no importa `epidemia_comun`.

### C7. Módulos que pide la retroalimentación

[Retro: «Aplicación web»]. Algunos ya existen (el tablero, el mapa y las regiones): la primera casilla es revisarlos.

- [ ] Revisar la web contra esta lista y marcar lo que ya cumple.
- [ ] Administración regional.
- [ ] Vigilancia: casos por región y periodo, con su seguimiento.
- [ ] Campañas. Espera a la decisión (0).
- [ ] Mapas epidemiológicos e indicadores.
- [ ] Reportes.
- [ ] Seguimiento de intervenciones. Espera a la decisión (0).
- [ ] Institución y región de cada cuenta en la administración de usuarios. Espera a E.
- [ ] Ninguna gráfica sin fuente, periodo, modelo, versión y unidades.

---

# Salón 2 · Backend

Antes de empezar: `microservicios/AGENTS.md`.

## D. Datos: MongoDB, Cloud Storage y volumen

### D1. MongoDB (D28, D-1)

- [x] Contenedor de MongoDB en `infra/docker-compose.yml`, con su contraseña en `genera_env.py`. `mongo:7.0`, usuario `epidemia` creado por `infra/mongo/10-usuario.js`; puerto local 27018.
- [x] Cliente de MongoDB en `epidemia_comun`, para que ningún servicio lo arme por su cuenta (RNF-L07). `mongo.py`; `/health` hace `ping`.
- [x] Colección `series_corridas`: un documento por día de cada corrida, con los totales del día (sin desglose por grupo), `scenario_version_id`, motor y `version_esquema`. Índices `{run_id, dia}` y `{scenario_version_id, motor, dia}` (D28, RF-E20, RNF-K03, RNF-K14).
- [x] Colección `historial_servicios`, con TTL de 30 días (RF-K03, RNF-K17).
- [x] `simulador` guarda la serie en MongoDB y el resumen en `simulation_runs` (RF-E20).
- [x] Migración 038 con las columnas del resumen en `simulation_runs`.
- [x] `resultados` lee la serie de MongoDB y conserva su caché de Redis.
- [x] `estado-servicios` pasa su historial de Redis a MongoDB (RF-K03). `/history` agrega además la disponibilidad y la latencia de 24 h.
- [x] Demostrar inserción, consulta, actualización y agregación, cada una con su prueba. La agregación: la banda p5–p95 por día de una versión y un motor (D28).
- [x] `simulation_results` deja de usarse. Retirarla con la migración 041, cuando la web (C) ya no la lea. Corte inmediato (2026-11-18): D1 también cambió la web (ver C3).
- [x] Si MongoDB no responde, la corrida termina con su resumen y la captura de casos sigue (RNF-C08). La serie se reintenta cada 30 s (`test_compose_mongo.py`).

### D2. Cloud Storage (D30, D-3)

- [ ] Una interfaz de archivos en `epidemia_comun` que cambie de disco a bucket por configuración. La web también la usa (D35), y hoy no importa `epidemia_comun`: acordar con C dónde vive.
- [ ] Emulador del bucket en el compose, para trabajar en local.
- [ ] `evidencias` guarda en el bucket y deja de usar su volumen (RF-C03, RNF-B01).
- [ ] URLs firmadas que vencen en minutos para los archivos privados (RNF-D17, RNF-D27).
- [ ] Validar cada archivo por su contenido, su tamaño y su huella al subirlo (RNF-C09).
- [ ] Tabla nueva con los metadatos de los reportes, y la ruta para subir uno (RF-F17). La usan el escritorio y la web (D35). Migración 039.
- [ ] Si el bucket no responde, el caso se guarda y la foto se reintenta (RNF-C19).
- [ ] Crear el bucket real en GCP, privado, con su cuenta de servicio (RNF-K12, RNF-K18). Con F.

### D3. Volumen (D29, D-6)

- [ ] Generar el conjunto de alto volumen: unas 10,000 corridas de 180 días. La cifra se confirma con el profesor (RNF-A17).
- [ ] Medir el tiempo de inserción y el de consulta, con y sin índice.
- [ ] Medir la consulta de resultados con y sin la caché de Redis (RNF-A09).
- [ ] Medir CPU, memoria y disco durante la carga.
- [ ] Escribir los resultados en `docs/`, con la forma de repetirlos.

### D4. Documentos

- [ ] Diseño de MongoDB y de los buckets en la arquitectura v3, con qué información va a PostgreSQL y cuál a MongoDB [Retro: MongoDB].
- [ ] Llenar la retención de cada dato en `matrices_v3.md`: hoy hay 48 «Por definir» (RNF-K07).
- [ ] Actualizar `docs/arquitectura/microservicios.md` con lo que cada servicio escribe ahora.

### D5. MongoDB después de D1

[Retro: «MongoDB deberá incorporar referencias estables…» y «Fallo de worker»].

- [ ] Cada documento de `series_corridas` trae `scenario_id`, además de `run_id`, `scenario_version_id` y la versión del motor. Hecho en `feat/bloque-D` (2026-11-18); se marca al integrarse.
- [ ] La serie se guarda antes de confirmar la corrida: si el proceso muere entre los dos pasos, la corrida no queda completada sin curvas. Hecho en `feat/bloque-D` (2026-11-18); se marca al integrarse.
- [ ] La serie de una corrida que el arranque cierra como fallida no se queda en MongoDB, o `banda()` la ignora. Va con la decisión de corridas interrumpidas (0).
- [ ] Con MongoDB caído y el simulador muerto después de confirmar, la serie se regenera con la misma semilla, comprobando la huella del escenario y el resumen. Va con la misma decisión.

### D6. Gestión de datos

[Retro: «Gestión de datos» del escritorio y validación científica].

- [ ] Importar conjuntos de datos autorizados (CSV, JSON o XML), validarlos y registrar su fuente y su versión (RF-B08, reabierto). Lo usa el escritorio (A4).
- [ ] Guardar la serie observada que usan la validación y la calibración, con su fuente (bloque 0).

### D7. Completar los servicios de catálogos y escenarios

[Retro: «Microservicios existentes que deben completarse y fortalecerse»]. Los servicios de D en [«Dueños de los servicios»](#dueños-de-los-servicios). La lista es lo que pide la retroalimentación, no lo que falta: lo que ya se cumpla se marca al revisarlo. Lo que dice «reabierto» o «hoy no existe» ya se revisó.

- [ ] Revisar cada servicio contra su lista de la retroalimentación y marcar aquí lo que ya cumple.

**Catálogos**

- [ ] `enfermedades`: definiciones de caso versionadas.
- [ ] `parametros`: incertidumbre y versiones de cada parámetro.
- [ ] `regiones`: jerarquía (país, estado, municipio y área sanitaria), geometrías y búsqueda territorial.
- [ ] `poblacion`: versiones y periodos de referencia.
- [ ] `tipos-intervencion`: supuestos de efectividad de cada tipo.

**Escenarios**

- [ ] `escenarios`: archivar (RF-D12, reabierto) y proyectos de investigación (decisión del bloque 0).
- [ ] Historial de un escenario: quién lo creó, modificó, revisó o aprobó (para A4).
- [ ] `aprobacion`: devolver una versión para cambios, además de rechazarla, y firmar la versión aprobada.

## E. Microservicios y seguridad

### E1. Avisos (I1)

- [x] `sincronizacion` crea un aviso por lote a los EPIDEMIOLOGO cuando el lote trae casos nuevos. Un reintento del mismo lote no vuelve a avisar (D32, RF-C19).
- [x] Al enviar una versión a revisión se avisa a los EPIDEMIOLOGO (RF-D15).
- [x] `aprobacion` avisa al autor también cuando se rechaza (RF-D16).

### E2. Corridas y comparación

- [x] `comparacion` pide los resultados a `resultados`, en lugar de leer la tabla (RF-F22). Va después de D1.
- [x] Migración que baja el tope de réplicas de 200 a 100, y `corridas` rechaza más de 100 (D8, RF-E03). Migración 036; `POST /runs` valida `replicas` (opcional, hasta 100) y el valor no cambia nada más: los lotes con varias réplicas llegan con la app de escritorio (RF-E03 queda «En parte»).
- [x] Al arrancar, el simulador vuelve a encolar las corridas `encolado` de su motor (D19, RF-E19, RNF-C03).
- [x] `corridas` acepta `abm-gpu` solo donde está habilitado (RF-E15). Lo decide `MOTORES_HABILITADOS` (por omisión solo `abm-ref`, el respaldo).
- [x] La web se identifica ante `resultados` como se haya decidido (D20).
  - D34: reenvía el JWT de la sesión del usuario (`backend_web/resultados.py`). Las curvas se piden a `resultados` si hay `SERVICIO_RESULTADOS_URL`; si no responde, la web sigue con PostgreSQL. El punto de arriba, «La corrida muestra su resumen desde `simulation_runs`…», sigue esperando a MongoDB.
- [x] `pareto` calcula la frontera en personas-día, con la vacunación por su factor de día-persona por dosis, y deja los pesos aparte. El factor necesita su lugar en la base, con fuente o marca de supuesto: migración 040 (D3). Hecho el 2026-11-17: `costo` va en personas-día y `costo_pesos` aparte (nulo si falta un precio, con aviso); el factor vive en `intervention_types.person_days_per_unit`, vacío, y se fija con `PUT .../interventions/{iid}/person-days` de `intervenciones`. Sin factor, una comparación con vacunación da 422.

### E2b. Captura solo del CAPTURISTA (D1)

- [x] Quitar al ADMINISTRADOR de `ROLES_ESCRITURA` en `casos`, de `ROLES` en `sincronizacion` y de `ROLES_SUBEN` en `evidencias`. `ROLES_BORRAN` se queda. Hecho el 2026-11-17; en `sincronizacion` solo para enviar: el ADMINISTRADOR sigue consultando cualquier lote.

### E3. Límites de consumo (D31, S2)

- [x] Contador `ratelimit:<usuario>:<ruta>` en Redis, desde `epidemia_comun/limites.py` (RNF-D08).
- [x] Al pasar el límite, el servicio responde 429 con el tiempo de espera (`Retry-After`).
- [x] Prueba de que el límite se cumple y de que se libera al vencer (`comun/tests/test_limites.py`; en contenedores, `test_compose_limites.py`).

### E4. Salud y panel (N3, N4)

- [x] `/health` informa también MongoDB, el bucket y el tiempo de respuesta. Un servicio que no los usa lo dice (RF-K10). Hecho en `epidemia_comun/salud.py` (`no_usa`, `no_configurado`, tiempos; ver `comun/README.md`); listo para conectar cuando D agregue el servicio: falta declarar `dependencias=` / `DEPENDENCIAS` y `MONGO_URL` / `BUCKET_URL` en los servicios que los usen. Verificado con MongoDB y emulador del bucket de la demostración (`infra/docker-compose.fallos.yml`; evidencia en `docs/pruebas/fallos/2026-11-16`); falta conectarlo a los servicios reales del bloque D.
- [x] `estado-servicios` marca MongoDB y el bucket como dependencias caídas (RF-K05). Hecho en `sondeo.py` (causas `mongodb` y `bucket`, con prueba); listo para conectar cuando D agregue el servicio. Verificado con MongoDB y emulador del bucket de la demostración (`infra/docker-compose.fallos.yml`; evidencia en `docs/pruebas/fallos/2026-11-16`); falta conectarlo a los servicios reales del bloque D.
- [x] El panel cuenta los errores de cada servicio (RF-K12, RNF-J05): llave `errors:<servicio>` y columna «Errores (24 h)» de la consola.

### E5. Detrás de nginx (D25)

- [x] Cada servicio funciona detrás de `/<servicio>`: revisar `/docs`, `/openapi.json` y el CORS. `DETRAS_DE_PROXY=1` (ProxyFix); falta probarlo con el nginx real (F2).
- [x] `estado-servicios` responde `https://<dominio>/<servicio>` (RF-K11), con `URL_PUBLICA=https://<dominio>/{servicio}`.

### E6. Verificar

- [x] Cada línea de registro trae la fecha, el servicio, el nivel y el identificador de correlación (RNF-J06). Formato en `epidemia_comun/registro.py`.
- [x] Los contratos de `docs/contratos/` y la colección de Postman coinciden con las rutas nuevas (pruebas de contratos).
- [x] `python -m pytest microservicios` y `python infra/pruebas_integracion.py` pasan (sin `--gpu`: 133 pasan, 1 se salta).
- [ ] Pruebas de interoperabilidad: datos válidos e inválidos, respuestas de error, permisos, versiones y XML contra XSD [Retro: interoperabilidad].
- [ ] Revisar y corregir los ejemplos de contratos que quedaron pendientes en el segundo parcial [Retro: interoperabilidad].

### E7. Completar los servicios de identidad y simulación

[Retro: «Microservicios existentes que deben completarse y fortalecerse»]. Los servicios de E en [«Dueños de los servicios»](#dueños-de-los-servicios). La lista es lo que pide la retroalimentación, no lo que falta: lo que ya se cumpla se marca al revisarlo. Lo que dice «reabierto» o «hoy no existe» ya se revisó.

- [ ] Revisar cada servicio contra su lista de la retroalimentación y marcar aquí lo que ya cumple.

**Identidad**

- [ ] `auth`: MFA para los perfiles críticos (decisión del bloque 0). El bloqueo temporal ya existe (15 min, `backend_web/auth.py`).
- [ ] `sesiones`: control de sesiones concurrentes y solo dispositivos autorizados (RF-A08, reabierto).
- [ ] `usuarios`: institución y región de cada cuenta, y los perfiles nuevos (decisión del bloque 0).
- [ ] `roles`: permisos por recurso, región, institución y operación (decisión del bloque 0).
- [ ] Consultar la bitácora: hoy no existe en ningún servicio. La necesitan la web (`/auditoria`) y el escritorio (historial de un escenario).

**Simulación**

- [ ] `corridas`: prioridades, tiempo estimado y reintentos seguros (RF-E07, RF-E08 y RF-E14, reabiertos).
- [ ] Una corrida interrumpida se recupera sin duplicar resultados, en lugar de cerrarse como fallida (RNF-C03; decisión del bloque 0).
- [ ] `resultados`: intervalos de incertidumbre de las réplicas, con la banda p5–p95 de `series_corridas` (D8, reabierto).
- [ ] `comparacion`: diferencias absolutas y relativas, incertidumbre y análisis contrafactual exploratorio.
- [ ] `pareto`: explica por qué cada alternativa queda dominada o no.
- [ ] Rutas para la calibración y la sensibilidad (con el bloque 0).

### E8. Reglas de negocio y despliegue independiente

[Retro: «Dependencia de reglas de negocio compartidas con el monolito»]. Va con la decisión de dueños (bloque 0).

- [ ] Tabla de dueños: cada regla de negocio con el servicio que la posee.
- [ ] Los servicios dejan de importar `backend_web`: cada regla vive con su dueño. Cada bloque lo hace en sus servicios (D, E y F).
- [ ] `epidemia_comun` queda solo con funciones técnicas. Revisar `sesiones` y `series_corridas`.
- [ ] Contratos de dominio separados de las clases internas.
- [ ] Demostrar que un servicio se construye y se despliega sin tocar a los demás.

### E9. Rutas para la web

- [ ] Una ruta para cada cosa que la web hoy lee o escribe directo, según el inventario de C6. Cada bloque agrega las de sus servicios (D, E y F).

## F. Nube, monitoreo y pruebas de carga

### F1. Compute Engine (N1)

- [ ] Crear la máquina y reservar una IP externa fija (RNF-H02, RNF-H17).
- [ ] Firewall: solo los puertos 80 y 443 abiertos (RNF-D10).
- [ ] Compose de producción: ningún servicio ni base publica su puerto fuera de nginx (RNF-H07, RNF-H18).
- [ ] Desplegar la web, los 29 servicios, PostgreSQL, MongoDB y Redis, con la base de la demostración (RNF-L09). La web usa el rol `epidemia_app` (D18).
- [ ] Pedir desde ya el aumento de cuota de GPU del proyecto, y confirmar qué cuenta de facturación paga la máquina: los cupones no se juntan (D23).
- [ ] Secretos fuera del repositorio y de la imagen, protegidos en GCP (S5, RNF-D03).
- [ ] Solo si sobra tiempo: máquina con GPU para `abm-gpu`, con su costo comparado contra los créditos y anotado en D23. Se enciende solo cuando hay corridas de `abm-gpu` (RNF-B09).

### F2. nginx y HTTPS (D25, D26, S6)

- [ ] nginx en `infra/`, como única entrada, con una ruta por servicio y la web (RNF-H16, RNF-L11).
- [ ] En local, certificado de mkcert.
- [ ] Conseguir el dominio: elegir el proveedor, confirmar que permite Let's Encrypt y quién lo paga (D26).
- [ ] Apuntar el dominio a la IP fija y obtener el certificado de Let's Encrypt con certbot (RNF-D01).
- [ ] Renovación programada del certificado, y HTTP redirige a HTTPS (RNF-D09).
- [ ] Tiempo máximo por petición en nginx, para la prueba del *timeout* (RNF-C10).

### F3. Registros y diagramas

- [ ] Los registros de todos los contenedores llegan a un solo lugar en la nube. Propuesta: Cloud Logging (N6, RF-K08, RNF-J13).
- [ ] Diagrama de distribución en la nube: web, servicios, PostgreSQL, MongoDB, Redis, archivos y monitoreo (N2).

### F4. Locust (A4, A5)

- [ ] Un perfil por tipo de uso: consulta en la web, captura desde la móvil, reportes desde el escritorio y corridas automáticas (RNF-L14).
- [ ] Medir usuarios concurrentes, peticiones por segundo, tiempo medio, p95, p99 y errores (RNF-A01, RNF-A05 a RNF-A08).
- [ ] Encontrar el punto de saturación y medir cuánto tarda en recuperarse (RNF-A14, RNF-A16).
- [ ] Listar los endpoints más lentos.
- [ ] Confirmar o corregir las metas de rendimiento de los requerimientos con lo medido.

### F5. Demostración de fallos (N5)

- [x] Guion y evidencia de qué pasa cuando se detiene un microservicio (RNF-C02). Evidencia: `docs/pruebas/fallos/2026-11-16`.
- [x] Lo mismo con Redis, con MongoDB y con PostgreSQL (RNF-C16). Evidencia: `docs/pruebas/fallos/2026-11-16`. MongoDB, solo `/health` y panel (falta la corrida con resumen, bloque D); con PostgreSQL las lecturas dan 503 `SERVICIO_NO_DISPONIBLE` (antes 500; corregido en `fabrica.py` y vuelto a demostrar el 2026-11-16).
- [x] Lo mismo con el bucket, y con una petición que excede el tiempo máximo (RNF-C18). Evidencia: `docs/pruebas/fallos/2026-11-16`. Bucket, solo `/health` y panel (falta la subida, bloque D).
- [ ] Fallo de worker: el simulador se detiene después de guardar los resultados y antes de confirmar la corrida, y no quedan corridas duplicadas ni resultados perdidos [Retro: fallo de worker]. Con D y E.

### F6. Documentos

- [ ] Guía de despliegue en GCP y `INSTALACION.md` al día, con MongoDB, el emulador y nginx.
- [x] Resultados de Locust y de las pruebas de fallos en `docs/` (`docs/pruebas/carga` y `docs/pruebas/fallos/2026-11-16`).

### F7. Completar los servicios de vigilancia, analítica y plataforma

[Retro: «Microservicios existentes que deben completarse y fortalecerse»]. Los servicios de F en [«Dueños de los servicios»](#dueños-de-los-servicios). La lista es lo que pide la retroalimentación, no lo que falta: lo que ya se cumpla se marca al revisarlo. Lo que dice «reabierto» o «hoy no existe» ya se revisó.

- [ ] Revisar cada servicio contra su lista de la retroalimentación y marcar aquí lo que ya cumple.

**Vigilancia**

- [ ] `casos`: actualizar, dar seguimiento y rechazar, con historial, duplicados y control de conflictos (RF-C11 y RF-C15, reabiertos; decisión del bloque 0).
- [ ] Formularios por enfermedad, con versiones (para B4).
- [ ] `sincronizacion`: conflictos entre lo capturado sin conexión y lo que cambió otro profesional.

**Analítica**

- [ ] `indicadores`: cada indicador con su numerador, su denominador y su periodo; capacidad utilizada, con su fuente (RF-G07, reabierto).
- [ ] `series`: filtrado, paginación y agregaciones por enfermedad, periodo, región y grupo.
- [ ] `zonas`: mapas de calor y agrupaciones territoriales.

**Plataforma**

- [ ] `notificaciones`: avisos de campañas, de datos incompletos y de errores operativos.
- [ ] `estado-servicios`: capacidad de procesamiento (la cola de cada motor).

---

## Entrega final · Todos

No es para terminar módulos: es para corregir, probar y documentar.

- [ ] Cada bloque corrige los defectos que salgan del ensayo de los tres procesos.
- [ ] Cada bloque repite sus pruebas después de integrar (regresión).
- [ ] Cada bloque revisa que sus requerimientos estén en «Hecho» o tengan anotado por qué no.
- [ ] Cada bloque aporta su parte del expediente técnico y del video.

## Fuera de alcance

- Lo que cada módulo lista en «Fuera de alcance» de [`requerimentos/`](../../requerimentos/README.md), salvo lo que [la retroalimentación reabre](#lo-que-la-retroalimentación-reabre).
- Lo que la retroalimentación llama propuesta o recomendación:
  - los servicios 27 a 38, de `calidad-datos` a `gobierno-datos`;
  - Kotlin con Jetpack Compose y MVVM en Android (de todos modos ya se usa);
  - la demostración con un escenario ficticio de Nuevo León (de todos modos es el de la demostración).
- Las pruebas de usabilidad, incluida la de cinco participantes por perfil y la «prueba de usuarios» de la aceptación (respuesta del equipo, 2026-11-18).
- Las alertas configurables por perfil y el aviso cuando un servicio cae (RF-K06).
- El progreso del escritorio por WebSocket o SSE: la retroalimentación dice «podrá». La app consulta el estado de la corrida.
- La IA predictiva, la visualización 3D y un modelo económico sofisticado.
- El XML de intercambio en el bucket (D32) y los lotes de `sincronizacion` en MongoDB, salvo que sobre tiempo.
