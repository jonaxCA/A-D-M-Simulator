> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# Historias de usuario

Una historia por paso de [`procesos_v3.md`](../arquitectura/procesos_v3.md): la historia es el paso visto desde quien lo hace, y su criterio de aceptación sale de las columnas *Escribe en*, *Auditoría* y *Notifica a*. El número de la historia es el del paso. Al final van las de las funciones de soporte.

Un criterio describe cómo debe quedar; lo que todavía falta está en el estado de cada requerimiento.

## P1 · Captura en campo

| ID | Como | quiero | para | Criterio de aceptación | Requerimientos |
|---|---|---|---|---|---|
| HU-1.1 | CAPTURISTA | entrar a la app con mi usuario, mi contraseña y un captcha | que solo yo registre casos con mi cuenta | Entro con datos correctos y la app guarda los tokens cifrados; con datos incorrectos no entro. Queda `LOGIN` o `LOGIN_FAILED` en la auditoría | RF-A01, RF-I01, RF-I13 |
| HU-1.2 | CAPTURISTA | que mi teléfono quede registrado a mi cuenta | que nadie envíe casos a mi nombre desde otro teléfono | El teléfono queda en `devices`, uno por cuenta; queda `CREATE` o `UPDATE` en la auditoría | RF-A09, RF-I14 |
| HU-1.3 | CAPTURISTA | tener las enfermedades y los municipios en el teléfono | llenar el formulario sin conexión | Los catálogos se descargan y el formulario los ofrece sin red | RF-B01, RF-B02, RF-I17 |
| HU-1.4 | CAPTURISTA | registrar un caso con su ubicación aunque no tenga señal | no perder casos en campo | El caso queda pendiente con su `local_uuid` y su ubicación. Un campo inválido no deja guardar | RF-C01, RF-C02, RF-C06, RF-C07 |
| HU-1.5 | CAPTURISTA | tomar fotos del caso | dejar evidencia | Las fotos se reducen a 1600 px, pierden el EXIF y quedan por subir | RF-C03, RF-I05 |
| HU-1.6 | CAPTURISTA | que los casos se manden solos cuando vuelve la red, y ver qué pasó con cada uno | no tener que acordarme de enviarlos | Los casos se crean en `cases` sin duplicarse, con `SYNC` y `CREATE` en la auditoría. La app muestra enviados, rechazados y pendientes. Se avisa a los EPIDEMIOLOGO, una vez por lote | RF-C08, RF-C09, RF-C10, RF-C12, RF-C14, RF-C19 |
| HU-1.7 | CAPTURISTA | que las fotos se suban cuando el caso ya existe | que la evidencia quede con su caso | `case_attachments` guarda los metadatos, con `CREATE` en la auditoría, y el archivo va al bucket | RF-C03 |
| HU-1.8 | CAPTURISTA | leer el QR o el código de barras de un lote de vacuna y aplicarle dosis | llevar la cuenta de las dosis sin escribir el lote a mano | El lote se da de alta y `doses_used` sube, con `CREATE` y `UPDATE` en la auditoría. No se pasa de las dosis del lote | RF-C04, RF-C05, RF-C13 |
| HU-1.9 | EPIDEMIOLOGO | ver los casos nuevos en el tablero y en el mapa | saber qué está pasando en campo | El tablero cuenta pendientes y validados, y el mapa los muestra por municipio. La foto se abre con una URL firmada | RF-G01, RF-G03, RF-C20 |

## P2 · Diseño y aprobación de escenarios

| ID | Como | quiero | para | Criterio de aceptación | Requerimientos |
|---|---|---|---|---|---|
| HU-2.1 | ANALISTA | entrar a la app de escritorio con captcha | trabajar mis escenarios | Solo entran ANALISTA y ADMINISTRADOR; queda `LOGIN` o `LOGIN_FAILED` en la auditoría | RF-A01, RF-H01 |
| HU-2.2 | ANALISTA | buscar un escenario y abrirlo con sus versiones e intervenciones | retomar mi trabajo | La búsqueda filtra la lista y el detalle muestra las versiones y su estado | RF-H02 |
| HU-2.3 | ANALISTA | crear un escenario, una versión nueva o un duplicado | probar una variante sin perder la anterior | Nace en `borrador`; queda `CREATE` de `scenarios` o de `scenario_versions` en la auditoría | RF-D01, RF-D04, RF-D08 |
| HU-2.4 | ANALISTA | agregar, quitar y mover intervenciones sobre la línea de tiempo | armar la estrategia que quiero simular | El formulario sale del `param_schema` del tipo; quedan `CREATE`, `DELETE` y `UPDATE` en la auditoría | RF-D02, RF-H03, RF-H04 |
| HU-2.5 | ANALISTA | validar la versión antes de enviarla | no mandar a revisión algo que el motor no acepta | Recibo la lista de errores, o que no hay | RF-D03, RF-B10 |
| HU-2.6 | ANALISTA | exportar una versión a XML e importar un XML | intercambiar escenarios con otras personas | El archivo valida contra `escenario.xsd` en la app y en el servidor; al importar queda `CREATE` en la auditoría | RF-D06, RF-D07, RF-H05 |
| HU-2.7 | ANALISTA | enviar mi versión a revisión | que un epidemiólogo la apruebe | La versión pasa a `en_revision`, con `UPDATE` en la auditoría, y se avisa a los EPIDEMIOLOGO | RF-D15 |
| HU-2.8 | EPIDEMIOLOGO | ver en la web las versiones por revisar y aprobarlas o rechazarlas con un comentario | que solo se simule lo que tiene sentido | La versión pasa a `aprobado` o `rechazado`, con `UPDATE` en la auditoría. No puedo revisar la mía. Se avisa al autor | RF-D16, RF-D13 |
| HU-2.9 | ANALISTA | ver el aviso y el estado de mi versión | saber si ya puedo lanzar corridas | El aviso aparece en la app y se marca como leído | RF-D17, RF-H15 |

