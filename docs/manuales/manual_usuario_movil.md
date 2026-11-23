# Manual de usuario · App móvil EPIDEMIA

> **Estado: Vigente** · 2026-11-22 · Corresponde a la app Android de `frontend_movil/` del tercer parcial (RNF-E08).

## 1. Para qué sirve

Con la app, el personal de campo (CAPTURISTA) registra los casos que encuentra, aunque no haya
señal. Los casos se guardan en el teléfono y se envían solos en cuanto hay conexión. La app
también lee los lotes de vacuna por su código, aplica dosis y muestra los avisos de la cuenta.

| Rol | Qué ve en la app |
|---|---|
| Capturista | Capturar casos, mis casos y su seguimiento, campañas, lotes de vacuna (registrar y aplicar), consulta por zona, avisos y perfil |
| Epidemiólogo y autoridad sanitaria | Casos (los de tu alcance, para consultarlos), campañas, lotes de vacuna (solo consultar), consulta por zona, avisos y perfil. Validar o descartar casos se hace en la web |
| Administrador | Lo mismo que el epidemiólogo, y además registra lotes y aplica dosis. No captura: los casos los registra solo el capturista |
| Analista e investigador | Consulta por zona, avisos y perfil |

**El inicio** es tu panel: cuántos casos faltan por enviar, cuántos tienen datos por completar,
cuántos avisos sin leer tienes y cuántas enfermedades tienen formulario propio en el teléfono.

## 2. Antes de empezar

- Android 7.0 o más nuevo.
- Una cuenta del sistema. En la demostración: usuario `karla.trevino`, contraseña `Epidemia2026!`.
- La app pide permisos solo cuando los necesita: la red local al abrirla (Android 17), la
  ubicación al agregarla a un caso, la cámara para fotos y lotes, y las notificaciones en la
  pantalla de avisos. Si niegas uno, la app sigue y te dice qué no puede hacer.

**El indicador de conexión.** Arriba de todas las pantallas hay una franja que dice «Con conexión»
o «Sin conexión». Sin conexión puedes capturar casos; consultar lotes, aplicar dosis y ver avisos
necesita red.

## 3. Iniciar y cerrar sesión

1. Escribe tu **Usuario** y **Contraseña**.
2. Contesta la pregunta del captcha (por ejemplo, `3 + 5`) en **Respuesta**. Si no la entiendes,
   toca **Otra pregunta**.
3. Toca **Entrar**.

La sesión dura 8 horas. **Mi perfil** dice a qué hora vence; después hay que volver a entrar.

Para salir: **Mi perfil** › **Cerrar sesión**. Los casos que no se han enviado **no se borran**:
antes de salir la app te dice cuántos quedan, y se envían la próxima vez que entres con tu cuenta. Otra
persona que entre en el mismo teléfono no los ve.

## 4. Capturar un caso

En el inicio, **Capturar caso**.

1. Elige la **enfermedad** y el **municipio**, y revisa la **Fecha de reporte** (es hoy por omisión).
2. Lo demás es opcional: **Inicio de síntomas**, **Edad**, **Sexo**, resultado de la prueba y severidad.
   Si la enfermedad tiene formulario propio (por ejemplo, días con fiebre o signos de alarma), sus
   campos aparecen debajo; los que no dicen «(opcional)» son obligatorios.
3. **Agregar mi ubicación** lee el GPS, que funciona sin red. Se ven las coordenadas y su
   precisión; **Quitar ubicación** la borra. Si el GPS no conviene, **Escribir las coordenadas**
   deja poner la latitud y la longitud a mano.
4. **Tomar foto** o **De la galería** agregan hasta cinco fotos. La app las reduce y les quita
   los datos de ubicación antes de guardarlas.
5. Toca **Guardar caso**. Verás «Caso guardado. Se envía en cuanto haya conexión.»

La app revisa lo mismo que el servidor: fechas que no estén en el futuro, el inicio de síntomas
antes del reporte, la edad de 0 a 120 años y los campos del formulario. Además:

- Si faltan datos importantes (edad, sexo, inicio de síntomas, resultado, gravedad o ubicación),
  te lo dice; puedes guardarlo así y completarlo después.
- Si ya hay en el teléfono un caso de la misma enfermedad, municipio, fecha, edad y sexo, te avisa
  de un posible duplicado. Si es otro caso, toca **Es otro caso: guardarlo**.

Los datos de salud del caso se guardan cifrados en el teléfono.

La primera vez, el teléfono necesita los catálogos de enfermedades y municipios. Se bajan solos
al abrir el inicio con conexión; si nunca los tuvo, la captura ofrece **Descargar catálogos**.

## 5. Mis casos

