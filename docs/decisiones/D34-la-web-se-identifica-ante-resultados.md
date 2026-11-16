# D34 - La web se identifica ante `resultados` con el JWT de la sesión

Fecha: 2026-11-16 · Estado: Aceptada (tomada por el orquestador; pendiente de validación del equipo)

## Contexto
D20 (excepción por D28) hace que la web pida las curvas de una corrida a `resultados`, pero no dice con qué identidad. `resultados` exige un JWT con `iss`, `aud`, `nbf`, `sid` y `jti`, y revisa la sesión y la revocación en Redis.

## Opciones consideradas
- Una cuenta de servicio de la web, con su token interno y un secreto nuevo.
- Reenviar el JWT de la sesión del usuario.

## Decisión
La web reenvía el JWT de la sesión del usuario (el mismo que firma con `sid` y `jti` y registra en Redis desde I3) en `Authorization: Bearer`. Para que los servicios lo acepten, el token de la web lleva además `iss` (`JWT_ISSUER`), `aud` (`JWT_AUDIENCE`) y `nbf`, con los mismos valores por omisión que los servicios.

## Consecuencias
- `resultados` aplica los permisos del rol del usuario y la revocación funciona igual; no hay secreto nuevo.
- Las cookies emitidas antes de este cambio no traen `aud`: quien las tenga debe entrar de nuevo.
- Si `resultados` no responde o contesta 5xx, la web lee la serie de PostgreSQL (I2). Un 403 se trata como acceso denegado, sin respaldo; un 401 (sesión inválida) manda a iniciar sesión de nuevo.
- Cliente: `backend_web/resultados.py`; variables `SERVICIO_RESULTADOS_URL` y `SERVICIO_RESULTADOS_TIMEOUT`.
