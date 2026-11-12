# D26 - Certificado HTTPS

Fecha: — · Estado: Aceptada (2026-11-08)

## Contexto
nginx necesita un certificado en Compute Engine y las apps de Android y escritorio deben confiar en él.

## Opciones consideradas
- Opción A: con dominio, Let's Encrypt.
- Opción B: sin dominio, certificado autofirmado.

## Decisión
Opción A: certificado de Let's Encrypt para un dominio que apunta a la IP fija de Compute Engine. El puerto 80 queda abierto para la validación (D25). Con la B, cada app tendría que traer el certificado autofirmado y cambiarlo cada vez que se renueve.

Let's Encrypt no emite certificados para localhost, así que la opción A de D26 no se puede aplicar todavía. No cambia la decisión, solo cuándo se aplica.
- Local: nginx (D25) con un certificado generado con mkcert, que también instala su raíz en la máquina. Así se demuestra TLS y la entrada única aunque no haya dominio.
- Escritorio: en local, requests se apunta a la raíz de mkcert con la variable REQUESTS_CA_BUNDLE. En producción no necesita nada (ya confía en Let's Encrypt).
- Android: el emulador llega a la máquina por 10.0.2.2, no por localhost. El build de depuración ya tiene su propio network_security_config.xml; ahí se agrega la raíz de mkcert. El build de release no cambia y sigue confiando solo en ISRG Root X1 y las del sistema.
- Despliegue: cuando haya IP fija en Compute Engine, se consigue el dominio y se aplica D26 tal como está.


## Consecuencias
- Hace falta un dominio, propio o gratuito, que apunte a la IP fija de la máquina. nginx renueva el certificado solo, con certbot.
- **Android:** la raíz de Let's Encrypt (ISRG Root X1) viene de fábrica desde Android 7.1.1 (API 25), pero la app acepta desde Android 7.0 (`minSdk 24`). Por eso la app trae esa raíz (`frontend_movil/app/src/main/res/raw/isrg_root_x1.crt`) y su configuración de seguridad de red confía en ella además de en las del sistema. `RaicesTlsTest` revisa su huella y que release y debug la conserven. La raíz vence en 2035; si Let's Encrypt deja de encadenar a ella antes, hay que cambiar la que trae la app.
- **Escritorio:** la app de `feat/app-escritorio` usa `requests`, que confía en las raíces de `certifi`, y ahí está ISRG Root X1. No necesita configuración.

Depende de: D25
