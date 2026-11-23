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
| A       | D       | Proyectos de investigación, historial y archivado de escenarios (D7). Listos en el servidor (D54) |
| A       | E       | Las rutas de calibración y sensibilidad (E7)                                                    |
| A       | D       | Importar conjuntos de datos (D6)                                                                |
| A       | 0       | El método de calibración y el de sensibilidad. Resuelto: D46 y D50                              |
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

- [x] ~~Definir qué cambia en la interfaz del escritorio para que sea más intuitiva y usable. **Frena a A.** Delegada al bloque A (A1).~~ No lo hará el bloque 0 (2026-11-22); pasa a A (A1).
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
- [X] Con el profesor: confirmar el volumen de D29 y si hay créditos para la GPU (brechas §8). **Frena a D y a F.** Créditos: sí (D23). Falta el volumen.

### Decisiones nuevas por la retroalimentación

Cada una reemplaza o amplía una decisión vigente (ver [«Lo que la retroalimentación reabre»](#lo-que-la-retroalimentación-reabre)) y se registra en `decisiones/` con número nuevo.

- [x] La web consume los servicios: en qué orden pasa cada módulo y qué ve el usuario cuando un servicio no responde. Reemplaza D20 y D33. **Frena a C y a E.** Opción B, sin respaldo en la base; orden de la demostración integrada (D36).
- [x] Dueño de cada regla de negocio, y cómo dejan los servicios de importar `backend_web`. Cambia las reglas 2 y 14 de `microservicios/AGENTS.md`. **Frena a E.** El dueño de la tabla es el dueño de la regla; los demás la piden por HTTP (D37).
- [X] Instituciones, regiones y los perfiles INVESTIGADOR y AUTORIDAD SANITARIA, con los permisos por recurso, región, institución y operación. Amplía D1. **Frena a E, B y C.** El bloque E propuso D42 y D43 (integradas el 2026-11-21).
- [x] Editar y rechazar casos: qué se edita, quién lo hace y cómo se detecta un conflicto. Reemplaza lo de D32 sobre editar casos. **Frena a E y a B.** D47: corrección y seguimiento con control de versión.
- [x] Calibración: método, función de pérdida, métricas de ajuste, datos y dónde corre. Reemplaza D24. **Frena a A.** D50: ABC por rechazo sobre `seir-ref` contra los casos de COVID-19 de NL de 2020 (DGE, agregados por semana), en el servicio nuevo `calibracion`; migraciones 061 a 063.
- [x] Corridas interrumpidas: reencolarlas en lugar de cerrarlas como fallidas, y qué pasa con su serie en MongoDB (RNF-C03). **Frena a E y a D.** Se reencolan hasta 3 intentos con la misma semilla; solo cuentan las series de corridas completadas; migración 045 (D38).
- [x] MFA: qué perfiles son críticos y con qué segundo factor. **Frena a E.** TOTP para ADMINISTRADOR, EPIDEMIOLOGO y AUTORIDAD_SANITARIA (D40). Arranca apagado: se prende cuando la web, el escritorio y la móvil tengan el segundo paso.
- [x] Qué son «campañas» y «seguimiento de intervenciones» en la web, y qué datos llevan. **Frena a C y a E.** Campañas, avisos de datos incompletos y preferencias de avisos: D49.
- [x] ~~Qué agrupa un proyecto de investigación del escritorio y dónde vive. **Frena a A y a E.**~~ No lo hará el bloque 0 (2026-11-22); pasa a A y D (A4 y D7).
- [x] ~~Reservar los números de migración para lo nuevo: instituciones y perfiles, casos, corridas, proyectos y calibración.~~ No lo hará el bloque 0 (2026-11-22).

### Validación científica

[Retro: «Hace falta validación científica»]. Lo que no se valide se presenta como exploratorio.

- [x] Ficha de cada modelo (`seir-ref`, `abm-ref` y `abm-gpu`): formulación matemática, población representada, variables, supuestos, fuentes de parámetros, límites de aplicación, versión del algoritmo, escenarios de prueba y resultados de validación. Se amplía [`ficha_simulador.md`](../../arquitectura/ficha_simulador.md). §16 (una columna por modelo) y §17 (categoría de D39); §13 a §15 con la validación.
- [x] ~~Investigar una fuente de datos observados para validar y calibrar: qué serie, de qué periodo y con qué licencia. Con D (D6).~~ No lo hará el bloque 0 (2026-11-22); pasa a D (D6), con la serie que fija D50.
- [x] Validación contra resultados esperados: soluciones conocidas (por ejemplo, el tamaño final de un brote SEIR), casos límite y `abm-ref` contra `seir-ref` (ya medido en la ficha). §13 de la ficha, `python -m procesamiento.mediciones esperados` y `test_validacion_cientifica.py`. Encontró que el R0 efectivo es ~10 % mayor que el nominal (§11): corregirlo queda como decisión del equipo.
- [x] ~~Validación contra los datos observados.~~ No lo hará el bloque 0 (2026-11-22); pasa a E con la calibración (D50: la ventana de validación).
- [x] Análisis de sensibilidad: variar cada parámetro y comprobar que el modelo responde como se espera (RF-F12, reabierto). El escritorio lo muestra (A4). §14 de la ficha (un factor a la vez, ±20 %) y `python -m procesamiento.mediciones sensibilidad`; las direcciones las revisa `test_validacion_cientifica.py`. Mostrarlo en el escritorio sigue en A4.
- [x] ~~Calibración: el algoritmo en `procesamiento/`, con su función de pérdida, sus métricas de ajuste y sus versiones. El escritorio la muestra (A4) y un servicio la expone (E7).~~ No lo hará el bloque 0 (2026-11-22); pasa a E, con el servicio `calibracion` (E7).
- [x] Reproducibilidad: la corrida determinista repetida, y la estocástica con la misma semilla y versión, dan lo mismo. Las pruebas existen (`test_contrato_motor.py`); falta la evidencia para la entrega. Evidencia en `docs/pruebas/validacion/2026-11-19` y §15 de la ficha; `seir-ref` y `abm-ref` (sin GPU aquí, `abm-gpu` queda pendiente de evidencia).
- [x] ~~Incertidumbre: cada intervalo se muestra con su interpretación.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Las pantallas distinguen simulación exploratoria, predicción y resultado validado. Hoy `AVISO_SIMULACION` solo dice que no es una predicción.~~ No lo hará el bloque 0 (2026-11-22).

### Documentos

- [x] ~~Validar en equipo los requerimientos y pasarlos de Borrador a Aceptado.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Validar la arquitectura v3 contra la rúbrica (brechas §9.5) y marcar la v2 como Obsoleta.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Corregir en `procesos_v3.md` las referencias de sección que quedaron desfasadas con `brechas_v3.md`.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Limpiar `decisiones/todo.md`: quitar lo hecho y las decisiones que ya no están pendientes.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Llenar los nombres de la tabla de reparto de este documento.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Llevar a los requerimientos lo que la retroalimentación reabre: sacarlo de «Fuera de alcance» y darle estado.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Actualizar el `AGENTS.md` de la raíz y `microservicios/AGENTS.md` con las decisiones nuevas. Hoy dicen que la web no llama a los servicios, que los servicios reutilizan `backend_web` y que la calibración está fuera.~~ No lo hará el bloque 0 (2026-11-22).

### Integración

- [x] ~~Crear un issue por casilla, con su bloque y su responsable.~~ No lo hará el bloque 0 (2026-11-22).
- [x] Reservar los números de migración de cada bloque: tabla y reglas en [«Números reservados»](../../../datos/postgres/migraciones/README.md#números-reservados-tercer-parcial) (2026-11-17).
- [x] ~~Confirmar el número de cada migración antes de que alguien la cree, y agregar a esa tabla los que se pidan fuera de ella.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Integrar las ramas de los dos salones al menos una vez por semana.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Ensayar P1, P2 y P3 de punta a punta en la nube, con cada rol.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Guion de la demostración integrada: los 12 pasos de [«Criterios de aceptación»](#criterios-de-aceptación), primero en local y después en la nube.~~ No lo hará el bloque 0 (2026-11-22).

### Entrega final

- [x] ~~Expediente técnico con los apartados que lista la rúbrica. Se arma enlazando lo que ya hay en `docs/`.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Wiki: miembros y roles, por dónde empiezo y glosario (`docs/todo.md`).~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Un README en cada carpeta de `docs/`.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Video de demostración y presentación final.~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Matriz individual de autoría y participación: servicios, pruebas, integración, documentación, incidencias y correcciones de cada estudiante [Retro: participación].~~ No lo hará el bloque 0 (2026-11-22).
- [x] ~~Qué entregó cada salón, por separado [Retro: participación].~~ No lo hará el bloque 0 (2026-11-22).
- [x] Toda la suite en una sola ejecución, sobre una base creada desde cero, con un solo resultado consolidado. Nada de juntar pruebas de distintas versiones [Retro: pruebas]. `docs/pruebas/suite/2026-11-19`: 2281 pasan, 2 fallan (ya existían: la semilla no trae un epidemiólogo inactivo y una de `frontend_desktop`), 182 se saltan. Repetirla cuando se integren los PR.
- [x] ~~Cada integrante ensaya ejecutar, explicar y modificar lo que le tocó, para la defensa técnica [Retro: participación].~~ No lo hará el bloque 0 (2026-11-22).

---

# Salón 1 · Clientes

## A. App de escritorio · `frontend_desktop/`

Antes de empezar: `frontend_desktop/AGENTS.md`. La app solo habla XML.

La [evidencia del bloque A](../../pruebas/bloque_a_escritorio.md) incluye los flujos, los
comandos de prueba y los pasos de defensa. Lo marcado se implementó y se verificó en el
escritorio, y se integró en `feat/tercer-parcial` el 2026-11-20 (PR #173).

### A1. Interfaz más intuitiva y usable

**Lo define el bloque A** (el bloque 0 lo delegó el 2026-11-22). Las casillas de implementación se escriben cuando exista la definición. La meta [Retro: usuarios finales]: un epidemiólogo o un analista entiende, configura, ejecuta y compara escenarios sin saber programar, y la app le muestra el progreso, errores que se entienden, resultados visuales, supuestos y limitaciones.

- [ ] Proponer los cambios, pantalla por pantalla, y acordarlos dentro del bloque A.
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
- [x] **Implementado en escritorio.** Subir el reporte al bucket y mostrar su URL firmada (D30, RF-F17). Desbloqueado por D2 (2026-11-22): `POST /api/v1/reports?runs=…` de `evidencias` con el PDF en el cuerpo y `GET /api/v1/reports/{id}/url`; en local va al emulador y en GCP a `gs://integracion-515321-archivos` (D2, 2026-11-23). Comparación tiene «Subir reporte», que manda el mismo PDF que «Exportar PDF» con `X-Content-SHA256` y sus corridas (hasta 100), y «Abrir reporte subido», que pide la URL firmada y la abre en el navegador (`servicios.subir_reporte` y `url_reporte`, `test_mfa_reportes_datos.py`, 2026-11-23). La prueba autenticada en nube queda en A3.
- [x] Segundo paso del login (D40) y equipo autorizado (D41). Código TOTP o de respaldo, alta con el código que emite un ADMINISTRADOR y códigos de respaldo que se muestran una vez; regresa a la contraseña si el reto vence. Con `EPIDEMIA_DISPOSITIVO=1` manda un identificador estable del equipo, como la web. Con esto la web y el escritorio ya tienen el segundo paso que pide D40 para prender `MFA_PERFILES`; falta la móvil (B). Probado con los ejemplos de `docs/contratos/auth` en `test_mfa_reportes_datos.py`.
- [x] Leer `exp` del token sin verificar la firma y renovarlo antes de que venza (D35, RF-H23).
- [x] La comparación dice «Personas-día» donde hoy dice «Costo», y muestra y exporta `costo_pesos` aparte, como «sin dato» cuando es nulo (D3, `ui/comparacion.py` y `exportar.py`). Desde el 2026-11-17 `pareto` ya manda personas-día en `costo`: hasta este cambio, la pantalla las rotula como costo.

### A3. Verificar

- [x] Sin red, con rechazo o sesión vencida, la app explica el problema (RF-H24, RNF-E06). Evidencia en `test_api.py` y `test_mensajes_ui.py`.
- [x] Búsqueda, filtros, tabla, XSD y exportación verificados localmente con ejemplos XML y PDF. Se conserva la evidencia previa de roles ANALISTA, ADMINISTRADOR y EPIDEMIOLOGO con respuestas controladas.
- [ ] **Parcial.** Verificación HTTPS contra `epidemos.app` (D25, D26). El cliente descubrió los 29 servicios sanos y la ventana mostró el captcha XML con verificación TLS. Geometría e historial respondieron 401 sin sesión. Para cerrar la prueba en nube falta iniciar sesión con una cuenta de demostración y recorrer mapa y auditoría con datos del despliegue, subir un reporte al bucket y abrir su URL, importar un conjunto en Datos y crear un proyecto con un escenario.
- [x] `python -m pytest frontend_desktop` pasó la suite completa con 315 pruebas, y con 388 tras el MFA, el reporte al bucket y las pantallas Datos y Proyectos sobre la rama de integración (2026-11-23). Ver [reproducción y resultados](../../pruebas/bloque_a_escritorio.md).

### A4. Módulos que pide la retroalimentación

[Retro: «Aplicación de escritorio»]. Todos son obligatorios. Algunos ya existen en parte (el editor, la comparación y Pareto): la primera casilla es revisarlos.

- [x] Contrastar esta lista con el código y las pruebas de cada pantalla.
- [x] **Implementado en escritorio.** Proyectos. El escritorio ya selecciona región, enfermedad, horizonte y motor de escenarios y corridas. La definición, los permisos y la persistencia del proyecto son de D54 (D7, 2026-11-23): `escenarios` crea, cambia, archiva y lista proyectos (`/projects`) y mete escenarios en ellos. La pantalla **Proyectos** (Ctrl+5, `ui/proyectos.py`, 2026-11-23) lista los de las regiones de la cuenta, crea y cambia (solo lo que cambió; enfermedad y región fijas si ya tiene escenarios), archiva y restaura; mete y saca escenarios de la misma enfermedad y región, y archiva o restaura un escenario (RF-D12). Solo el autor o un ADMINISTRADOR edita, y el servidor decide. Probado con los ejemplos del contrato en `test_proyectos.py`; la prueba contra el servicio levantado queda en A3.
- [x] **Implementado en escritorio.** Gestión de datos. Se consultan las series guardadas de corridas y las series de casos municipales de `zonas`. La pantalla **Datos** (Ctrl+4, `ui/datos.py`, 2026-11-23) consume `importacion` (D6, D53): lista las versiones de cada conjunto con fuente, licencia, corte y huella, muestra sus puntos validados con `serie_observada.xsd`, verifica la calidad sin guardar (`/datasets/validate`, con todas las fallas) e importa la versión siguiente (avisa si el archivo ya estaba). Probado con los ejemplos del contrato en `test_mfa_reportes_datos.py`; la prueba contra el servicio levantado queda en A3.
- [ ] **Parcial (D).** Configuración del modelo. Se elige el motor al lanzar, se ajustan población, infecciones iniciales y horizonte. `parametros/status` aporta definiciones, unidades, rangos, fuentes y estado. Falta el ajuste de parámetros por versión del escenario. Qué parámetros se guardan por versión lo deciden A y D (el bloque 0 lo delegó el 2026-11-22).
- [x] Editor de escenarios. Alta, duplicado, nuevas versiones, historial y edición del borrador por XML. La prueba del bloque A verifica que una respuesta tardía no reemplaza la versión que pidió el usuario.
- [x] Configuración de intervenciones. Intervalo y duración inclusiva, cobertura, cumplimiento, parámetros por tipo y consulta del costo unitario con su procedencia. Cambiar el costo del catálogo es una operación compartida de administración.
- [ ] **Parcial (E y D).** Calibración. El escritorio consume el estado, la categoría y la evidencia de D46. El método ya está decidido (D50): ABC por rechazo sobre `seir-ref`, con RMSE, R² y cobertura. Para ejecutarla falta el servicio `calibracion` con su algoritmo (E7); la serie observada ya está en la 061 (D6).
- [ ] **Parcial (E).** Validación. El escritorio muestra errores y advertencias del escenario, el motivo de su categoría y la sensibilidad exploratoria de una versión aprobada (D46). La validación con datos observados y su criterio están en D50 (`GET /api/v1/calibrations/{id}/fit`, ventana de validación), que espera a E.
- [ ] **Parcial (E).** Ejecución asíncrona. La app encola, monitorea, sigue la nueva corrida y cancela en espera por versión y motor. Falta demostrar la recuperación del trabajador de punta a punta (D38).
- [x] Comparación descriptiva. Mediana, p5–p95, diferencias absolutas y relativas contra referencia, semillas completas y curvas alineadas por día. Se avisa si cambian motor, versión u horizonte.
- [x] Análisis económico exploratorio y Pareto (D3/D8). Se ven supuestos y diferencias de costos en personas-día y pesos. La frontera sobre medianas muestra dominancia y alternativas fuera por falta de datos.
- [x] **Implementado en escritorio.** Mapa regional. Dibuja los 51 polígonos oficiales de INEGI de `zonas/geometry` con ETag, coloreados con el nivel de `zonas/map`. La selección sincroniza mapa, tabla y serie. Verificado con la geometría del repositorio y el ejemplo XML. La prueba autenticada en nube queda en A3.
- [x] Reportes. El comparativo exporta gráficas, metodología, diferencias, advertencias, costos e identificadores de origen. La ficha PDF por réplica exporta serie, indicadores, parámetros con procedencia, versión y limitaciones devueltos por `resultados`.
- [ ] **Parcial (D y E).** Reproducibilidad. Misma versión del escenario, semilla y motor al reencolar; consulta de huella y resumen, acceso al equivalente y seguimiento. Faltan ID/versionado del conjunto y un contrato para repetir con configuración histórica. Desde D55 (2026-11-23), la versión aprobada guarda su firma, que es la huella de la entrada del motor, y `aprobacion` (`/versions/{id}/signature`) dice cuántas corridas simularon exactamente lo firmado.
- [x] **Implementado en escritorio.** Auditoría. El diálogo consulta `roles/audit/history` por escenario, versión o intervención, muestra autor, acción y valores antes/después y respeta el 403 del servidor (D43). Probado con XML, paginación y rechazo regional controlado. La prueba autenticada en nube queda en A3.
- [x] Seleccionar una curva por leyenda o tabla, escoger una réplica y abrir su ficha, sus supuestos y su versión del escenario. La repetición histórica sigue en el requisito de reproducibilidad.
- [x] Trazabilidad gráfica. `corridas` aporta versión del motor y horizonte; `comparacion` y `resultados`, las series e indicadores; `pareto`, los costos. Los ejes muestran unidades. Si faltan datos de procedencia, se muestran tablas y se omite la gráfica afectada.

## B. App Android · `frontend_movil/`

La app solo habla JSON.

### B1. Funciones que faltan

- [x] Indicador de conexión fijo, visible en todas las pantallas (C3, RF-I20, RNF-E11). `ui/navegacion/IndicadorConexion.kt`.
- [x] Menú por rol: un rol distinto del CAPTURISTA no ve la captura (C8, RF-I19). Los roles del login quedan con la sesión (`InicioViewModelTest`).
- [x] Las fotos se suben y se bajan con la `evidencias` del bucket (D30, RF-C03). Subir: igual que antes (con el bucket caído, 503 y la app reintenta sin perder la foto). Bajar (2026-11-23): el seguimiento de un caso lista sus fotos (`GET /cases/{id}/attachments`) y "Ver" pide la URL firmada (`GET /attachments/{id}/url`) y baja directo del bucket sin el token de la sesión; lo que llega se compara con su SHA-256 antes de mostrarlo (`SeguimientoViewModelTest`). En la VM, el bucket privado `integracion-515321-archivos` desde el 2026-11-23.
- [x] Probar que el aviso por lote no se repite cuando la app reintenta el mismo lote (D32, RF-C19). La app reenvía el mismo `batch_id` (`SincronizadorTest.sin_respuesta_reintenta_el_mismo_lote`) y `sincronizacion` no vuelve a avisar (`test_reintentar_el_lote_no_vuelve_a_avisar`).
- [x] Mostrar los tipos de aviso de la migración 037 (`NEW_CASES`, `SCENARIO_SUBMITTED` y `SCENARIO_REJECTED`) en `Formato.kt` (D32).

### B2. Verificar

- [x] Sin red, con un rechazo del servidor y con la sesión vencida, la app explica qué pasó sin cerrarse (RF-I22, RNF-E06). Sin red y los rechazos ya se explicaban en cada pantalla; desde el 2026-11-22, al perder la sesión el login dice que se cerró y que los casos sin enviar siguen en el teléfono.
- [x] Los casos sin enviar se quedan al cerrar sesión y se mandan cuando esa cuenta vuelve a entrar (D19, RF-I21). `SincronizadorTest`.
- [x] La app pasa la lista de la rúbrica para Android: perfil, consulta, registro, actualización (dosis y avisos, D32) y borrado local de credenciales. Perfil (Mi perfil), consulta (Mis casos, seguimiento, consulta por zona y lotes), registro (captura), actualización (dosis, avisos leídos y corrección de casos, D47) y borrado de credenciales al cerrar sesión (`SesionTest`). Revisado el 2026-11-22.
- [ ] La app funciona contra el dominio real con su certificado, de preferencia también en un Android 7.0 (D26). Ya no espera a F: `https://epidemos.app` responde con las rutas que usa la app y el APK de la nube está (B3). Falta abrirlo en un teléfono o emulador, y en un Android 7.0.
- [x] Las pruebas de `frontend_movil` pasan. 116 pruebas unitarias con `./gradlew testDebugUnitTest` (2026-11-22), con el JDK de Android Studio: con el de Adoptium fallan las de DataStore en Windows (`frontend_movil/README.md`). Las instrumentadas compilan; correrlas pide emulador.

### B3. Entregables

- [x] Manual de usuario de la app móvil en `docs/manuales/` (RNF-E08). `manual_usuario_movil.md`, al día con B4 (2026-11-22), sin capturas todavía.
- [x] APK de la demostración, apuntando al dominio de la nube. `./gradlew assembleDebug -Pepidemia.directorio=https://epidemos.app/estado-servicios/` (`frontend_movil/README.md`, sección 2); el APK no se sube al repositorio.

### B4. Módulos que pide la retroalimentación

[Retro: «Aplicación móvil Android»]. Para capturistas, personal de vigilancia, supervisores regionales y responsables de campañas.

- [x] Revisar la app contra esta lista y marcar lo que ya cumple. Revisado el 2026-11-22; lo que hizo falta está en `frontend_movil/README.md`, sección 10.
- [x] Panel del capturista: casos pendientes, formularios, registros incompletos, sincronizaciones pendientes y avisos. El inicio muestra los casos por enviar, los que tienen datos faltantes (`GET /cases/incomplete`), los avisos sin leer y los formularios en el teléfono.
- [x] Seguimiento: actualizar el estado de un caso, con observaciones e historial (RF-I12, reabierto). Pantalla de seguimiento: estado en el servidor, motivo e historial (`GET /cases/{id}/history`); quien lo capturó lo corrige mientras está pendiente con `PATCH /cases/{id}` e `If-Match`, con su motivo. Cambiar el estado es del EPIDEMIOLOGO (D47).
- [x] Formularios por enfermedad, con versiones, validaciones y campos obligatorios. La app baja `GET /forms/current` con los catálogos, arma la captura con esos campos, los valida como `casos` y manda `form_id` y `form_answers` en el lote (D48). Base local en la versión 3.
- [x] GPS, con selección manual cuando la captura automática no conviene. «Escribir las coordenadas» en la captura.
- [x] Cola local cifrada: hoy Room guarda los casos sin cifrar y solo los tokens van cifrados. Los datos de salud de cada caso (edad, sexo, inicio de síntomas, resultado, gravedad, ubicación y respuestas) van en una columna cifrada con la llave del Keystore, sin librería nueva; la enfermedad, el municipio y la fecha quedan en claro para listar. Decidido en la sesión del 2026-11-22, falta registrarlo en `decisiones.md`.
- [x] Un caso no se muestra como recibido, validado o publicado hasta que el servidor lo confirma. «Recibido» solo con el `case_id` que regresa el lote; validado, descartado o duplicado solo los dice el seguimiento, desde el servidor.
- [x] La sincronización no sobrescribe en silencio lo que cambió otro profesional: el conflicto se muestra. Las correcciones van con `If-Match`; un 412 se muestra con el caso como quedó, sin pisarlo (`SeguimientoViewModelTest`). Corregir pide conexión: la app no usa los `updates` del lote.
- [x] Consulta epidemiológica agregada por zona, periodo y enfermedad, según los permisos. «Consulta por zona» (`GET /zones`): casos, incidencia y nivel por municipio, para 7, 30 o 90 días; el alcance lo aplica el servidor.
- [x] Alertas: tareas nuevas, registros rechazados, campañas y eventos de vigilancia, desde `notificaciones`. `CASE_REJECTED` («Caso descartado»), `CAMPAIGN` («Campaña») y `DATA_INCOMPLETE` («Datos incompletos») en `Formato.kt`.
- [x] Control de calidad: avisa de campos incompletos, fechas incoherentes y posibles duplicados. La captura dice qué falta sin impedir guardar, rechaza fechas incoherentes y pide confirmar un posible duplicado del teléfono.
- [x] Perfil con institución, región asignada y estado de conexión. E7 ya los daba; Mi perfil los muestra.
- [x] Menú para cada perfil de campo. D56 (2026-11-23): CAPTURISTA captura; EPIDEMIOLOGO (vigilancia y campañas) y AUTORIDAD_SANITARIA (supervisor regional, con su alcance D43) consultan casos del servidor, campañas, lotes, zonas y avisos, sin validar ni descartar (eso es de la web); ANALISTA e INVESTIGADOR, consulta por zona. `casos`, `vacunas` y `dispositivos` ya dejan leer a los perfiles de D42 y `casos` y `zonas` aplican el alcance por región (`MenuTest`, `CasosServidorViewModelTest`, `CampanasViewModelTest`).

## C. Sistema web · `frontend_web/` y `backend_web/`

La web deja de ir directo a PostgreSQL y a Redis, y consume los servicios (C6; reemplaza D20). Mientras tanto, nada de SQL en `frontend_web`.

### C1. Permisos (D1)

- [x] Migración 034: crea `scenarios.approve`, lo da a EPIDEMIOLOGO y ADMINISTRADOR, quita `audit.read` al EPIDEMIOLOGO (RF-L05) y quita `cases.create` al ADMINISTRADOR. También crea `reports.upload` para ANALISTA y ADMINISTRADOR (D35). `034_permisos_d1_y_reportes.sql` (2026-11-22); amplía el CHECK de `permissions.action` con `upload`. `aprobacion` deja revisar también al ADMINISTRADOR.
- [x] Quitar la captura de casos de la web: `/reportes/nuevo`, sus enlaces y su plantilla.
- [x] Guardar los permisos en la sesión y crear `requiere_permiso(codigo)`, que responde 403 y registra `PERMISSION_DENIED` (RF-A05). `frontend_web/app/permisos.py`; los permisos salen de `roles` `GET /api/v1/permissions/me` y el 403 se anota con `POST /api/v1/audit/denied`.
- [x] Cambiar el candado de cada ruta según la [matriz de permisos](../../requerimentos/matriz-permisos.md).
- [x] El CAPTURISTA entra solo al tablero y al mapa; lo demás le responde 403 (RF-G11).
- [x] Cuenta de prueba de CAPTURISTA en `datos/postgres/semillas/demo_datos_nl.sql`. Ya existía: `karla.trevino`.
- [ ] Probar cada pantalla con un rol que entra y con uno que no (pruebas de roles). Pendiente: las pruebas de la web deben simular los servicios (D36).

### C2. Sesión y seguridad

- [x] La web registra y revisa su sesión en Redis; cerrar sesión deja el token sin valor (I3, RF-A12). Verificado el 2026-11-16: `demo_fallos.py web` y `redis` (`docs/pruebas/fallos/2026-11-16`).
- [x] Segundo paso del MFA en el login de la web (D40): verificar el código o el de respaldo, enrolarse con el código de alta y ver los códigos de respaldo una vez (`/login/mfa`). Con el MFA o `DISPOSITIVO_OBLIGATORIO` prendidos, la web manda el dispositivo del navegador (D41). Con esto, la web ya no impide prender el MFA.
- [x] Protección contra CSRF en los formularios (RNF-D07). `frontend_web/app/seguridad.py`: token por sesión en cada formulario POST.
- [x] Encabezados de seguridad en las respuestas (RNF-D21). CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` y HSTS detrás de HTTPS.
- [x] Verificar que ninguna consulta arma SQL con texto del usuario (RNF-D05) y que las plantillas escapan lo que muestran (RNF-D06). La web ya no tiene SQL (C6). Las plantillas no usan `|safe`; el JavaScript que arma HTML con datos del servidor los escapa (mapa, comparación y estado de la corrida).

### C3. Resultados y archivos

- [x] La corrida muestra su resumen desde `simulation_runs` y pide las curvas a `resultados`. Si `resultados` no responde, se ve el resumen sin curvas (D28, D20, RF-F21). Espera a D y a E.
- [x] La web deja de leer `simulation_results`. Hecho en D1 (2026-11-18), también en `/comparacion`.
- [ ] La web muestra la foto de un caso con una URL firmada que vence en minutos (D30, RF-C20). Desbloqueado por D2 (2026-11-22): `GET /api/v1/attachments/{id}/url` de `evidencias`.
- [ ] La web abre el reporte de una comparación con su URL firmada (RF-F17). Desbloqueado por D2 (2026-11-22): `GET /api/v1/reports?runs=…` y `GET /api/v1/reports/{id}/url` de `evidencias`.
- [ ] La web recibe el reporte de una comparación (ANALISTA y ADMINISTRADOR, `reports.upload`), lo valida por su contenido, su tamaño y su huella, y lo manda al bucket con la misma tabla y la misma interfaz que el escritorio (D35, RF-G16). Desbloqueado por D2 (2026-11-22): la web lo reenvía por HTTP a `POST /api/v1/reports?runs=…` de `evidencias`, que valida contenido, tamaño y huella (`X-Content-SHA256`); no importa `epidemia_comun` (D36). El permiso ya existe (034) y `/reportes` deja el lugar.
- [x] `/comparacion` dice personas-día en el eje y la tabla de la frontera, y muestra `costo_pesos` aparte (D3). Con la trazabilidad de cada costo.
- [x] `/comparacion/costos` permite fijar las personas-día por dosis de la vacunación, con fuente o marca de supuesto (D3, migración 040). Sin ese factor, la comparación de escenarios con vacunación se niega. Ruta nueva en `intervenciones`: `PUT /api/v1/intervention-types/{id}/person-days`.

### C4. Avisos de P2

- [x] Al aprobar o rechazar en la web se avisa al autor, en los dos casos (I1, RF-D16). Lo hace `aprobacion` (`SCENARIO_APPROVED` y `SCENARIO_REJECTED`).
- [x] El EPIDEMIOLOGO ve en la web los avisos de versiones por revisar y de casos nuevos (RF-D15, RF-C19). `/avisos` y la campana con los no leídos.

### C5. Verificar y entregar

- [x] El tablero y el mapa se leen en un teléfono (RNF-E03). Vista de menos de 760 px en `styles.css`. Falta revisarlo en un teléfono real.
- [x] Los errores se explican sin mostrar la traza (RNF-E06). Manejadores de 400, 403, 404, 405, 500, servicio caído y rechazo de un servicio.
- [x] Las pantallas de resultados conservan el aviso de que no es una predicción (`AVISO_SIMULACION`). Además muestran la categoría de la corrida que regresa `resultados`.
- [x] Manual de usuario de la web en `docs/manuales/` (RNF-E08). `manual_usuario_web.md`.

### C6. La web consume los servicios

[Retro: «Ninguna aplicación cliente deberá conectarse directamente a PostgreSQL, MongoDB o Redis»]. Va con D36, la decisión que reemplaza D20.

- [x] Inventario: cada pantalla de la web y cada consulta de `backend_web` que usa, con el servicio que debe atenderla. Lo que no tenga servicio se le pide a su dueño (E9). En [`inventario_web_servicios.md`](../../arquitectura/inventario_web_servicios.md): 20 de 32 pantallas ya tienen su servicio; faltan 11 rutas (4 de D, 4 de E y 3 de F).
- [x] Iniciar y cerrar sesión con `auth` y `sesiones`, sin leer Redis. `frontend_web/app/sesion_servicios.py` y el cliente `backend_web/servicios.py`: login con el captcha de `auth`, sesión revisada por `sesiones` en cada petición (renueva el access con el refresh), logout en `sesiones`. Sin `sesiones` la web no deja pasar (D36). Se retiró `sesion_redis.py`.
- [x] Pasar cada módulo a su servicio, en el orden que fije la decisión. 2026-11-22: `frontend_web/app/routes.py` llama a `backend_web/servicios.py` y no a `queries.py`. Lo que la web usa sin base quedó en `backend_web/formato.py` y `catalogo.py`. Cambios compatibles en los servicios: `escenarios` (autor de la versión, parámetros congelados, población de la región), `corridas` (enfermedad y región en la lista) y `usuarios` (institución y región en la lista).
- [x] Cuando un servicio no responde, la pantalla lo explica y lo demás sigue. `seccion()` en `routes.py` y el aviso de `base_app.html`.
- [x] Al terminar, la web no tiene credenciales de PostgreSQL, MongoDB ni Redis, y no importa `epidemia_comun`. El contenedor arranca con `frontend_web/servir.py` y el compose ya no le pasa `DATABASE_URL`. Las pruebas viejas de `frontend_web/tests` todavía usan la base: hay que pasarlas a servicios simulados.

### C7. Módulos que pide la retroalimentación

[Retro: «Aplicación web»]. Algunos ya existen (el tablero, el mapa y las regiones): la primera casilla es revisarlos.

- [x] Revisar la web contra esta lista y marcar lo que ya cumple.
- [x] Administración regional. Regiones, con la corrección de la población y de las bandas de edad.
- [x] Vigilancia: casos por región y periodo, con su seguimiento. `/vigilancia` y `/vigilancia/casos/<id>`, con el historial y el cambio de estado (D47).
- [x] Campañas. Decididas en D49. `/campanas` con el servicio `vacunas`: consulta, alta y cancelación.
- [x] Mapas epidemiológicos e indicadores.
- [x] Reportes. `/reportes` reúne las descargas. Falta el reporte de la comparación: la ruta ya está (D2, C3).
- [ ] Seguimiento de intervenciones. Lo definen C y E y lo registran en `decisiones/` (el bloque 0 lo delegó el 2026-11-22). **Falta que E valide [D51](../../decisiones/D51-seguimiento-de-intervenciones.md)**, la propuesta de C; la pantalla ya está. `/intervenciones` muestra, por versión aprobada, lo programado, su costo, las corridas que lo simularon y las campañas de la vacunación.
- [x] Institución y región de cada cuenta en la administración de usuarios.
- [x] Ninguna gráfica sin fuente, periodo, modelo, versión y unidades. Ficha bajo cada gráfica.

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

Decidido con el líder (2026-11-22): `evidencias` pasa a ser el servicio de los archivos (fotos y reportes); la biblioteca oficial `google-cloud-storage`, que en GCP firma con signBlob de la cuenta de servicio de la máquina; y E8 de `evidencias` en este mismo trabajo.

- [x] Una interfaz de archivos en `epidemia_comun` que cambie de disco a bucket por configuración. La web también la usa (D35), y hoy no importa `epidemia_comun`: acordar con C dónde vive. `epidemia_comun/archivos.py` (`ARCHIVOS=disco|gcs`), con `tests/test_archivos.py`. La web no la importa: sube por HTTP a `evidencias`, así que usa la misma tabla y la misma interfaz (D35, D36). `/health` la usa para el bucket.
- [x] Emulador del bucket en el compose, para trabajar en local. `bucket` (`fake-gcs-server:1.56.1`) en `127.0.0.1:4443`, con el bucket `epidemia-archivos` y el volumen `bucket-datos`. Se retiró `docker-compose.fallos.yml`.
- [x] `evidencias` guarda en el bucket y deja de usar su volumen (RF-C03, RNF-B01). Sin `backend_web`: sus reglas pasaron a `microservicios/evidencias/datos.py` y su imagen parte de `base-vigilancia` (E8, `test_datos_sin_backend_web.py`).
- [x] URLs firmadas que vencen en minutos para los archivos privados (RNF-D17, RNF-D27). V4 de 15 minutos: `GET /api/v1/attachments/{id}/url` y `GET /api/v1/reports/{id}/url`, sin caché.
- [x] Validar cada archivo por su contenido, su tamaño y su huella al subirlo (RNF-C09). Tipo por contenido, hasta 20 MB y `X-Content-SHA256` (422 si no coincide); un reporte solo es PDF.
- [x] Tabla nueva con los metadatos de los reportes, y la ruta para subir uno (RF-F17). La usan el escritorio y la web (D35). Migración 039. `comparison_reports` (identificado por sus corridas) y `POST/GET /api/v1/reports`, `GET/DELETE /api/v1/reports/{id}`; contrato y ejemplos en `docs/contratos/evidencias/`.
- [x] Si el bucket no responde, el caso se guarda y la foto se reintenta (RNF-C19). La subida es 503 sin registro y `/health` sale degradado (`test_evidencias.py` y `test_compose_evidencias.py`, con el bucket detenido). Reintentar es de la app (B1).
- [x] Crear el bucket real en GCP, privado, con su cuenta de servicio (RNF-K12, RNF-K18). Con F (2026-11-23): `gs://integracion-515321-archivos`, la 039 aplicada en la máquina, y subir, leer, URL firmada y borrar probados desde `evidencias`; el acceso anónimo da 403. La máquina usa su propia cuenta, `epidemia-vm` (`storage.objectAdmin` solo sobre el bucket, `logging.logWriter`, `monitoring.metricWriter` y signBlob sobre sí misma), no la de Compute por omisión, que tiene Editor en el proyecto. `infra/crea_bucket.sh` la crea y DESPLIEGUE_GCP §2 y §6 la usan.

### D3. Volumen (D29, D-6)

- [x] Generar el conjunto de alto volumen: unas 10,000 corridas de 180 días. La cifra se confirma con el profesor (RNF-A17).
- [x] Medir el tiempo de inserción y el de consulta, con y sin índice.
- [x] Medir la consulta de resultados con y sin la caché de Redis (RNF-A09).
- [x] Medir CPU, memoria y disco durante la carga.
- [x] Escribir los resultados en `docs/`, con la forma de repetirlos. `docs/pruebas/volumen/2026-11-18` y `datos/scripts/volumen_mongo.py` (2026-11-18); la cifra sigue por confirmar con el profesor.

### D4. Documentos

- [x] Diseño de MongoDB y de los buckets en la arquitectura v3, con qué información va a PostgreSQL y cuál a MongoDB [Retro: MongoDB]. La parte de MongoDB está hecha (§6 y §9 de `arquitectura_v3.md`: criterio, tabla por dato, cómo se relacionan, consistencia y volumen medido). La de los buckets, con D2 (2026-11-22): §6, «Archivos en Cloud Storage».
- [x] Llenar la retención de cada dato en `matrices_v3.md`: hoy hay 48 «Por definir» (RNF-K07). Hechas las de MongoDB, `simulation_runs` y `simulation_results` (2026-11-18). Hecho el 2026-11-22 con D52 (la retención de hoy, sin purgas por antigüedad): §2 tiene vida y volumen en cada fila, más las 17 tablas y las llaves de Redis que faltaban, y `test_inventario_de_datos.py` revisa que no falte ninguna tabla.
- [x] Actualizar `docs/arquitectura/microservicios.md` con lo que cada servicio escribe ahora. Columna *Escribe* al día con los permisos de las migraciones (`test_catalogo_escribe_bd.py`), más el encabezado (D36, MongoDB, bucket y nginx), `pareto` sin `simulation_results`, el arranque de `simulador` (D38) y el diagrama.

### D5. MongoDB después de D1

[Retro: «MongoDB deberá incorporar referencias estables…» y «Fallo de worker»].

- [x] Cada documento de `series_corridas` trae `scenario_id`, además de `run_id`, `scenario_version_id` y la versión del motor. Hecho en `feat/bloque-D` (2026-11-18, `2ceadf8`); vale al integrarse el PR del bloque D.
- [x] La serie se guarda antes de confirmar la corrida: si el proceso muere entre los dos pasos, la corrida no queda completada sin curvas. Hecho en `feat/bloque-D` (2026-11-18, `2ceadf8`); vale al integrarse el PR del bloque D.
- [x] La serie de una corrida que el arranque cierra como fallida no se queda en MongoDB, o `banda()` la ignora. Va con la decisión de corridas interrumpidas (0). Las dos: el arranque borra la serie de las que cierra, y `banda(..., run_ids=)` cuenta solo las corridas que le pasen como completadas (D38).
- [ ] Con MongoDB caído y el simulador muerto después de confirmar, la serie se regenera con la misma semilla, comprobando la huella del escenario y el resumen. Va con la misma decisión.

### D6. Gestión de datos

[Retro: «Gestión de datos» del escritorio y validación científica].

- [x] Importar conjuntos de datos autorizados (CSV, JSON o XML), validarlos y registrar su fuente y su versión (RF-B08, reabierto). Lo usa el escritorio (A4). Hecho el 2026-11-22 con D53: el servicio `importacion` (n.º 31, puerto 5226) importa una serie agregada, solo `periodo_inicio` y `valor`, y la revisa: periodos seguidos, enfermedad, región, fuente, licencia y corte. La guarda como la versión siguiente de su clave; `/validate` revisa sin guardar. Importan EPIDEMIOLOGO, ANALISTA y ADMINISTRADOR (`datasets.upload`, no `datasets.import`: la 034 rehace el CHECK de acciones), con el alcance de D43. Contrato en `docs/contratos/importacion/`.
- [x] Guardar la serie observada que usan la validación y la calibración, con su fuente. D50 fija cuál es (casos de COVID-19 de NL de 2020 por inicio de síntomas, DGE, por semana) y que entra con la migración 061, generada por un script de `datos/scripts/`. Falta bajarla, confirmar la licencia y fijar el corte y la ventana (pasa del bloque 0 a D, 2026-11-22). Hecho el 2026-11-22. Viene del cierre anual 2020 de la DGE (corte 2021-10-31, con su SHA-256) y se publica como datos abiertos de libre uso citando la fuente (DOF 20-02-2015, art. 5). La ventana sale por regla: de la primera semana con casos al valle después del pico, del 2020-03-01 al 2020-07-26, 22 semanas y 22 259 casos. `datos/scripts/build_serie_observada.py` genera el CSV de `datos/observados/` y la 061; la 063 cambia el comentario de `cases`. Detalle en la §18 de la ficha y en D53.

### D7. Completar los servicios de catálogos y escenarios

[Retro: «Microservicios existentes que deben completarse y fortalecerse»]. Los servicios de D en [«Dueños de los servicios»](#dueños-de-los-servicios). La lista es lo que pide la retroalimentación, no lo que falta: lo que ya se cumpla se marca al revisarlo. Lo que dice «reabierto» o «hoy no existe» ya se revisó.

- [x] Revisar cada servicio contra su lista de la retroalimentación y marcar aquí lo que ya cumple. Hecho el 2026-11-23: [`revision_d7.md`](revision_d7.md), servicio por servicio, con lo que cumple, lo parcial y lo que falta, y lo que sigue por tamaño. Va en dos partes (decidido con el líder): Escenarios primero, lo que espera el escritorio, y Catálogos después, que necesita investigar fuentes.

**Catálogos**

- [ ] `enfermedades`: definiciones de caso versionadas.
- [ ] `parametros`: incertidumbre y versiones de cada parámetro.
- [ ] `regiones`: jerarquía (país, estado, municipio y área sanitaria), geometrías y búsqueda territorial.
- [ ] `poblacion`: versiones y periodos de referencia.
- [ ] `tipos-intervencion`: supuestos de efectividad de cada tipo.

**Escenarios**

- [x] `escenarios`: archivar (RF-D12, reabierto) y proyectos de investigación (la definición la proponen D y A; el bloque 0 la delegó el 2026-11-22). Hecho el 2026-11-23 con [D54](../../decisiones/D54-proyectos-y-archivado.md) y la migración 064. Un proyecto (`/projects`) agrupa escenarios de una enfermedad y una región, con objetivo, periodo y motores; un escenario entra con `PUT /scenarios/{id}/project` o al crearlo. Archivar (`/scenarios/{id}/archive` y `/restore`) lo deja de solo lectura: sin versiones, intervenciones, envíos ni corridas (la base las rechaza). Leen también INVESTIGADOR y AUTORIDAD_SANITARIA, con el alcance de D43. Falta la pantalla (A4).
- [x] Historial de un escenario: quién lo creó, modificó, revisó o aprobó (para A4). `roles` ya lo daba por entidad (`/audit/history`, D43). Desde el 2026-11-23, `GET /scenarios/{id}/versions` da además los responsables de cada versión: autor, envío, revisor, comentario, si se devolvió y su firma. Archivar y mover de proyecto quedan en la bitácora.
- [x] `aprobacion`: devolver una versión para cambios, además de rechazarla, y firmar la versión aprobada. Hecho el 2026-11-23 con [D55](../../decisiones/D55-devolver-y-firmar-versiones.md) y la migración 064. `decision: devolver` regresa la misma versión a borrador con el motivo (aviso `SCENARIO_RETURNED`). Al aprobar se guarda la firma: la huella de la entrada del motor que da `validacion`, la misma que guarda cada corrida. `GET /versions/{id}/signature` la verifica y la coteja con las corridas. De paso, `aprobacion` dejó `backend_web` (E8) y ya no se puede crear una versión con la vigente en revisión.

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

- [x] `auth`: MFA para los perfiles críticos (decisión del bloque 0). TOTP y códigos de respaldo en `microservicios/auth/mfa.py`, migración 051, D40. Salvedad: el MFA arranca apagado (`MFA_PERFILES` vacía) hasta que los clientes (web, escritorio, Android) implementen el flujo de segundo factor; se probó encendido a mano con ADMINISTRADOR y EPIDEMIOLOGO.  El bloqueo temporal ya existe (15 min, `backend_web/auth.py`).
- [x] `sesiones`: control de sesiones concurrentes y solo dispositivos autorizados (RF-A08, reabierto). Tope de sesiones y lista de dispositivos en `microservicios/sesiones/almacen.py` y `dispositivos.py`, migración 050, D41. Salvedad: el control de dispositivos autorizados viene apagado por omisión hasta que los clientes envíen `dispositivo_id`.
- [x] `usuarios`: institución y región de cada cuenta, y los perfiles nuevos (decisión del bloque 0). Migración 052, D42.
- [x] `roles`: permisos por recurso, región, institución y operación (decisión del bloque 0). Alcance por región en `microservicios/roles/rutas.py` y cliente `epidemia_comun/alcance.py`, migración 053, D43. Salvedad: el alcance por institución no se aplica a los datos de E porque estos no traen institución (D43); solo se aplica el de región.
- [x] Consultar la bitácora. La nota de que «hoy no existe» estaba desactualizada: `roles` ya la tenía (`/api/v1/audit`) y se extendió con resumen e historial de una entidad con alcance por región (migraciones 046, 053 y 055, D43). Probada en vivo: `GET /api/v1/audit?entity_id=130`.

**Simulación**

- [x] `corridas`: prioridades, tiempo estimado y reintentos seguros (RF-E07, RF-E08 y RF-E14, reabiertos). Prioridad, posición en la cola, estimación y `POST /runs/{id}/retry` en `microservicios/corridas/`, migración 054, D44. Salvedad: el reintento es solo manual; no hay reintento automático de corridas fallidas.
- [x] Una corrida interrumpida se recupera sin duplicar resultados, en lugar de cerrarse como fallida (RNF-C03; decisión del bloque 0). D38: el simulador la reencola con la misma semilla, hasta 3 intentos (migración 045, `attempts`); sin intentos o con otra versión de motor se cierra como `fallido`.
- [x] `resultados`: intervalos de incertidumbre de las réplicas, con la banda p5–p95 de `series_corridas` (D8, reabierto). `GET /api/v1/runs/{id}/band` en `microservicios/resultados/`. Salvedad: `replicas` cuenta las corridas completadas de la versión, no las que tienen series en MongoDB.
- [x] `comparacion`: diferencias absolutas y relativas, incertidumbre y análisis contrafactual exploratorio. En `microservicios/comparacion/rutas.py`; contrato y ejemplos actualizados. Es exploratorio y no recomienda un escenario (regla 10).
- [x] `pareto`: explica por qué cada alternativa queda dominada o no. Campo `explicacion` por fila en `microservicios/pareto/dominio.py`. Probado en vivo.
- [x] Rutas para la calibración y la sensibilidad (con el bloque 0). En `pareto`, D46. Salvedad: la calibración solo informa su estado (fuera de alcance, D24 y D46); la sensibilidad es exploratoria.
- [ ] Servicio `calibracion` (D50, pasa del bloque 0 a E el 2026-11-22): el algoritmo en `procesamiento/calibracion/` con su prueba sintética, la migración 062, la API y su trabajador, el contrato en `docs/contratos/calibracion/` y su contenedor. Lo espera el escritorio (A4).

### E8. Reglas de negocio y despliegue independiente

[Retro: «Dependencia de reglas de negocio compartidas con el monolito»]. Va con la decisión de dueños (D37).

- [x] Tabla de dueños: cada regla de negocio con el servicio que la posee. [`docs/arquitectura/duenos_de_reglas.md`](../../arquitectura/duenos_de_reglas.md) (D37). Las copias de `get_run`, `_sincroniza_lote` y la selección de corridas quedan documentadas ahí.
- [ ] Los servicios dejan de importar `backend_web`: cada regla vive con su dueño. Cada bloque lo hace en sus servicios (D, E y F). E hecho: ningún servicio de E importa `backend_web` (`test_sin_backend_web.py`, `test_simulacion_sin_backend_web.py`). F hecho el 2026-11-22: ninguno de sus nueve servicios lo importa y sus imágenes parten de `epidemia/base-vigilancia` (`test_vigilancia_sin_backend_web.py`); dispositivos, lotes de vacuna y avisos se mudaron de `backend_web` a su servicio, y lo que la web todavía lee (tablero, Monitoreo, mapa y captura) quedó como copia en el servicio dueño, igual a la del monolito (`test_copias_del_monolito.py`) hasta que la web consuma el servicio (D36). D: `evidencias` hecho el 2026-11-22 con D2 (sus reglas en `evidencias/datos.py`, imagen de `base-vigilancia`, `test_datos_sin_backend_web.py`), `importacion` nació sin él (D6) y `aprobacion` hecho el 2026-11-23 con D7 (`aprobacion/datos.py`). Sigue abierta por D: `enfermedades`, `escenarios`, `escenarios-xml`, `intervenciones`, `parametros`, `poblacion`, `regiones`, `tipos-intervencion` y `validacion` todavía lo importan, y `epidemia_comun/validaciones.py` espera a su dueño.
- [ ] `epidemia_comun` queda solo con funciones técnicas. Revisar `sesiones` y `series_corridas`. Parte de E hecha: las curvas de corridas pasaron a `simulador/serie.py` y `resultados/serie.py`, y abrir sesiones a `sesiones` (auth la llama por HTTP). `ambito.py` (F) ya solo lee y valida parámetros: los catálogos los consulta cada servicio (2026-11-22). Sigue abierta: `validaciones.py` pendiente de D, y quedan copias documentadas (`get_run`, `_sincroniza_lote`, entrada del motor).
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

- [x] `casos`: actualizar, dar seguimiento y rechazar, con historial, duplicados y control de conflictos (RF-C11 y RF-C15, reabiertos; decisión del bloque 0). Hecho el 2026-11-22 con [D47](../../decisiones/D47-correccion-y-seguimiento-de-casos.md) y la migración 057: `PATCH /cases/{id}` y `POST /cases/{id}/status` con `If-Match`, `GET /cases/{id}/history` y el aviso `CASE_REJECTED`. Falta la detección automática de duplicados probables ([`revision_f7.md`](revision_f7.md)).
- [x] Formularios por enfermedad, con versiones (para B4). Hecho el 2026-11-22 con [D48](../../decisiones/D48-formularios-por-enfermedad.md) y la migración 059: `/forms` para armarlos y publicarlos, `/forms/current` para la app, y cada caso con `form_id` y `form_answers` validadas contra su versión ([`revision_f7.md`](revision_f7.md)).
- [x] `sincronizacion`: conflictos entre lo capturado sin conexión y lo que cambió otro profesional. Hecho el 2026-11-22 (D47): el lote acepta `updates` y una corrección sobre un caso que cambió otra persona sale `conflicto` con el caso actual, sin sobrescribirlo. Mostrarlo en la app es de B4 ([`revision_f7.md`](revision_f7.md)).

**Analítica**

- [ ] `indicadores`: cada indicador con su numerador, su denominador y su periodo; capacidad utilizada, con su fuente (RF-G07, reabierto). Desde el 2026-11-21, cada indicador trae su numerador, su denominador y su periodo, más mortalidad, letalidad y casos graves (`indicadores` en `/dashboard/indicators`). Faltan capacidad utilizada (sin fuente), hospitalizaciones (no hay el dato) y prevalencia ([`revision_f7.md`](revision_f7.md)).
- [x] `series`: filtrado, paginación y agregaciones por enfermedad, periodo, región y grupo. Hecho el 2026-11-21: `/series/cases/aggregate` con rango libre, agregación por día, semana epidemiológica o mes, grupos (sexo, edad, enfermedad, municipio) y paginación, y `/series/cases/highcharts` con la misma serie para Highcharts ([`revision_f7.md`](revision_f7.md)).
- [x] `zonas`: mapas de calor y agrupaciones territoriales. Hecho el 2026-11-21: `/zones/heatmap` (celdas de ~1 km como mínimo, sin celdas de menos de 3 casos) y `/zones/jurisdictions` (por jurisdicción sanitaria, del Reglamento Interior de Servicios de Salud de NL; falta confirmar con la Secretaría que siga vigente). La geometría oficial de los municipios también, desde el 2026-11-22: `/zones/geometry` (GeoJSON de INEGI) y `/zones/locate` (municipio y jurisdicción de un punto); falta que el escritorio la dibuje (A4) ([`revision_f7.md`](revision_f7.md)).

**Plataforma**

- [x] `notificaciones`: avisos de campañas, de datos incompletos y de errores operativos. Hecho: errores operativos el 2026-11-21 (`SYSTEM` desde `estado-servicios`) y, el 2026-11-22 con [D49](../../decisiones/D49-campanas-incompletos-y-preferencias.md) y la migración 060, campañas (`CAMPAIGN`, desde `vacunas`), datos incompletos (`DATA_INCOMPLETE`, desde `casos`) y preferencias por persona ([`revision_f7.md`](revision_f7.md)).
- [x] `estado-servicios`: capacidad de procesamiento (la cola de cada motor). Hecho el 2026-11-21: `GET /api/v1/services/capacity` da por motor las corridas en cola (por prioridad, D44) y los simuladores vivos, ocupados y libres, con el latido que cada simulador renueva en Redis (`worker:<motor>:<simulador>`), también el de `abm-gpu` de la PC. Alertas técnicas, también el 2026-11-21: un servicio que cae, se degrada o se recupera durante 30 s manda un aviso `SYSTEM` a los ADMINISTRADOR por `notificaciones` ([`revision_f7.md`](revision_f7.md)).

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
