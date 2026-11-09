Estado: Obsoleto. Requiere actualizarse

# RF-A: Autenticación y Control de Acceso

## Dependencias

- PostgreSQL (users, roles)
- Redis (sesiones)

### RF-A01 Inicio de sesión

El sistema debe permitir autenticación mediante usuario y contraseña, emitiendo un JWT con tiempo de expiración configurable
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-A02 Renovación de token

El sistema debe permitir renovar el JWT sin necesidad de reautenticación completa
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-A03 Cierre de sesión

El sistema debe permitir revocar el token activo, invalidándolo en Redis
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-A04 Gestión de roles

El sistema debe soportar cinco perfiles: Administrador, Epidemiólogo, Analista, Capturista y Público general
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-A05 Matriz de permisos

El sistema debe aplicar permisos diferenciados por rol para cada operación disponible
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-A06 Registro de auditoría

El sistema debe registrar usuario, fecha, hora, dirección IP y operación realizada en cada acción sensible
Criterio de aceptación: pendiente de definir
Prioridad: Alta

### RF-A08 Sesiones concurrentes

El sistema debe permitir configurar el número máximo de sesiónes activas por usuario
Criterio de aceptación: pendiente de definir
Prioridad: Baja

### RF-A09 Verificación por dispositivo

La app móvil debe registrar un identificador único por dispositivo asociado al usuario
Criterio de aceptación: pendiente de definir
Prioridad: Media

### RF-A10 Recuperación de contraseña

El sistema debe permitir restablecimiento de contraseña mediante flujo seguro
Criterio de aceptación: pendiente de definir
Prioridad: Alta

#### Casos de uso detallados:

#### CU-A01: Autenticación de usuario

* **Actor:** Todos los usuarios registrados  
* **Precondición:** Usuario registrado en el sistema  
* **Flujo principal:**

  1\. Usuario ingresa credenciales

  2\. Sistema valida credenciales contra PostgreSQL

  3\. Sistema verifica que la cuenta esté activa

  4\. Sistema emite JWT con claims de rol y permisos

  5\. Sistema registra sesión en Redis

  6\. Sistema responde con token y perfil del usuario

* **Flujos alternativos:**  
  * Credenciales inválidas → 401 con mensaje genérico  
  * Cuenta bloqueada → 403 con tiempo de desbloqueo  
  * Token previo no revocado → renovación automática  
* **Postcondición:** Usuario autenticado con sesión activa
