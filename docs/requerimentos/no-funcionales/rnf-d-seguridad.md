> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RNF-D: Seguridad

Lo que pide la rúbrica en seguridad y cómo se cumple. El cotejo está en [`arquitectura_v3.md`](../../arquitectura/arquitectura_v3.md) (§8). Cómo leer la tabla: [`README.md`](../README.md).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Componente | Estado |
|---|---|---|---|---|
| RNF-D01 | Todo el tráfico de fuera va por HTTPS | nginx atiende en 443 y el 80 redirige. Certificado de Let's Encrypt en la nube y de mkcert en local (D25, D26) | Infraestructura, Seguridad | Falta (S6) |
| RNF-D03 | Los secretos no están en el código ni en el repositorio | `.env` fuera de git, generado por `infra/genera_env.py`. En GCP, con permisos 600 en la máquina; propuesta: Secret Manager | Infraestructura, Seguridad | En parte: falta GCP (S5) |
| RNF-D04 | Toda entrada se valida antes de usarse | El XML se valida contra su XSD y se lee con `defusedxml`; cada cuerpo JSON se valida campo por campo | Microservicios, Seguridad | Hecho |
| RNF-D05 | Las consultas a PostgreSQL llevan parámetros, sin armar SQL con texto del usuario | Ninguna consulta concatena valores que llegan de fuera | Bases de datos, Seguridad | Verificar |
| RNF-D06 | La web escapa lo que muestra | Las plantillas escapan el HTML por omisión | Web, Seguridad | Verificar |
| RNF-D07 | Los formularios de la web llevan protección contra CSRF | Un formulario enviado desde otro sitio se rechaza | Web, Seguridad | Falta: no hay código ni brecha registrada |
| RNF-D08 | Hay límites de consumo por usuario y ruta (D31) | Un contador `ratelimit:<usuario>:<ruta>` en Redis, en `epidemia_comun`. Más permisivo en `casos` y `sincronizacion`, más estricto en `corridas`. Sin sesión, va por IP. Responde 429 con `Retry-After` | Microservicios, Seguridad | Hecho |
| RNF-D09 | Desde fuera solo se llega a nginx | Ni los servicios ni las bases publican puertos en la nube | Infraestructura, Seguridad | Falta (N1, S6) |
| RNF-D10 | El firewall deja pasar solo lo necesario | 80 y 443 para todos; 22 solo para el equipo; 5432 y 6379 solo desde la máquina con GPU; lo demás, denegado | Infraestructura, Seguridad | Falta (N1) |
| RNF-D11 | Los tokens tienen vida corta | Token de acceso HS256 de 20 minutos; token de renovación de un solo uso; sesión de 8 horas | Seguridad | Hecho |
| RNF-D12 | Un token revocado deja de servir de inmediato | Cada servicio revisa la sesión y la revocación en Redis en cada petición. En Redis solo se guarda la huella del identificador, nunca el valor | Seguridad, Microservicios | Hecho en los servicios (S1) y en la web (RF-A12, verificado el 2026-11-16) |
| RNF-D13 | Cada servicio toca solo sus datos | Un rol de PostgreSQL por servicio, con permiso solo sobre sus tablas (D18) | Bases de datos, Seguridad | Hecho |
| RNF-D14 | La auditoría es completa | Ver RF-A06 | Seguridad | Hecho |
| RNF-D15 | No se guardan datos que identifiquen a una persona | Un caso no lleva nombre, CURP ni domicilio: solo edad, sexo, fechas, resultado, severidad y ubicación | Bases de datos, Seguridad | Hecho |
| RNF-D17 | Los archivos privados se abren solo con una URL firmada que vence | El servicio dueño revisa el permiso y responde la URL. Propuesta: 15 minutos. Ninguna URL es permanente | Microservicios, Seguridad | Falta (D-3) |
| RNF-D20 | Las contraseñas tienen un mínimo de 8 caracteres y no se guardan en claro | Una contraseña más corta se rechaza al crear o editar la cuenta. La base guarda solo su huella (`password_hash`) | Seguridad | Hecho |
| RNF-D21 | La web manda los encabezados de seguridad | `X-Content-Type-Options`, `X-Frame-Options` y `Strict-Transport-Security`, desde nginx o desde la web | Web, Infraestructura | Falta: no hay código ni brecha registrada |
| RNF-D23 | El teléfono protege lo que guarda | Ver RF-I13 y RF-I15 | Móvil, Seguridad | Hecho |
| RNF-D24 | Las fotos de los casos solo las ve quien tiene permiso | El archivo se baja con token; cada uno lleva su nivel de privacidad | Microservicios, Seguridad | Hecho; con el bucket pasa a URL firmada (RNF-D17) |
| RNF-D25 | Los intentos fallidos de inicio de sesión se registran | Cada uno deja `LOGIN_FAILED` en la auditoría | Seguridad | Hecho (S3) |
| RNF-D26 | Los errores no revelan cómo está hecho el sistema | Formato RFC 7807 con un `codigo` estable, sin traza ni SQL | Microservicios, Seguridad | Hecho |
| RNF-D27 | Los archivos se validan al subirlos | Se revisan el tipo por su contenido (no por la extensión), el tamaño máximo y la huella | Microservicios, Seguridad | Falta: va con el bucket (D30) |
| RNF-D28 | Las rutas internas solo aceptan a otros servicios | Una ruta con `@solo_servicios` rechaza el token de un usuario; así se crean los avisos | Microservicios, Seguridad | Hecho |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RNF-D02 | Cifrar los datos en reposo | No lo pide la rúbrica; en el teléfono sí se cifran los tokens (RNF-D23) |
| RNF-D16 | Coordenadas exactas restringidas por rol y agregación con umbral | No hay umbral definido (ver RF-C18) |
| RNF-D18 | Escanear las dependencias | No hay integración continua (RNF-F07) |
| RNF-D19 | Segundo factor para administradores | No lo pide la rúbrica |
| RNF-D22 | Población sintética | Pasa a RNF-I06 |
