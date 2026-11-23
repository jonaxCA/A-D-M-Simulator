# D49 - Campañas, avisos de datos incompletos y preferencias de avisos

Fecha: 2026-11-22 · Estado: Aceptada · Atiende la retroalimentación de `notificaciones` (campañas, datos incompletos, alertas configurables por perfil) · Amplía D1, D32 y D47

## Contexto
La retroalimentación pide que `notificaciones` avise de campañas y de datos incompletos, y que las
alertas sean configurables por perfil. No había campañas (`vacunas` solo lleva lotes y dosis), ningún
servicio avisaba de casos con datos faltantes y cada aviso le llegaba a todos los de su rol sin
poder apagarlo.

## Opciones consideradas
- Campañas: A) en `vacunas`, sin coberturas; B) el servicio opcional de vacunación completo, con
  coberturas y poblaciones objetivo.
- Datos incompletos: A) un aviso por captura o por lote a quien capturó, y una lista para el panel
  de la app; B) un resumen periódico.
- Preferencias: A) cada persona apaga los tipos de aviso que le tocan por su perfil; B) el
  ADMINISTRADOR fija por rol qué tipos recibe cada perfil.

## Decisión
- **Campañas (A).** `campaigns` (migración 060), en `vacunas`: nombre, enfermedad, municipio de
  Nuevo León o todo el estado, fechas, población objetivo (opcional) y descripción. Las crean, editan
  y cancelan (con motivo) el EPIDEMIOLOGO y el ADMINISTRADOR, los que dan de alta enfermedades (D1);
  las consultan los cuatro roles. Su estado sale de las fechas: programada, activa, terminada, o
  cancelada. Una cancelada o terminada no cambia. Al crear o cancelar una, los CAPTURISTA reciben un
  aviso `CAMPAIGN`. Sin coberturas: eso es el servicio opcional de vacunación (B, fuera de alcance).
- **Datos incompletos (A).** A un caso le faltan datos si no trae edad, sexo, inicio de síntomas,
  resultado, gravedad o ubicación (ninguno es obligatorio). Quien lo capturó recibe un aviso
  `DATA_INCOMPLETE` con lo que falta: uno por captura y uno por lote (como `NEW_CASES`, D32), nunca
  en un reintento. `GET /cases/incomplete` da sus casos incompletos (los de todos, a los demás roles)
  para el panel de la app; se completan con la corrección de D47.
- **Preferencias (A).** `notification_preferences`: cada persona apaga o prende los tipos de aviso
  que le llegan por su perfil (`GET` y `PUT /notifications/preferences`). `notificaciones` no crea un
  aviso apagado (a una persona responde 200 con `omitida`; a un rol, se salta a quien lo apagó).
  `SYSTEM`, las alertas técnicas del ADMINISTRADOR, no se apaga.
- Migración 060: las dos tablas, los tipos `CAMPAIGN` y `DATA_INCOMPLETE`, y los permisos de
  `svc_vacunas` y `svc_notificaciones`.

## Consecuencias
- `notificaciones` acepta avisos al rol CAPTURISTA; `vacunas` llama a `notificaciones`.
- Capturar casos sueltos sin esos datos manda un aviso por caso (por lote, uno solo): quien no los
  quiera los apaga en sus preferencias.
- Las apps pueden mostrar las campañas, el panel de incompletos y la pantalla de preferencias;
  ninguna lo hace todavía (B4 para la móvil).
- Coberturas, poblaciones objetivo por grupo y metas de una campaña quedan para el servicio opcional
  de vacunación.
