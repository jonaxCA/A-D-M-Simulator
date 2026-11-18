> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-A: Autenticación y control de acceso

Función de soporte: la usan los tres procesos (pasos 1.1 y 2.1 de [`procesos_v3.md`](../../arquitectura/procesos_v3.md)). Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- PostgreSQL: `users`, `user_roles`, `role_permissions`, `devices`, `audit_log`.
- Redis: captcha, sesión y tokens revocados.
- Servicios: `auth`, `sesiones`, `usuarios`, `roles`, `dispositivos`.

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-A01 | Las apps inician sesión con usuario, contraseña y captcha. `auth` emite un token de acceso y uno de renovación | Con datos correctos responde los dos tokens y abre la sesión en Redis; queda `LOGIN` en la auditoría. Con datos incorrectos responde 401 con un mensaje genérico y queda `LOGIN_FAILED`. El captcha sirve para un solo intento y vence a los 300 s | 1.1, 2.1 | Microservicios, Seguridad | Alta | Hecho |
| RF-A02 | La sesión se renueva sin volver a pedir la contraseña | `sesiones` cambia el token de renovación por uno nuevo. Reutilizar uno ya usado cierra la sesión completa. Renovar no alarga la sesión | 1.1, 2.1 | Microservicios, Seguridad | Alta | Hecho |
| RF-A03 | Cerrar sesión revoca el token | `sesiones` marca el token como revocado en Redis y borra la sesión; la siguiente petición con ese token responde 401 | Soporte | Microservicios, Seguridad | Alta | Hecho |
| RF-A04 | El sistema tiene cuatro roles: ADMINISTRADOR, EPIDEMIOLOGO, ANALISTA y CAPTURISTA. El sitio público no pide sesión | Toda cuenta tiene un rol (RN-01). El token lleva los roles | Soporte | Seguridad, Bases de datos | Alta | Hecho |
| RF-A05 | Cada ruta lleva un candado por rol, según la [matriz de permisos](../matriz-permisos.md) | Un rol sin permiso recibe 403 y un mensaje; ocultar el botón no basta. Se prueba con un rol que entra y con uno que no | Soporte | Seguridad | Alta | En parte: falta la migración 034 y los candados por permiso en la web (D1) |
| RF-A06 | Todo cambio de datos queda en la auditoría | `audit_log` guarda quién, qué acción, sobre qué entidad, cuándo, la IP y el identificador de correlación, en la misma transacción que el cambio | Todos | Seguridad, Bases de datos | Alta | Hecho |
| RF-A09 | La app móvil registra el teléfono, uno por cuenta | `dispositivos` crea o actualiza el registro en `devices`; queda `CREATE` o `UPDATE` en la auditoría. Un teléfono revocado no sincroniza | 1.2 | Móvil, Microservicios | Media | Hecho |
| RF-A11 | La web inicia sesión con usuario y contraseña, y guarda su token en una cookie | Con datos correctos entra al tablero; con datos incorrectos no entra y queda `LOGIN_FAILED`. Después de entrar solo redirige a rutas del propio sitio | Soporte | Web, Seguridad | Alta | Hecho |
| RF-A12 | La web registra y revisa su sesión en Redis, igual que las apps | Cerrar sesión en la web deja el token sin valor antes de que venza | Soporte | Web, Seguridad | Alta | Hecho (I3), verificado el 2026-11-16; con Redis caído la web conserva las sesiones abiertas y no deja entrar (D33) |
| RF-A13 | Cada usuario consulta su perfil | `usuarios` responde el nombre, el usuario y los roles de quien pregunta (`GET /api/v1/users/me`) | Soporte | Microservicios | Media | Hecho |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-A08 | Número máximo de sesiones por usuario, configurable | Ningún proceso lo pide |
| RF-A10 | Recuperar la contraseña | El servicio `recuperacion` era opcional y no se construyó; la contraseña la cambia el ADMINISTRADOR (RF-L01) |
