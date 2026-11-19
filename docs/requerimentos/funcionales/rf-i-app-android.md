> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-I: Aplicación Android

La app de `frontend_movil/` atiende el proceso **P1** de [`procesos_v3.md`](../../arquitectura/procesos_v3.md) para el CAPTURISTA. Solo habla JSON con los microservicios. Lo que captura está en [RF-C](rf-c-vigilancia.md); aquí va lo que es propio de la app. Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- RF-A, RF-B y RF-C.
- 11 servicios: `estado-servicios`, `auth`, `sesiones`, `usuarios`, `dispositivos`, `enfermedades`, `regiones`, `sincronizacion`, `evidencias`, `vacunas` y `notificaciones`.
- Del teléfono: cámara, GPS, lector de QR y de código de barras, notificaciones, almacenamiento local y sincronización en segundo plano.

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-I01 | La app inicia sesión con usuario, contraseña y captcha, y renueva la sesión sola | Hay una sola renovación a la vez, aunque varias peticiones fallen juntas | 1.1 | Móvil, Seguridad | Alta | Hecho |
| RF-I02 | La app lista los casos guardados en el teléfono | Se ven los pendientes, los enviados y los rechazados | 1.6 | Móvil | Alta | Hecho |
| RF-I03 | La app tiene un formulario de captura con validación local | Ver RF-C01 y RF-C06 | 1.4 | Móvil | Alta | Hecho |
| RF-I04 | La app toma la ubicación del GPS | Ver RF-C02 | 1.4 | Móvil | Alta | Hecho |
| RF-I05 | La app toma fotos con la cámara | Ver RF-C03 | 1.5 | Móvil | Alta | Hecho |
| RF-I06 | La app lee QR y códigos de barras | Ver RF-C04 y RF-C05 | 1.8 | Móvil | Media | Hecho |
| RF-I07 | La app funciona sin conexión: captura, guarda y deja en cola | Ver RF-C07 | 1.4, 1.5 | Móvil | Alta | Hecho |
| RF-I08 | La app sincroniza en segundo plano cuando hay red (WorkManager) | Un reintento manda el mismo lote. Ver RF-C08 y RF-C09 | 1.6 | Móvil | Alta | Hecho |
| RF-I09 | La app consulta los avisos del usuario y los marca como leídos | Abrir un aviso lo marca como leído en `notificaciones`. No hay notificaciones push | Soporte | Móvil | Media | Hecho |
| RF-I10 | La app muestra el estado de envío de cada caso | Ver RF-C14 | 1.6 | Móvil | Alta | Hecho |
| RF-I13 | La app guarda los tokens cifrados | Se cifran con una llave del Keystore. La base local no entra en los respaldos del teléfono ni pasa a otro | 1.1 | Móvil, Seguridad | Alta | Hecho |
| RF-I14 | La app registra el teléfono al iniciar sesión | Si no quedó registrado, se registra antes de enviar. Ver RF-A09 | 1.2 | Móvil | Alta | Hecho |
| RF-I15 | La app no conserva datos de salud que ya envió | De un caso enviado queda solo el comprobante: enfermedad, municipio, fecha y `case_id`. La edad, el sexo, el resultado, la severidad y la ubicación se borran | 1.6 | Móvil, Seguridad | Media | Hecho |
| RF-I16 | Una cuenta usa un solo teléfono | Ver RF-A09 | 1.2 | Móvil | Media | Hecho |
| RF-I17 | La app descarga los catálogos que usa el formulario | Enfermedades y regiones quedan en el teléfono y sirven sin conexión | 1.3 | Móvil | Alta | Hecho |
| RF-I18 | La app muestra el perfil del usuario | Se ven el nombre, el rol y cuántos casos faltan por enviar | Soporte | Móvil | Alta | Hecho |
| RF-I19 | El menú depende del rol | Un rol distinto del CAPTURISTA no ve la captura | Soporte | Móvil, Seguridad | Alta | Hecho: los roles del login quedan con la sesión; sin CAPTURISTA, el inicio no muestra «Capturar caso» ni «Mis casos» (`InicioViewModelTest`) |
| RF-I20 | La app tiene un indicador de conexión fijo | Se ve en todas las pantallas si hay red o no | Soporte | Móvil | Alta | Hecho: una franja arriba de todas las pantallas dice «Con conexión» o «Sin conexión» (`ui/navegacion/IndicadorConexion.kt`) |
| RF-I21 | La app cierra la sesión y borra las credenciales | Al cerrar o perder la sesión se borran los tokens. Los casos sin enviar se quedan y se mandan cuando esa cuenta vuelve a entrar; otra cuenta en el mismo teléfono no los ve (D19) | Soporte | Móvil, Seguridad | Alta | Hecho |
| RF-I22 | La app muestra los errores con un mensaje entendible | Sin red, un rechazo del servidor o una sesión vencida se explican sin cerrar la app | Todos | Móvil | Alta | Verificar: ningún paso lo describe |

«Actualización de información», que pide la rúbrica, se cumple con aplicar dosis (RF-C13) y marcar avisos como leídos (RF-I09), según D32.

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-I11 | Filtrar los casos capturados por fecha, zona o estado | Ningún paso lo pide |
| RF-I12 | Editar un caso pendiente o reciente | D32: la app no edita casos |
| — | Notificaciones push | `notificaciones` solo se consulta; no hay envío |
