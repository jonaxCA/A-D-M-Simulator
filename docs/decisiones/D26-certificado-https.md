# D26 - Certificado HTTPS

Fecha: — · Estado: Pendiente

## Contexto
nginx necesita un certificado en Compute Engine y las apps de Android y escritorio deben confiar en él.

## Opciones consideradas
- Opción A: con dominio, Let's Encrypt.
- Opción B: sin dominio, certificado autofirmado.

## Decisión
Pendiente. Se registra aquí cuando se tome.

## Consecuencias
Con un certificado autofirmado, la app Android y la de escritorio tienen que configurarse para confiar en él. Necesita saber si el equipo tiene dominio.

Depende de: D25
