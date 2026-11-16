# Límite de login por IP (2026-11-16)

- Rama `feat/4-seguridad-y-fallos`, commit `c7ebeb7` más los cambios sin confirmar de límites.
- Comando: `RESULTADOS=<dir> locust -f pruebas_carga/locustfile.py LimiteLogin --headless -u 1 -r 1 -t 75s --csv <dir>/locust --csv-full-history --html <dir>/reporte.html`
- Un usuario manda `POST /api/v1/auth/login` cada 100 ms con datos falsos. El límite se evalúa antes de leer el captcha, así que sin el límite respondería 422.
- Límite vigente: `publico`, 10 peticiones cada 60 s por IP.

## Resultados

| Respuesta | Peticiones | p95 ms |
|---|---|---|
| 422 (dentro del límite) | 20 | 9 |
| 429 `LIMITE_EXCEDIDO` con `Retry-After` | 665 | 6 |
| Fallos reales | 0 | |

Cronología: 10 peticiones aceptadas, el 429 empieza en la 11 (t = 1.1 s) y la ventana se abre a los 60 s, con otras 10. Una prueba con `curl` confirmó el encabezado `Retry-After: 45` y el cuerpo con `codigo` `LIMITE_EXCEDIDO`.

## Interpretación

- Funciona como se diseñó.
- El contador es por IP y cuenta también los logins buenos. En Docker Desktop todas las peticiones llegan con la misma IP de la puerta de enlace, y detrás de nginx (D25) serían la IP de nginx salvo que se use `X-Forwarded-For`. En ambos casos 10 por minuto sería para todos los usuarios juntos, no por persona.
- En la primera corrida combiné este flood con otras pruebas: bloqueó los inicios de sesión de las otras clases. Por eso este escenario va aparte.

## Recomendación (no se cambió código)

- Cuando haya nginx, tomar la IP real del cliente (`ProxyFix` o equivalente) antes de dejar este límite.
- Subir a 20/60 si en la demostración se espera que varias personas inicien sesión desde la misma red, o sumar un contador por nombre de usuario.
