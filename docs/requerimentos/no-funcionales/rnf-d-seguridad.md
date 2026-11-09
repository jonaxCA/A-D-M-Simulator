Estado: Obsoleto. Requiere actualizarse

# RNF-D: Seguridad

### RNF-D01 Encriptación en tránsito

Todo tráfico externo debe usar TLS 1.2+
Criterio de aceptación: pendiente de definir

### RNF-D02 Encriptación en reposo

Datos sensibles en reposo deben estar cifrados
Criterio de aceptación: pendiente de definir

### RNF-D03 Gestión de secretos

Secretos en Google Secret Manager, nunca en código ni repositorio
Criterio de aceptación: pendiente de definir

### RNF-D04 Validación de entradas

Toda entrada debe validarse contra esquema antes de procesarse
Criterio de aceptación: pendiente de definir

### RNF-D05 Protección contra inyección

Consultas parametrizadas en PostgreSQL; sin concatenación de SQL
Criterio de aceptación: pendiente de definir

### RNF-D06 Protección contra XSS

Escapado automático en plantillas web; CSP configurado
Criterio de aceptación: pendiente de definir

### RNF-D07 Protección contra CSRF

Tokens CSRF en formularios web
Criterio de aceptación: pendiente de definir

### RNF-D08 Rate limiting

Límites de consumo por usuario y endpoint configurados en Flask-Limiter
Criterio de aceptación: pendiente de definir

### RNF-D09 Red privada

Bases de datos y microservicios sin IP pública; solo Nginx expuesto
Criterio de aceptación: pendiente de definir

### RNF-D10 Firewall

Reglas restrictivas por puerto y origen
Criterio de aceptación: pendiente de definir

### RNF-D11 JWT seguro

Firma HS256/RS256, expiración ≤ 24h, refresh token separado
Criterio de aceptación: pendiente de definir

### RNF-D12 Revocación de tokens

Tokens revocados verificados contra Redis en cada petición
Criterio de aceptación: pendiente de definir

### RNF-D13 Principio de mínimo privilegio

Cada servicio accede solo a los datos que necesita
Criterio de aceptación: pendiente de definir

### RNF-D14 Auditoría completa

Toda operación sensible registrada con usuario, timestamp, IP, recurso
Criterio de aceptación: pendiente de definir

### RNF-D15 Protección de datos personales

Datos de salud sensibles: sin nombre, CURP, dirección exacta
Criterio de aceptación: pendiente de definir

### RNF-D16 Privacidad por diseño

Coordenadas exactas restringidas por rol; agregación con umbral mínimo
Criterio de aceptación: pendiente de definir

### RNF-D17 URLs firmadas

Archivos en Cloud Storage accesibles solo mediante URLs firmadas con expiración
Criterio de aceptación: pendiente de definir

### RNF-D18 Escaneo de dependencias

Dependencias deben escanearse contra vulnerabilidades conocidas
Criterio de aceptación: pendiente de definir

### RNF-D19 Autenticación multifactor

MFA opcional para roles administrativos
Criterio de aceptación: pendiente de definir

### RNF-D20 Política de contraseñas

Mínimo 12 caracteres, complejidad, rotación periódica
Criterio de aceptación: pendiente de definir

### RNF-D21 Header de seguridad

X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security
Criterio de aceptación: pendiente de definir

### RNF-D22 Datos sintéticos

Población simulada es sintética; ningún agente corresponde a persona real
Criterio de aceptación: pendiente de definir

### RNF-D23 Cifrado local móvil

Datos sensibles en Room cifrados con SQLCipher o equivalente
Criterio de aceptación: pendiente de definir

### RNF-D24 Protección de evidencias

Fotografías accesibles solo a roles autorizados
Criterio de aceptación: pendiente de definir
