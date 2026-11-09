# D26 - Certificado HTTPS

Fecha: — · Estado: Aceptada (2026-11-08)

## Contexto
nginx necesita un certificado en Compute Engine y las apps de Android y escritorio deben confiar en él.

## Opciones consideradas
- Opción A: con dominio, Let's Encrypt.
- Opción B: sin dominio, certificado autofirmado.

## Decisión
Opción A: certificado de Let's Encrypt para un dominio que apunta a la IP fija de Compute Engine. El puerto 80 queda abierto para la validación (D25).

## Consecuencias
Las apps de Android y de escritorio confían en el certificado sin configuración. Hace falta un dominio, propio o gratuito, que apunte a la IP fija de la máquina. nginx renueva el certificado solo, con certbot.

Depende de: D25
