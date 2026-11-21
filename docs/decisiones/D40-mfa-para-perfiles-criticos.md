# D40 - MFA para los perfiles críticos

Fecha: 2026-11-20 · Estado: Aceptada (tomada por el orquestador; pendiente de validación del líder) · Cierra el pendiente «MFA» del bloque 0 · Amplía D1

## Contexto
La retroalimentación pide MFA para los perfiles críticos. Sin SMTP no hay segundo factor por correo; hoy solo hay captcha y bloqueo de 15 min tras cinco fallos.

## Opciones consideradas
- Opción A: código por correo o SMS. Necesita un proveedor que no tenemos.
- Opción B: TOTP (RFC 6238), con cualquier app de autenticación y solo biblioteca estándar.

## Decisión
Opción B.

- **Perfiles críticos:** `ADMINISTRADOR` y `EPIDEMIOLOGO` (los códigos de `roles` en la migración 010). Quien tenga cualquiera de los dos pasa por MFA. Se cambian con `MFA_PERFILES` (lista separada por comas; vacía la apaga). **Arranca apagado**: sin `MFA_PERFILES` (o vacía) no se pide MFA, en el código y en el compose, mientras los clientes no tengan el flujo de dos pasos; se activa con `MFA_PERFILES=ADMINISTRADOR,EPIDEMIOLOGO` cuando lo tengan.
- **Algoritmo:** HMAC-SHA1, pasos de 30 s, 6 dígitos y ±1 ventana (`hmac`, `hashlib`, `base64`). Un código ya usado no sirve otra vez (`last_counter`).
- **Enrolamiento:** el secreto (20 bytes aleatorios, base32) lo genera `auth` y el usuario lo registra en su app con la URI `otpauth://`. Queda pendiente hasta que confirma con un primer código válido; entonces se muestran, una sola vez, 8 códigos de respaldo.
- **Códigos de respaldo:** 10 caracteres base32 (50 bits), de un solo uso; en la base solo está PBKDF2-SHA256 con la cuenta como sal (la columna `code_hash` sigue siendo de 64 caracteres; el comentario de la 051 que dice SHA-256 quedó superado).
- **Alta del enrolamiento (anti toma de cuenta):** quien solo tiene la contraseña no puede fijar el secreto. `/mfa/enroll` exige un `codigo_alta` de un solo uso y 15 min que emite un ADMINISTRADOR (`POST /api/v1/auth/mfa/{user_id}/enrollment-code`, auditado). Un secreto pendiente no se sobrescribe durante 15 min. Excepción para el primer administrador: `MFA_ENROLAMIENTO_LIBRE=1` en `auth` (apagado por omisión) mientras enrola; después se quita.
- **Tope por cuenta:** 5 códigos probados por cuenta en 15 min, contados en Redis de forma atómica e independientes del token de MFA; luego 429 `MFA_BLOQUEADO` en `/login` y `/mfa/verify`.
- **Inicio de sesión en dos pasos:** `POST /api/v1/auth/login` con contraseña correcta y un perfil crítico no regresa tokens: regresa un token temporal de MFA (opaco, no es un JWT, vive 5 min en Redis, 5 intentos). `POST /api/v1/auth/mfa/verify` (o `/mfa/enroll` y `/mfa/confirm` si aún no tiene MFA) lo cambia por el access y el refresh finales.
- **Pérdida del teléfono y de los códigos:** otro `ADMINISTRADOR` restablece el MFA (`DELETE /api/v1/auth/mfa/{user_id}`) y la cuenta vuelve a enrolarse en su siguiente login. Queda en la bitácora.
- Los perfiles no críticos no cambian.

## Consecuencias
- El secreto TOTP está en `user_mfa.secret` sin cifrar: el servidor tiene que conocerlo para verificar. Solo lo lee y escribe `svc_auth`. Cifrarlo con una llave de Secret Manager queda pendiente.
- La web, el escritorio y la móvil tienen que implementar los dos pasos para esos perfiles; hasta entonces, un `ADMINISTRADOR` o `EPIDEMIOLOGO` no recibe tokens de esos clientes (con `MFA_PERFILES` sin definir o vacía no pasa).
- Riesgo residual: con `MFA_ENROLAMIENTO_LIBRE=1` vuelve la toma en el primer enrolamiento; debe estar encendida solo durante el alta del primer administrador. Los códigos de respaldo previos a este cambio dejan de servir (el cambio es previo a cualquier despliegue).
- Migración 051 (`user_mfa`, `mfa_backup_codes`).