## P3 · Simulación y comparación

| ID | Como | quiero | para | Criterio de aceptación | Requerimientos |
|---|---|---|---|---|---|
| HU-3.1 | ANALISTA | lanzar N réplicas de cada versión aprobada, con el motor que elija | comparar escenarios con las mismas semillas | Las corridas quedan `encolado`, con semillas 1 a N, y queda `RUN` en la auditoría. Una versión sin aprobar no se lanza | RF-E01, RF-E02, RF-E03, RF-E04, RF-E09, RF-E15, RF-H07 |
| HU-3.2 | ANALISTA | que las corridas se ejecuten en segundo plano | seguir trabajando mientras tanto | El simulador guarda el resumen y la serie, anota `RUN` al empezar y al cerrar, y me avisa al terminar o fallar | RF-E05, RF-E11, RF-E12, RF-E20 |
| HU-3.3 | ANALISTA | seguir el avance de mis corridas y cancelar las que no necesito | no esperar corridas inútiles | Veo el avance de cada una; al cancelar queda `cancelado`, con `CANCEL` en la auditoría | RF-E05, RF-E06, RF-H08 |
| HU-3.4 | ANALISTA | ver el aviso de que terminaron mis corridas | saber cuándo puedo comparar | El aviso aparece en la app y se marca como leído | RF-E11, RF-H15 |
| HU-3.5 | ANALISTA | comparar las versiones: su costo, sus curvas con banda y la frontera | ver qué opciones hay y cuánto cuestan | Se resumen media, mediana y p5–p95 de las semillas comunes, y la frontera va sobre medianas. Se ve el aviso de que no es una predicción, y no se recomienda ninguna | RF-F05, RF-F06, RF-F07, RF-F08, RF-H10, RF-H11, RF-F19 |
| HU-3.6 | ANALISTA | exportar el reporte a CSV y PDF, o imprimirlo, y compartirlo | entregarlo a quien decide | El reporte se guarda; con el bucket, se sube y se comparte con una URL firmada, y la exportación queda en la auditoría | RF-F09, RF-F11, RF-F17, RF-H13 |
| HU-3.7 | EPIDEMIOLOGO | consultar en la web una corrida y sus curvas | revisar los resultados sin la app de escritorio | Veo el resumen y las curvas, con el aviso de que no es una predicción. No puedo lanzar corridas desde la web | RF-F21, RF-F01, RF-F04, RF-G02 |

## Funciones de soporte

| ID | Como | quiero | para | Criterio de aceptación | Requerimientos |
|---|---|---|---|---|---|
| HU-S1 | ADMINISTRADOR | crear cuentas, asignarles su rol y desactivarlas | que cada persona tenga solo el acceso que le toca | Solo yo puedo hacerlo; cada cambio queda en la auditoría | RF-L01, RF-L02 |
| HU-S2 | ADMINISTRADOR | consultar la bitácora de auditoría | saber quién hizo qué y cuándo | Solo yo la veo | RF-L05 |
| HU-S3 | ADMINISTRADOR | revocar un teléfono o cerrar las sesiones de una cuenta | cortar el acceso de un teléfono perdido | El teléfono deja de sincronizar y la siguiente petición de esa cuenta responde 401 | RF-L03, RF-L04 |
| HU-S4 | EPIDEMIOLOGO | dar de alta enfermedades y fijar sus parámetros y los costos, cada uno con su fuente | que las simulaciones no usen cifras inventadas | Un dato sin fuente ni marca de supuesto impide simular | RF-B01, RF-B09, RF-B11 |
| HU-S5 | Integrante del equipo | ver en un panel qué servicio está caído y por qué | encontrar una falla sin entrar a cada contenedor | El panel muestra el estado, la latencia, las dependencias caídas y el historial de cada servicio | RF-K02, RF-K03, RF-K05 |
| HU-S6 | Visitante | ver los indicadores generales sin iniciar sesión | enterarme de la situación | La página pública muestra datos agregados, sin ningún caso individual | RF-J01, RF-J03 |
| HU-S7 | CAPTURISTA | cerrar sesión sin perder lo que no he enviado | prestar o guardar el teléfono con tranquilidad | Se borran los tokens; los casos pendientes se quedan y se mandan cuando vuelvo a entrar | RF-I21 |