Lista los casos de tu cuenta en este teléfono:

| Estado | Qué quiere decir | Qué hacer |
|---|---|---|
| Por enviar | Guardado en el teléfono, todavía no llega al servidor | Nada: se envía solo con red. **Enviar ahora** lo intenta de inmediato |
| Recibido · caso N | El servidor lo recibió con el número N. Del teléfono se borran la edad, el sexo, el resultado, la severidad y la ubicación | Tócalo para ver su seguimiento |
| Rechazado | El servidor no lo aceptó; se muestra el motivo | Captúralo de nuevo corregido y toca **Descartar** en el rechazado |

También dice cuántas fotos van subidas, por subir o rechazadas. Arriba, en **Les faltan datos**,
salen los casos tuyos a los que el servidor les marca algo por completar (necesita red).

### Seguimiento de un caso

Al tocar un caso recibido ves lo que tiene el servidor: si está **Recibido, por validar**,
**Validado**, **Descartado** o **Duplicado** (con el motivo), sus datos y su historial de cambios.
Validar o descartar lo hace el epidemiólogo.

Mientras esté por validar, puedes tocar **Corregir datos**, cambiar lo que esté mal, escribir el
motivo y **Guardar**. Necesita conexión. Si otra persona lo cambió mientras tanto, la app no lo
sobrescribe: te avisa y te muestra cómo quedó, para que decidas.

En **Fotos** están las que el caso tiene en el servidor. **Ver** la baja y la muestra; necesita
conexión y no se guarda en el teléfono. Los documentos PDF se abren en la web.

## 6. Consulta por zona

En el inicio, **Consulta por zona**. Elige una enfermedad (o ninguna, para todas) y el periodo de 7,
30 o 90 días: ves por municipio los casos, la incidencia por 100 mil habitantes, los graves y su
nivel. Necesita conexión.

## 7. Lotes de vacuna

En el inicio, **Lotes de vacuna**. Necesita conexión.

1. Apunta la cámara al QR o al código de barras de la caja, o escríbelo en **O escribe el código**
   y toca **Buscar lote**.
2. Si el lote existe, ves la enfermedad, el fabricante, la caducidad y cuántas dosis quedan.
   Elige cuántas aplicar y toca **Aplicar**. Un lote caducado o sin dosis no deja aplicar.
3. Si no existe, captura los datos de la caja y toca **Registrar lote**.

Si la respuesta no llega al aplicar dosis, la app no lo reintenta sola: no se sabe si el servidor
ya las descontó. Te pide revisar las dosis del lote antes de volver a intentarlo.

## 8. Avisos

En el inicio, **Avisos** dice cuántos hay sin leer. Tocar uno lo marca como leído; **Marcar
leídos** marca todos. La app revisa cada 15 minutos si hay avisos nuevos y, si diste el permiso,
muestra una notificación. Los tipos son, entre otros, «Casos nuevos», «Versión por revisar»,
«Versión aprobada», «Versión rechazada», «Caso descartado», «Campaña» y «Datos incompletos».

## 9. Mi perfil

Muestra tu nombre, usuario, correo, rol, institución, región asignada, estado de conexión, último
inicio de sesión, la hora a la que vence la sesión y el número de este teléfono. Al tocar **Cerrar sesión** con casos sin enviar, avisa cuántos
son antes de salir. Si el teléfono no quedó registrado al
entrar, ofrece registrarlo: hasta hacerlo, los casos no quedan ligados a este teléfono.

## 10. Problemas frecuentes

| Ves | Qué pasa | Qué hacer |
|---|---|---|
| «Sin conexión» arriba | El teléfono no tiene red | Captura igual; se envía al volver la red |
| «El captcha es incorrecto o venció. Pide uno nuevo.» | La respuesta no coincide o tardaste mucho | Toca **Otra pregunta** |
| «Se cerró tu sesión…» en la pantalla de entrada | La sesión venció, la cerraron en otro lado o revocaron el teléfono | Entra de nuevo; tus casos pendientes siguen ahí |
| «El caso cambió desde que lo leíste…» | Otra persona lo corrigió o lo revisó mientras lo editabas | Revisa cómo quedó y corrige otra vez si hace falta |
| Un caso «Rechazado» | El servidor no aceptó un dato | Lee el motivo, captúralo corregido y descarta el rechazado |
| «No llegó la señal del GPS…» | No hay señal de satélite | Intenta a cielo abierto, o guarda el caso sin ubicación |
| «No se pudo confirmar si se aplicaron…» | Se cortó la respuesta al aplicar dosis | Revisa las dosis del lote antes de volver a aplicar |

La app nunca muestra errores técnicos: siempre dice qué pasó y qué puedes hacer (RF-I22).
