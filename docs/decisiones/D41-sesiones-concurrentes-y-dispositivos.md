# D41 - Sesiones concurrentes y dispositivos autorizados

Fecha: 2026-11-20 · Estado: Aceptada (tomada por el orquestador; pendiente de validación del líder) · Reabre RF-A08 (antes fuera de alcance) · Amplía D1

## Contexto
La retroalimentación pide limitar las sesiones concurrentes y aceptar solo dispositivos autorizados. RF-A08 había quedado fuera de alcance porque ningún proceso lo pedía.

## Opciones consideradas
- Opción A: solo el tope de sesiones.
- Opción B: tope de sesiones y lista de dispositivos autorizados por cuenta, con la autorización a cargo del usuario o de un `ADMINISTRADOR`.

## Decisión
Opción B.

- **Tope:** como máximo `MAX_SESIONES_POR_USUARIO` sesiones activas por cuenta. **Supuesto**, sin fuente: 3 por omisión, configurable. Al abrir una nueva por encima del tope se cierra la más antigua (su access y su refresh dejan de servir).
- **Dispositivo:** cada login envía `dispositivo_id`, un identificador estable que genera el cliente (de 8 a 128 caracteres) y, opcionalmente, `dispositivo_etiqueta`. En la base solo se guarda su SHA-256, en `session_devices`; no se mezcla con `devices` (teléfonos que sincronizan, RF-A09).
- **Estados:** `pendiente`, `autorizado`, `revocado`. El primer dispositivo de una cuenta nace `autorizado` (si no, nadie podría autorizar el primero); los siguientes nacen `pendiente` y el login responde 403 `DISPOSITIVO_NO_AUTORIZADO`. Un `revocado` sigue rechazado.
- **Quién autoriza:** la persona, desde una sesión abierta en un dispositivo autorizado (se comprueba: una sesión sin dispositivo o con uno no autorizado recibe 403 `DISPOSITIVO_NO_AUTORIZADO`, así un token robado no autoriza ni revoca), o un `ADMINISTRADOR` (de cualquier cuenta). El `ADMINISTRADOR` también revoca; revocar cierra las sesiones abiertas desde ese dispositivo.
- **Obligatoriedad:** `dispositivo_id` es obligatorio para los perfiles críticos de D40 (solo si el MFA está activo para ellos, es decir, con `MFA_PERFILES=ADMINISTRADOR,EPIDEMIOLOGO,AUTORIDAD_SANITARIA`; con el MFA apagado, que es lo que trae el compose, no se exige); para los demás es opcional (si llega, se aplica la regla; si no, el login sigue como hoy) hasta que los clientes lo envíen. Para exigirlo a todos: `DISPOSITIVO_OBLIGATORIO=1`.
- **Tope de pendientes:** 10 por cuenta (supuesto); el siguiente login con un dispositivo nuevo da 429. El registro se serializa por cuenta, así que solo el primero nace autorizado.
- **Rutas internas:** `/internal/open` y `/devices/check` solo aceptan el token de servicio de `auth`.
- **Dueño:** `sesiones` es dueño de `session_devices`; `auth` le pide la decisión por HTTP (ruta interna) al iniciar sesión.

## Consecuencias
- Honestamente: el control es opcional por omisión. Con el compose por defecto (`MFA_PERFILES` vacía, `DISPOSITIVO_OBLIGATORIO=0`) nadie está obligado, ni siquiera ADMINISTRADOR, EPIDEMIOLOGO y AUTORIDAD_SANITARIA; omitir `dispositivo_id` salta D41 por completo. Es protección real solo con `MFA_PERFILES` activa o `DISPOSITIVO_OBLIGATORIO=1`.
- Un cliente que no envía `dispositivo_id` no puede iniciar sesión como `ADMINISTRADOR` ni `EPIDEMIOLOGO`.
- Si `sesiones` no responde, el login que lleva `dispositivo_id` responde 503.
- Migración 050.
