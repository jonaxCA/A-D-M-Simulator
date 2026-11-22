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
- [x] ¿Quién consigue el dominio y con qué proveedor? (D26). **Frena a F.** Delegada al bloque F (F2). Gratuito: `<ip-con-guiones>.sslip.io`, sin proveedor ni pago; respaldo, DuckDNS (D26, 2026-11-20).
- [x] ¿Qué archivo recibe la web? (D-5, RF-G16). **Frena a C.** El reporte de una comparación (D35).
- [x] ¿Cómo entra la vacunación a la frontera de Pareto? (D3). Como fracción de día-persona por dosis (D3).
- [x] ¿Se retiran los roles `app_*` de la migración 009, y qué rol de base usa el monolito? (D18). No; la web sigue con `epidemia_app` (D18).
- [ ] Con el profesor: confirmar el volumen de D29 y si hay créditos para la GPU (brechas §8). **Frena a D y a F.** Créditos: sí (D23). Falta el volumen.

### Decisiones nuevas por la retroalimentación

Cada una reemplaza o amplía una decisión vigente (ver [«Lo que la retroalimentación reabre»](#lo-que-la-retroalimentación-reabre)) y se registra en `decisiones/` con número nuevo.

- [x] La web consume los servicios: en qué orden pasa cada módulo y qué ve el usuario cuando un servicio no responde. Reemplaza D20 y D33. **Frena a C y a E.** Opción B, sin respaldo en la base; orden de la demostración integrada (D36).
- [x] Dueño de cada regla de negocio, y cómo dejan los servicios de importar `backend_web`. Cambia las reglas 2 y 14 de `microservicios/AGENTS.md`. **Frena a E.** El dueño de la tabla es el dueño de la regla; los demás la piden por HTTP (D37).
- [ ] Instituciones, regiones y los perfiles INVESTIGADOR y AUTORIDAD SANITARIA, con los permisos por recurso, región, institución y operación. Amplía D1. **Frena a E, B y C.** El bloque E propuso D42 y D43 (integradas el 2026-11-21): falta que el líder las valide. Pendientes aun validadas: los perfiles nuevos no están en los candados de los servicios, y el alcance no filtra datos todavía.
- [ ] Editar y rechazar casos: qué se edita, quién lo hace y cómo se detecta un conflicto. Reemplaza lo de D32 sobre editar casos. **Frena a E y a B.**
- [ ] Calibración: método, función de pérdida, métricas de ajuste, datos y dónde corre. Reemplaza D24. **Frena a A.**
- [x] Corridas interrumpidas: reencolarlas en lugar de cerrarlas como fallidas, y qué pasa con su serie en MongoDB (RNF-C03). **Frena a E y a D.** Se reencolan hasta 3 intentos con la misma semilla; solo cuentan las series de corridas completadas; migración 045 (D38).
- [ ] MFA: qué perfiles son críticos y con qué segundo factor. **Frena a E.** El bloque E propuso D40 (TOTP para ADMINISTRADOR, EPIDEMIOLOGO y AUTORIDAD_SANITARIA, apagado por omisión): falta que el líder la valide, y que la web, el escritorio y la móvil tengan el segundo paso antes de prenderlo.
- [ ] Qué son «campañas» y «seguimiento de intervenciones» en la web, y qué datos llevan. **Frena a C y a E.**
- [ ] Qué agrupa un proyecto de investigación del escritorio y dónde vive. **Frena a A y a E.**
- [ ] Reservar los números de migración para lo nuevo: instituciones y perfiles, casos, corridas, proyectos y calibración.

### Validación científica

[Retro: «Hace falta validación científica»]. Lo que no se valide se presenta como exploratorio.

- [x] Ficha de cada modelo (`seir-ref`, `abm-ref` y `abm-gpu`): formulación matemática, población representada, variables, supuestos, fuentes de parámetros, límites de aplicación, versión del algoritmo, escenarios de prueba y resultados de validación. Se amplía [`ficha_simulador.md`](../../arquitectura/ficha_simulador.md). §16 (una columna por modelo) y §17 (categoría de D39); §13 a §15 con la validación.
- [ ] Investigar una fuente de datos observados para validar y calibrar: qué serie, de qué periodo y con qué licencia. Con D (D6).
- [x] Validación contra resultados esperados: soluciones conocidas (por ejemplo, el tamaño final de un brote SEIR), casos límite y `abm-ref` contra `seir-ref` (ya medido en la ficha). §13 de la ficha, `python -m procesamiento.mediciones esperados` y `test_validacion_cientifica.py`. Encontró que el R0 efectivo es ~10 % mayor que el nominal (§11): corregirlo queda como decisión del equipo.
- [ ] Validación contra los datos observados.
- [x] Análisis de sensibilidad: variar cada parámetro y comprobar que el modelo responde como se espera (RF-F12, reabierto). El escritorio lo muestra (A4). §14 de la ficha (un factor a la vez, ±20 %) y `python -m procesamiento.mediciones sensibilidad`; las direcciones las revisa `test_validacion_cientifica.py`. Mostrarlo en el escritorio sigue en A4.
- [ ] Calibración: el algoritmo en `procesamiento/`, con su función de pérdida, sus métricas de ajuste y sus versiones. El escritorio la muestra (A4) y un servicio la expone (E7).
- [x] Reproducibilidad: la corrida determinista repetida, y la estocástica con la misma semilla y versión, dan lo mismo. Las pruebas existen (`test_contrato_motor.py`); falta la evidencia para la entrega. Evidencia en `docs/pruebas/validacion/2026-11-19` y §15 de la ficha; `seir-ref` y `abm-ref` (sin GPU aquí, `abm-gpu` queda pendiente de evidencia).
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
- [x] Toda la suite en una sola ejecución, sobre una base creada desde cero, con un solo resultado consolidado. Nada de juntar pruebas de distintas versiones [Retro: pruebas]. `docs/pruebas/suite/2026-11-19`: 2281 pasan, 2 fallan (ya existían: la semilla no trae un epidemiólogo inactivo y una de `frontend_desktop`), 182 se saltan. Repetirla cuando se integren los PR.
- [ ] Cada integrante ensaya ejecutar, explicar y modificar lo que le tocó, para la defensa técnica [Retro: participación].

---

# Salón 1 · Clientes

## A. App de escritorio · `frontend_desktop/`

Antes de empezar: `frontend_desktop/AGENTS.md`. La app solo habla XML.

La [evidencia del bloque A](../../pruebas/bloque_a_escritorio.md) incluye los flujos, los
comandos de prueba y los pasos de defensa. Lo marcado se implementó y se verificó en el
escritorio, y se integró en `feat/tercer-parcial` el 2026-11-20 (PR #173).

### A1. Interfaz más intuitiva y usable

**Pendiente de definir** (bloque 0). Las casillas de implementación se escriben cuando exista la definición. La meta [Retro: usuarios finales]: un epidemiólogo o un analista entiende, configura, ejecuta y compara escenarios sin saber programar, y la app le muestra el progreso, errores que se entienden, resultados visuales, supuestos y limitaciones.

- [ ] Proponer los cambios, pantalla por pantalla, y acordarlos con el líder.
- [ ] **Parcial.** Implementar los cambios acordados. La rama ordena la comparación por pestañas, evita resultados tardíos al cambiar de versión y agrega accesos directos a la ficha, el seguimiento y los indicadores.
- [x] Actualizar el [manual](../../manuales/manual_usuario_escritorio.md) y las capturas de Escenarios, Simulaciones, Comparación, Diferencias e Indicadores municipales con datos de demostración.

Propuesta para revisar en el PR #173: en Escenarios se distingue el fondo del editor y
se ensancha el selector de intervención. En Simulaciones se mantiene la cola para monitorear
y cancelar corridas en espera. El diálogo de envío abre en cero, permite seguir usando la
ventana e indica qué pasó al detenerlo. En Comparación se distinguen las fichas de escenarios
y el PDF pone las gráficas y el aviso de incertidumbre antes de la tabla.

### A2. Funciones que faltan

- [x] Avisar cuando las bandas p5–p95 de dos escenarios se enciman (A3, RF-H22, RF-F23).
- [x] Mostrar la escala que ya responde `resultados`: habitantes por agente (D6, RF-H21, RF-F20).
- [ ] **Bloqueado (E y F).** Ofrecer `abm-gpu` al lanzar solo si `corridas` anuncia que el despliegue lo acepta (D23, RF-H20, RF-E15).
- [ ] **Bloqueado (D y F).** Subir el reporte al bucket y mostrar su URL firmada (D30, RF-F17). Faltan la ruta de reportes y el almacenamiento en el despliegue.
- [x] Leer `exp` del token sin verificar la firma y renovarlo antes de que venza (D35, RF-H23).
- [x] La comparación dice «Personas-día» donde hoy dice «Costo», y muestra y exporta `costo_pesos` aparte, como «sin dato» cuando es nulo (D3, `ui/comparacion.py` y `exportar.py`). Desde el 2026-11-17 `pareto` ya manda personas-día en `costo`: hasta este cambio, la pantalla las rotula como costo.

### A3. Verificar

- [x] Sin red, con rechazo o sesión vencida, la app explica el problema (RF-H24, RNF-E06). Evidencia en `test_api.py` y `test_mensajes_ui.py`.
- [x] Búsqueda, filtros, tabla, XSD y exportación verificados localmente con ejemplos XML y PDF. Se conserva la evidencia previa de roles ANALISTA, ADMINISTRADOR y EPIDEMIOLOGO con respuestas controladas.
- [ ] **Parcial (F).** Verificar el escritorio detrás de nginx y contra el dominio con HTTPS (D25, D26). nginx en local ya está (F2, `infra/docker-compose.nginx.yml`): se puede probar con el directorio en `https://localhost`. El dominio sigue esperando a F.
- [x] `python -m pytest frontend_desktop` pasó la suite completa. Ver [reproducción y resultados](../../pruebas/bloque_a_escritorio.md).

### A4. Módulos que pide la retroalimentación

[Retro: «Aplicación de escritorio»]. Todos son obligatorios. Algunos ya existen en parte (el editor, la comparación y Pareto): la primera casilla es revisarlos.

- [x] Contrastar esta lista con el código y las pruebas de cada pantalla.
- [ ] **Bloqueado (0 y D).** Proyectos. El escritorio ya selecciona región, enfermedad, horizonte y motor de escenarios y corridas. Faltan la definición, permisos y persistencia del proyecto (D7).
- [ ] **Parcial (D).** Gestión de datos. Se consultan las series guardadas de corridas y las series de casos municipales de `zonas`. Faltan importación autorizada, verificación de calidad y versiones de conjuntos (D6).
- [ ] **Parcial (D y 0).** Configuración del modelo. Se elige el motor al lanzar, se ajustan población, infecciones iniciales y horizonte. `parametros/status` aporta definiciones, unidades, rangos, fuentes y estado. Falta el ajuste de parámetros por versión del escenario.
- [x] Editor de escenarios. Alta, duplicado, nuevas versiones, historial y edición del borrador por XML. La prueba del bloque A verifica que una respuesta tardía no reemplaza la versión que pidió el usuario.
- [x] Configuración de intervenciones. Intervalo y duración inclusiva, cobertura, cumplimiento, parámetros por tipo y consulta del costo unitario con su procedencia. Cambiar el costo del catálogo es una operación compartida de administración.
- [ ] **Bloqueado (0 y E).** Calibración. Falta la decisión sobre el método y el servicio de calibración con series y métricas de ajuste.
- [ ] **Parcial (0 y E).** Validación. El escritorio muestra errores y advertencias del escenario y el motivo de la categoría científica devuelta por `resultados`. Faltan las rutas del estudio de sensibilidad y la validación científica.
- [ ] **Parcial (E).** Ejecución asíncrona. La app encola, monitorea, sigue la nueva corrida y cancela en espera por versión y motor. Falta demostrar la recuperación del trabajador de punta a punta (D38).
- [x] Comparación descriptiva. Mediana, p5–p95, diferencias absolutas y relativas contra referencia, semillas completas y curvas alineadas por día. Se avisa si cambian motor, versión u horizonte.
- [x] Análisis económico exploratorio y Pareto (D3/D8). Se ven supuestos y diferencias de costos en personas-día y pesos. La frontera sobre medianas muestra dominancia y alternativas fuera por falta de datos.
- [ ] **Parcial (D y F).** Mapa regional. `zonas/map` aporta coordenadas, casos, incidencia, semáforo y serie por municipio. El escritorio dibuja marcadores sin polígonos; falta geometría oficial si se exigen límites municipales.
- [x] Reportes. El comparativo exporta gráficas, metodología, diferencias, advertencias, costos e identificadores de origen. La ficha PDF por réplica exporta serie, indicadores, parámetros con procedencia, versión y limitaciones devueltos por `resultados`.
- [ ] **Parcial (D y E).** Reproducibilidad. Misma versión del escenario, semilla y motor al reencolar; consulta de huella y resumen, acceso al equivalente y seguimiento. Faltan ID/versionado del conjunto y un contrato para repetir con configuración histórica.
- [ ] **Parcial (D y E).** Auditoría. Versiones muestra autor, fechas y revisor del servidor cuando existen. Falta la consulta de eventos por operación y modificación (D7/E7).
- [x] Seleccionar una curva por leyenda o tabla, escoger una réplica y abrir su ficha, sus supuestos y su versión del escenario. La repetición histórica sigue en el requisito de reproducibilidad.
- [x] Trazabilidad gráfica. `corridas` aporta versión del motor y horizonte; `comparacion` y `resultados`, las series e indicadores; `pareto`, los costos. Los ejes muestran unidades. Si faltan datos de procedencia, se muestran tablas y se omite la gráfica afectada.

## B. App Android · `frontend_movil/`

La app solo habla JSON.

### B1. Funciones que faltan

- [x] Indicador de conexión fijo, visible en todas las pantallas (C3, RF-I20, RNF-E11). `ui/navegacion/IndicadorConexion.kt`.
- [x] Menú por rol: un rol distinto del CAPTURISTA no ve la captura (C8, RF-I19). Los roles del login quedan con la sesión (`InicioViewModelTest`).
- [ ] Las fotos se suben y se bajan con la `evidencias` del bucket (D30, RF-C03). Espera a D.
- [ ] Probar que el aviso por lote no se repite cuando la app reintenta el mismo lote (D32, RF-C19). Espera a E.
- [x] Mostrar los tipos de aviso de la migración 037 (`NEW_CASES`, `SCENARIO_SUBMITTED` y `SCENARIO_REJECTED`) en `Formato.kt` (D32).

### B2. Verificar

- [ ] Sin red, con un rechazo del servidor y con la sesión vencida, la app explica qué pasó sin cerrarse (RF-I22, RNF-E06).
- [x] Los casos sin enviar se quedan al cerrar sesión y se mandan cuando esa cuenta vuelve a entrar (D19, RF-I21). `SincronizadorTest`.
- [ ] La app pasa la lista de la rúbrica para Android: perfil, consulta, registro, actualización (dosis y avisos, D32) y borrado local de credenciales.
- [ ] La app funciona contra el dominio real con su certificado, de preferencia también en un Android 7.0 (D26). Espera a F.
- [ ] Las pruebas de `frontend_movil` pasan.

### B3. Entregables

- [x] Manual de usuario de la app móvil en `docs/manuales/` (RNF-E08). `manual_usuario_movil.md`, sin capturas todavía.
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

- [x] Inventario: cada pantalla de la web y cada consulta de `backend_web` que usa, con el servicio que debe atenderla. Lo que no tenga servicio se le pide a su dueño (E9). En [`inventario_web_servicios.md`](../../arquitectura/inventario_web_servicios.md): 20 de 32 pantallas ya tienen su servicio; faltan 11 rutas (4 de D, 4 de E y 3 de F).
- [x] Iniciar y cerrar sesión con `auth` y `sesiones`, sin leer Redis. `frontend_web/app/sesion_servicios.py` y el cliente `backend_web/servicios.py`: login con el captcha de `auth`, sesión revisada por `sesiones` en cada petición (renueva el access con el refresh), logout en `sesiones`. Sin `sesiones` la web no deja pasar (D36). Se retiró `sesion_redis.py`.
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

- [x] Generar el conjunto de alto volumen: unas 10,000 corridas de 180 días. La cifra se confirma con el profesor (RNF-A17).
- [x] Medir el tiempo de inserción y el de consulta, con y sin índice.
- [x] Medir la consulta de resultados con y sin la caché de Redis (RNF-A09).
- [x] Medir CPU, memoria y disco durante la carga.
- [x] Escribir los resultados en `docs/`, con la forma de repetirlos. `docs/pruebas/volumen/2026-11-18` y `datos/scripts/volumen_mongo.py` (2026-11-18); la cifra sigue por confirmar con el profesor.

### D4. Documentos

- [ ] Diseño de MongoDB y de los buckets en la arquitectura v3, con qué información va a PostgreSQL y cuál a MongoDB [Retro: MongoDB]. La parte de MongoDB está hecha (§6 y §9 de `arquitectura_v3.md`: criterio, tabla por dato, cómo se relacionan, consistencia y volumen medido); falta la de los buckets, que espera a D2.
- [ ] Llenar la retención de cada dato en `matrices_v3.md`: hoy hay 48 «Por definir» (RNF-K07). Hechas las de MongoDB, `simulation_runs` y `simulation_results` (2026-11-18).
- [ ] Actualizar `docs/arquitectura/microservicios.md` con lo que cada servicio escribe ahora.

### D5. MongoDB después de D1

[Retro: «MongoDB deberá incorporar referencias estables…» y «Fallo de worker»].

- [x] Cada documento de `series_corridas` trae `scenario_id`, además de `run_id`, `scenario_version_id` y la versión del motor. Hecho en `feat/bloque-D` (2026-11-18, `2ceadf8`); vale al integrarse el PR del bloque D.
- [x] La serie se guarda antes de confirmar la corrida: si el proceso muere entre los dos pasos, la corrida no queda completada sin curvas. Hecho en `feat/bloque-D` (2026-11-18, `2ceadf8`); vale al integrarse el PR del bloque D.
- [x] La serie de una corrida que el arranque cierra como fallida no se queda en MongoDB, o `banda()` la ignora. Va con la decisión de corridas interrumpidas (0). Las dos: el arranque borra la serie de las que cierra, y `banda(..., run_ids=)` cuenta solo las corridas que le pasen como completadas (D38).
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

- [x] Cada servicio funciona detrás de `/<servicio>`: revisar `/docs`, `/openapi.json` y el CORS. `DETRAS_DE_PROXY=1` (ProxyFix). Probado con nginx el 2026-11-19 (`test_compose_nginx.py`); hizo falta que waitress también confíe en nginx (`epidemia_comun/servir.py`), porque borraba `X-Forwarded-For`, `-Proto` y `-Host` y el límite por IP contaba la de nginx.
- [x] `estado-servicios` responde `https://<dominio>/<servicio>` (RF-K11), con `URL_PUBLICA=https://<dominio>/{servicio}`.

### E6. Verificar

- [x] Cada línea de registro trae la fecha, el servicio, el nivel y el identificador de correlación (RNF-J06). Formato en `epidemia_comun/registro.py`.
- [x] Los contratos de `docs/contratos/` y la colección de Postman coinciden con las rutas nuevas (pruebas de contratos).
- [x] `python -m pytest microservicios` y `python infra/pruebas_integracion.py` pasan (sin `--gpu`: 133 pasan, 1 se salta).
- [x] Pruebas de interoperabilidad: datos válidos e inválidos, respuestas de error, permisos, versiones y XML contra XSD [Retro: interoperabilidad]. `microservicios/comun/tests/test_interoperabilidad.py` recorre las rutas de todos los contratos: 401 en XML (contra `problem.xsd`) y en JSON, `/api/v2` 404, formato desconocido 400 y cuerpos inválidos sin 500 ni traza (332 casos). Encontró que un `?format` desconocido no se rechazaba antes de trabajar; se corrigió en `fabrica.py`. Datos válidos e inválidos por ruta y XML contra XSD: las pruebas de cada servicio y `test_xsd.py`.
- [x] Revisar y corregir los ejemplos de contratos que quedaron pendientes en el segundo parcial [Retro: interoperabilidad]. Los cuatro servicios de identidad ya tienen `ejemplos/` (un JSON y un XML por ruta, iguales al contrato) y entran en `test_contratos_analitica.py`; el XML del captcha de `auth` no correspondía a su JSON y se corrigió. Revisión de todos los contratos: cada XML de ejemplo es el que `a_xml` genera de su JSON.

### E7. Completar los servicios de identidad y simulación

[Retro: «Microservicios existentes que deben completarse y fortalecerse»]. Los servicios de E en [«Dueños de los servicios»](#dueños-de-los-servicios). La lista es lo que pide la retroalimentación, no lo que falta: lo que ya se cumpla se marca al revisarlo. Lo que dice «reabierto» o «hoy no existe» ya se revisó.

- [x] Revisar cada servicio contra su lista de la retroalimentación y marcar aquí lo que ya cumple. Revisado el 2026-11-20 contra `RETROALIMENTACION_SEGUNDO_PARCIAL.txt`, servicio por servicio. `auth`: JWT, renovación, revocación, intentos y bloqueo ya estaban; se agregó MFA (D40). `sesiones`: Redis, cierre remoto, expiración y tokens revocados ya estaban; se agregaron concurrentes y dispositivos (D41). `usuarios`: altas y bajas ya estaban; se agregaron institución, región y perfiles (D42). `roles`: roles y auditoría de cambios ya estaban; se agregaron alcance (D43) y la bitácora. `corridas`: cola, cancelación, progreso, estados e idempotencia ya estaban; se agregaron prioridad, estimación y reintento (D44). `simulador`: SEIR, semillas, estocástico y recuperación (D38) ya estaban; nada nuevo pedido. `resultados`: se agregó la banda p5-p95. `comparacion`: se agregaron diferencias, incertidumbre y contrafactual. `pareto`: se agregó la explicación, la sensibilidad y el estado de calibración (D46). Evidencia: [`docs/pruebas/bloque_e/2026-11-20/`](../../pruebas/bloque_e/2026-11-20/LEEME.md).

**Identidad**

- [x] `auth`: MFA para los perfiles críticos (decisión del bloque 0). TOTP y códigos de respaldo en `microservicios/auth/mfa.py`, migración 051, D40. Decisión tomada por el orquestador, pendiente de validación del líder. Salvedad: el MFA arranca apagado (`MFA_PERFILES` vacía) hasta que los clientes (web, escritorio, Android) implementen el flujo de segundo factor; se probó encendido a mano con ADMINISTRADOR y EPIDEMIOLOGO.  El bloqueo temporal ya existe (15 min, `backend_web/auth.py`).
- [x] `sesiones`: control de sesiones concurrentes y solo dispositivos autorizados (RF-A08, reabierto). Tope de sesiones y lista de dispositivos en `microservicios/sesiones/almacen.py` y `dispositivos.py`, migración 050, D41. Decisión tomada por el orquestador, pendiente de validación del líder. Salvedad: el control de dispositivos autorizados viene apagado por omisión hasta que los clientes envíen `dispositivo_id`.
- [x] `usuarios`: institución y región de cada cuenta, y los perfiles nuevos (decisión del bloque 0). Migración 052, D42. Decisión tomada por el orquestador, pendiente de validación del líder.
- [x] `roles`: permisos por recurso, región, institución y operación (decisión del bloque 0). Alcance por región en `microservicios/roles/rutas.py` y cliente `epidemia_comun/alcance.py`, migración 053, D43. Decisión tomada por el orquestador, pendiente de validación del líder. Salvedad: el alcance por institución no se aplica a los datos de E porque estos no traen institución (D43); solo se aplica el de región.
- [x] Consultar la bitácora. La nota de que «hoy no existe» estaba desactualizada: `roles` ya la tenía (`/api/v1/audit`) y se extendió con resumen e historial de una entidad con alcance por región (migraciones 046, 053 y 055, D43). Probada en vivo: `GET /api/v1/audit?entity_id=130`.

**Simulación**

- [x] `corridas`: prioridades, tiempo estimado y reintentos seguros (RF-E07, RF-E08 y RF-E14, reabiertos). Prioridad, posición en la cola, estimación y `POST /runs/{id}/retry` en `microservicios/corridas/`, migración 054, D44. Decisión tomada por el orquestador, pendiente de validación del líder. Salvedad: el reintento es solo manual; no hay reintento automático de corridas fallidas.
- [x] Una corrida interrumpida se recupera sin duplicar resultados, en lugar de cerrarse como fallida (RNF-C03; decisión del bloque 0). D38: el simulador la reencola con la misma semilla, hasta 3 intentos (migración 045, `attempts`); sin intentos o con otra versión de motor se cierra como `fallido`.
- [x] `resultados`: intervalos de incertidumbre de las réplicas, con la banda p5–p95 de `series_corridas` (D8, reabierto). `GET /api/v1/runs/{id}/band` en `microservicios/resultados/`. Salvedad: `replicas` cuenta las corridas completadas de la versión, no las que tienen series en MongoDB.
- [x] `comparacion`: diferencias absolutas y relativas, incertidumbre y análisis contrafactual exploratorio. En `microservicios/comparacion/rutas.py`; contrato y ejemplos actualizados. Es exploratorio y no recomienda un escenario (regla 10).
- [x] `pareto`: explica por qué cada alternativa queda dominada o no. Campo `explicacion` por fila en `microservicios/pareto/dominio.py`. Probado en vivo.
- [x] Rutas para la calibración y la sensibilidad (con el bloque 0). En `pareto`, D46. Decisión tomada por el orquestador, pendiente de validación del líder. Salvedad: la calibración solo informa su estado (fuera de alcance, D24 y D46); la sensibilidad es exploratoria.

### E8. Reglas de negocio y despliegue independiente

[Retro: «Dependencia de reglas de negocio compartidas con el monolito»]. Va con la decisión de dueños (bloque 0).

- [x] Tabla de dueños: cada regla de negocio con el servicio que la posee. [`docs/arquitectura/duenos_de_reglas.md`](../../arquitectura/duenos_de_reglas.md) (D37). Las copias de `get_run`, `_sincroniza_lote` y la selección de corridas quedan documentadas ahí.
- [ ] Los servicios dejan de importar `backend_web`: cada regla vive con su dueño. Cada bloque lo hace en sus servicios (D, E y F). Parte de E hecha: ningún servicio de E importa `backend_web` (`test_sin_backend_web.py`, `test_simulacion_sin_backend_web.py`). Sigue abierta porque `series`, `notificaciones`, `regiones`, `dispositivos` e `intervenciones` (D y F) todavía lo importan, y `epidemia_comun/ambito.py` (F) y `validaciones.py` (D) esperan a su dueño.
- [ ] `epidemia_comun` queda solo con funciones técnicas. Revisar `sesiones` y `series_corridas`. Parte de E hecha: las curvas de corridas pasaron a `simulador/serie.py` y `resultados/serie.py`, y abrir sesiones a `sesiones` (auth la llama por HTTP). Sigue abierta: `ambito.py` y `validaciones.py` pendientes de F y D, y quedan copias documentadas (`get_run`, `_sincroniza_lote`, entrada del motor).
- [x] Contratos de dominio separados de las clases internas. Las respuestas se arman con los campos del contrato (`epidemia_comun.contratos.proyectar`); ver «Contratos de dominio» en `duenos_de_reglas.md`. Aplicado en los servicios de E; D y F por su bloque.
- [x] Demostrar que un servicio se construye y se despliega sin tocar a los demás. `usuarios` y `corridas` se reconstruyeron con `--no-deps` y los otros 32 contenedores no cambiaron; las imágenes no traen `backend_web`. Evidencia: [`docs/pruebas/despliegue_independiente/2026-11-20/`](../../pruebas/despliegue_independiente/2026-11-20/LEEME.md).

### E9. Rutas para la web

- [x] Una ruta para cada cosa que la web hoy lee o escribe directo, según el inventario de C6. Cada bloque agrega las de sus servicios (D, E y F). Las 11 del inventario: E-1 a E-4 en `feat/bloque-E`, D-1 a D-4 en `feat/bloque-D` (#166) y F-1 a F-3 en `feat/bloque-F` (#171). Las de F todavía sin pruebas propias.

## F. Nube, monitoreo y pruebas de carga

### F1. Compute Engine (N1)

- [x] Crear la máquina y reservar una IP externa fija (RNF-H02, RNF-H17). e2-highmem-2 (2 vCPU, 16 GB), Debian 13, disco de 50 GB, us-central1-c, IP estática 35.222.19.202 (2026-11-20). Con todo levantado usa unos 2.6 GB.
- [x] Firewall: solo los puertos 80 y 443 abiertos (RNF-D10). Se borraron `default-allow-ssh` y `default-allow-rdp`; SSH solo entra por IAP (`permitir-ssh-iap`, 35.235.240.0/20). Comprobado desde fuera: 22, 3389, los de los servicios y los de las bases, cerrados (2026-11-20).
- [x] Compose de producción: ningún servicio ni base publica su puerto fuera de nginx (RNF-H07, RNF-H18). Compose principal + `docker-compose.nginx.yml` + `docker-compose.letsencrypt.yml`. Las bases siguen solo en el 127.0.0.1 de la máquina, para el túnel del simulador de GPU (D23); desde internet no se alcanzan.
- [x] Desplegar la web, los 29 servicios, PostgreSQL, MongoDB y Redis, con la base de la demostración (RNF-L09). La web usa el rol `epidemia_app` (D18). Todo corre en la máquina y responde por HTTPS (2026-11-20). La web va en su contenedor (`frontend_web/Dockerfile`, perfil `web`), llama a los servicios por la red interna y les pasa la IP de quien la usa, para el límite por IP (D31). Ojo: los casos de la semilla van del 2026-07-20 al 2026-09-03, así que el tablero público, que cuenta los últimos 7 y 30 días, sale en ceros.
- [x] ~~Pedir desde ya el aumento de cuota de GPU del proyecto, y confirmar qué cuenta de facturación paga la máquina: los cupones no se juntan (D23).~~ Ya no hace falta: la GPU es la de una PC (D23, 2026-11-20).
- [ ] Secretos fuera del repositorio y de la imagen, protegidos en GCP (S5, RNF-D03). Hoy, `infra/.env` generado en la máquina con `genera_env.py` (permisos 600, nunca impreso). Falta decidir si pasan a Secret Manager.
- [ ] ~~Solo si sobra tiempo: máquina con GPU para `abm-gpu`, con su costo comparado contra los créditos y anotado en D23. Se enciende solo cuando hay corridas de `abm-gpu` (RNF-B09).~~ No alcanzaron los créditos: el simulador de `abm-gpu` corre en una PC con GPU, conectado a la máquina por un túnel SSH por IAP (`infra/docker-compose.gpu-remoto.yml`, `infra/tunel_gpu.py`; D23). Probado en local con `python infra/pruebas_integracion.py --gpu-remoto` (2026-11-20); falta con la máquina real.

### F2. nginx y HTTPS (D25, D26, S6)

- [x] nginx en `infra/`, como única entrada, con una ruta por servicio y la web (RNF-H16, RNF-L11). En local: `infra/docker-compose.nginx.yml` e `infra/nginx/` (2026-11-19); ningún servicio publica su puerto. Se prueba con `python infra/pruebas_integracion.py --nginx`.
- [x] En local, certificado de mkcert. El script está (`infra/nginx/certificado_local.py`): usa mkcert si está instalado y, si no, genera uno autofirmado con OpenSSL. Falta que cada quien instale mkcert y corra `mkcert -install` en su máquina. Queda como paso de cada integrante, documentado en `INSTALACION.md` §6 (2026-11-21).
- [x] Conseguir el dominio: elegir el proveedor, confirmar que permite Let's Encrypt y quién lo paga (D26). `<ip-con-guiones>.sslip.io`, gratuito y compatible con Let's Encrypt; si se agota su límite semanal, DuckDNS (2026-11-20).
- [x] Apuntar el dominio a la IP fija y obtener el certificado de Let's Encrypt con certbot (RNF-D01). Dominio del equipo, `https://epidemos.app` (registro A en name.com, 2026-11-21); certificado emitido el 2026-11-21 y vigente hasta el 2027-02-20, con cadena hasta ISRG Root X1, la raíz que trae la app móvil. Antes, del 2026-11-20 al 21, `https://35-222-19-202.sslip.io`.
- [x] Renovación programada del certificado, y HTTP redirige a HTTPS (RNF-D09). La redirección ya está (`test_http_redirige_a_https`). La renovación está en `infra/docker-compose.letsencrypt.yml`: certbot cada 12 h y nginx recarga cada 6 h. En la máquina, los dos ciclos corren y `certbot renew --dry-run` salió bien (2026-11-20).
- [x] Tiempo máximo por petición en nginx, para la prueba del *timeout* (RNF-C10). `NGINX_TIEMPO_MAXIMO`, 30 s (8 s en las pruebas): un servicio congelado responde 504 (`test_nginx_corta_una_peticion_colgada`).

### F3. Registros y diagramas

- [x] Los registros de todos los contenedores llegan a un solo lugar en la nube (N6, RF-K08, RNF-J13): Cloud Logging, con el driver `gcplogs` de Docker (`infra/docker-compose.cloud-logging.yml`). Comprobado en la máquina el 2026-11-20: llegan los de los servicios, la web, nginx y las bases, al registro `gcplogs-docker-driver`.
- [x] Diagrama de distribución en la nube: web, servicios, PostgreSQL, MongoDB, Redis, archivos y monitoreo (N2). En la arquitectura v3, §8, con lo desplegado (2026-11-21): dominio y DNS, Let's Encrypt, firewall e IAP, la VM con sus 37 contenedores y volúmenes, Cloud Logging, la PC con GPU por el túnel y Cloud Storage pendiente (D-3).

### F4. Locust (A4, A5)

- [x] Un perfil por tipo de uso: consulta en la web, captura desde la móvil, reportes desde el escritorio y corridas automáticas (RNF-L14). `pruebas_carga/perfiles.py` (2026-11-21): cinco perfiles, con el panel de administración que pide RNF-A16 y las fotos de la móvil. `escalones.py` da la forma de carga y `analiza.py` el resumen. Probados contra el compose de pruebas. Guía: `pruebas_carga/README.md`.
- [x] Medir usuarios concurrentes, peticiones por segundo, tiempo medio, p95, p99 y errores (RNF-A01, RNF-A05 a RNF-A08). Medido en la máquina el 2026-11-21 con los cinco perfiles (`docs/pruebas/carga/2026-11-21_nube_perfiles`): 5 733 peticiones, hasta 16.6 por segundo con 200 usuarios, p50 1.3 s, p95 y p99 de 30 s, 1 236 fallos (todos 504 de nginx por tiempo).
- [x] Encontrar el punto de saturación y medir cuánto tarda en recuperarse (RNF-A14, RNF-A16). La máquina (e2-highmem-2, 2 vCPU) se satura con unos 40 usuarios: sin CPU (carga media 15 a 19) y con el simulador ocupando un núcleo entero. Se recupera en 40 s al bajar a 20 usuarios, pero desde un p95 que ya era de 7.8 s.
- [x] Hallazgo de la primera corrida local: `sincronizacion` convertía el 429 por cuenta de `casos` en un 503 para todo el lote, y la app reintentaba de inmediato contra el mismo límite. Ahora pasa el 429 con su `Retry-After` (contrato y prueba al día). La app ya lo trata como un 503: reintenta con la espera de WorkManager.
- [x] Listar los endpoints más lentos. En `resumen.md` de la medición. Aun con 20 usuarios: `/mapa` (mediana 11 s), `/api/mapa` (8 s), lote de 5 casos en `sincronizacion` (5.3 s), inicio de sesión (2 a 6 s) y tablero (2.1 s); con más, `pareto`.
- [x] Confirmar o corregir las metas de rendimiento de los requerimientos con lo medido. Las metas se quedan. Con 4 vCPU y las conexiones reutilizadas (`docs/pruebas/carga/2026-11-21_nube_perfiles_conexiones`, con la ventana) la máquina aguanta unos 80 a 100 usuarios: cumplen A06 (73 en la web sin errores), A07 (tablero, p95 < 0.7 s hasta 100 usuarios), A08 (lote de 100, p95 < 14 s hasta 160) y A14 (p95 422 ms); A01 queda en 634 ms con 80 usuarios y A05 en 72.8 casos/s con una sola cuenta CAPTURISTA. Antes: 2 vCPU se saturaban con 40 usuarios. Lo siguiente es `sincronizacion` (una llamada a `casos` por caso).

### F5. Demostración de fallos (N5)

- [x] Guion y evidencia de qué pasa cuando se detiene un microservicio (RNF-C02). Evidencia: `docs/pruebas/fallos/2026-11-16`.
- [x] Lo mismo con Redis, con MongoDB y con PostgreSQL (RNF-C16). Evidencia: `docs/pruebas/fallos/2026-11-16`. MongoDB, solo `/health` y panel (falta la corrida con resumen, bloque D); con PostgreSQL las lecturas dan 503 `SERVICIO_NO_DISPONIBLE` (antes 500; corregido en `fabrica.py` y vuelto a demostrar el 2026-11-16).
- [x] Lo mismo con el bucket, y con una petición que excede el tiempo máximo (RNF-C18). Evidencia: `docs/pruebas/fallos/2026-11-16`. Bucket, solo `/health` y panel (falta la subida, bloque D).
- [x] Fallo de worker: el simulador se detiene después de guardar los resultados y antes de confirmar la corrida, y no quedan corridas duplicadas ni resultados perdidos [Retro: fallo de worker]. Con D y E. `test_f5_el_trabajador_muere_entre_guardar_la_serie_y_confirmar` (`microservicios/simulador/tests`): el proceso muere ahí, el siguiente arranque la reencola y queda una sola corrida `completado` con su serie entera, sin días duplicados; a los 3 intentos se cierra sin serie. La demostración contra los contenedores (`demo_fallos.py`) queda pendiente.

### F6. Documentos

- [x] Guía de despliegue en GCP y `INSTALACION.md` al día, con MongoDB, el emulador y nginx. nginx en local, hecho (§6 de los microservicios en `INSTALACION.md`). Guía de despliegue: [`docs/DESPLIEGUE_GCP.md`](../../DESPLIEGUE_GCP.md) (2026-11-21): máquina, firewall e IAP, Docker y secretos, dominio y certificado, levantar (`infra/levanta_nube.sh`), Cloud Logging, actualizar con migraciones, la GPU, pruebas de carga, costos y problemas conocidos.
- [x] Resultados de Locust y de las pruebas de fallos en `docs/` (`docs/pruebas/carga` y `docs/pruebas/fallos/2026-11-16`).

### F7. Completar los servicios de vigilancia, analítica y plataforma

[Retro: «Microservicios existentes que deben completarse y fortalecerse»]. Los servicios de F en [«Dueños de los servicios»](#dueños-de-los-servicios). La lista es lo que pide la retroalimentación, no lo que falta: lo que ya se cumpla se marca al revisarlo. Lo que dice «reabierto» o «hoy no existe» ya se revisó.

- [x] Revisar cada servicio contra su lista de la retroalimentación y marcar aquí lo que ya cumple. Hecho el 2026-11-21: [`revision_f7.md`](revision_f7.md), servicio por servicio, con lo que cumple, lo parcial y lo que falta, y lo que sigue por tamaño.

**Vigilancia**

- [ ] `casos`: actualizar, dar seguimiento y rechazar, con historial, duplicados y control de conflictos (RF-C11 y RF-C15, reabiertos; decisión del bloque 0). Hoy: registro, validaciones e idempotencia, sí; actualizar y cambiar estado, no ([`revision_f7.md`](revision_f7.md)).
- [ ] Formularios por enfermedad, con versiones (para B4). Falta por completo: los campos de un caso son fijos ([`revision_f7.md`](revision_f7.md)).
- [ ] `sincronizacion`: conflictos entre lo capturado sin conexión y lo que cambió otro profesional. Lo demás de su lista se cumple; este conflicto espera a que `casos` tenga actualización ([`revision_f7.md`](revision_f7.md)).

**Analítica**

- [ ] `indicadores`: cada indicador con su numerador, su denominador y su periodo; capacidad utilizada, con su fuente (RF-G07, reabierto). Hoy: incidencia por 100 000 semanal; faltan numerador, denominador y periodo explícitos, mortalidad, hospitalizaciones y prevalencia ([`revision_f7.md`](revision_f7.md)).
- [ ] `series`: filtrado, paginación y agregaciones por enfermedad, periodo, región y grupo. Hoy: por enfermedad, región y periodo (7, 30 o 90 días), por día; faltan paginación, agregación por semana o mes y el formato para Highcharts ([`revision_f7.md`](revision_f7.md)).
- [ ] `zonas`: mapas de calor y agrupaciones territoriales. El mapa del escritorio (A4) espera además la geometría oficial de los municipios: hoy dibuja marcadores sin polígonos. Hoy: mapa temático y semáforo por municipio ([`revision_f7.md`](revision_f7.md)).

**Plataforma**

- [ ] `notificaciones`: avisos de campañas, de datos incompletos y de errores operativos. Hoy: escenarios por aprobar, corridas terminadas y casos nuevos; `SYSTEM` existe sin uso ([`revision_f7.md`](revision_f7.md)).
- [ ] `estado-servicios`: capacidad de procesamiento (la cola de cada motor). Hoy: APIs, bases, latencia y errores de 24 h; faltan colas, capacidad y alertas técnicas ([`revision_f7.md`](revision_f7.md)).

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
