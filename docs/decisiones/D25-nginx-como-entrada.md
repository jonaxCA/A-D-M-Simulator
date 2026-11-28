# D25 - nginx como terminador TLS y entrada única

Fecha: 2026-11-01 · Estado: Aceptada (2026-11-08)

## Contexto
La v2 retiró nginx (D13) y dejó abierto cómo proteger el tráfico en Compute Engine. La rúbrica pide HTTPS, firewall y puertos controlados. El equipo decidió usar nginx.

## Opciones consideradas
- Opción A: una sola entrada con prefijo por servicio. nginx escucha en 443 y enruta `https://<dominio>/aprobacion/api/v1/...` a `aprobacion:8000/api/v1/...`. Solo quedan abiertos el 80 (redirige al 443) y el 443.
- Opción B: nginx delante de cada puerto. Un puerto abierto y una regla de firewall por servicio.
- Opción C: no usar nginx (D13 original). Descartada por el equipo.

No sirve enrutar por la ruta de la API, porque varios servicios comparten prefijo: `/api/v1/scenarios/...` lo atienden `escenarios`, `aprobacion` y `escenarios-xml`.

## Decisión
Opción A. nginx es el terminador TLS y el proxy inverso, sin validar JWT ni tener lógica de negocio. Solo quedan abiertos el 80 (redirige al 443) y el 443.

## Consecuencias
- Ajusta D13: `estado-servicios` devuelve `https://<dominio>/<servicio>`. Las rutas de D11 no cambian.
- Los servicios deben funcionar detrás de un prefijo: revisar `/docs`, `/openapi.json` y el CORS de `CONSOLE_ORIGIN`.
- A un servicio solo van sus rutas: `/<servicio>/api/...`, `/health`, `/docs` y `/openapi.json`. Lo demás es de la web, porque varias de sus páginas se llaman como un servicio (`/usuarios`, `/regiones/5/editar`, `/escenarios/3`, `/enfermedades`, `/comparacion`); al principio nginx las mandaba al servicio, que respondía 404 (visto en la máquina el 2026-11-21). La consola, que sí tiene páginas propias, conserva todo `/consola/`.
- Los límites de consumo siguen en Redis. `limit_req` de nginx puede ser una capa extra, no la única.
- D26 decide de dónde sale el certificado.
- Implementado en local el 2026-11-19: `infra/docker-compose.nginx.yml` e `infra/nginx/` (guía en `docs/INSTALACION.md`). Detrás de nginx, cada servicio confía en sus cabeceras `X-Forwarded-*` solo con `DETRAS_DE_PROXY=1`, y esa variable solo va donde los servicios no publican su puerto. waitress también tiene que confiar en ellas (`epidemia_comun/servir.py`): por omisión las borra, y el servicio veía la IP de nginx en lugar de la del cliente.

Depende de: D13
