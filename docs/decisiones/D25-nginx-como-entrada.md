# D25 - nginx como terminador TLS y entrada única

Fecha: 2026-11-01 · Estado: Propuesta

## Contexto
La v2 retiró nginx (D13) y dejó abierto cómo proteger el tráfico en Compute Engine. La rúbrica pide HTTPS, firewall y puertos controlados. El equipo decidió usar nginx.

## Opciones consideradas
- Opción A: una sola entrada con prefijo por servicio. nginx escucha en 443 y enruta `https://<dominio>/aprobacion/api/v1/...` a `aprobacion:8000/api/v1/...`. Solo quedan abiertos el 80 (redirige al 443) y el 443.
- Opción B: nginx delante de cada puerto. Un puerto abierto y una regla de firewall por servicio.
- Opción C: no usar nginx (D13 original). Descartada por el equipo.

No sirve enrutar por la ruta de la API, porque varios servicios comparten prefijo: `/api/v1/scenarios/...` lo atienden `escenarios`, `aprobacion` y `escenarios-xml`.

## Decisión
El equipo decidió usar nginx como terminador TLS y proxy inverso, sin validar JWT ni tener lógica de negocio. La opción A es la recomendada. Falta que el equipo la confirme.

## Consecuencias
- Ajusta D13: `estado-servicios` devuelve `https://<dominio>/<servicio>`. Las rutas de D11 no cambian.
- Los servicios deben funcionar detrás de un prefijo: revisar `/docs`, `/openapi.json` y el CORS de `CONSOLE_ORIGIN`.
- Los límites de consumo siguen en Redis. `limit_req` de nginx puede ser una capa extra, no la única.
- D26 decide de dónde sale el certificado.

Depende de: D13
