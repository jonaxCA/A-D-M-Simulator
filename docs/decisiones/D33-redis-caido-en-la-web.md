# D33 - Redis caído en la web

Fecha: 2026-11-16 · Estado: Aceptada (tomada por el orquestador; pendiente de validación del equipo)

## Contexto
La web consulta Redis en cada petición para saber si la sesión sigue abierta y si el token fue revocado (I3). Los servicios fallan cerrados cuando Redis no responde (503), pero la web debe seguir funcionando (I2).

## Opciones consideradas
- Fallar cerrada: sin Redis, la web no deja entrar ni a quien ya tiene sesión.
- Aceptar las sesiones ya abiertas y negar los inicios de sesión nuevos.

## Decisión
Con Redis caído, la web acepta las sesiones ya abiertas (no puede verificar la revocación y lo registra en el log), pero no permite iniciar sesión y muestra un mensaje amable.

## Consecuencias
La web conserva su independencia de Redis (I2). Mientras dure la caída, un token revocado puede seguir valiendo hasta que Redis vuelva o venza el token.

**Riesgo aceptado:** si alguien cierra sesión con Redis caído, la cookie se borra pero no se puede revocar la sesión ni el `jti`; al volver Redis, ese token copiado sigue valiendo hasta que venza (`TOKEN_TTL_MINUTES` = 480 min, 8 horas, en `backend_web/auth.py`). No se añade código: la caída de Redis es excepcional y la ventana está acotada por el vencimiento. Se prueba a mano en la demostración de caídas (`infra/demo_fallos.py redis`, con `DEMO_WEB_URL`).
