> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RNF-C: Disponibilidad y fallos

Qué debe pasar cuando una pieza falla. La tabla de fallos está en [`arquitectura_v3.md`](../../arquitectura/arquitectura_v3.md) (§9). Cómo leer la tabla: [`README.md`](../README.md).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Componente | Estado |
|---|---|---|---|---|
| RNF-C02 | La caída de un servicio no tumba a los demás | El panel lo marca caído; quien lo llama responde 503 `SERVICIO_NO_DISPONIBLE`; los demás siguen | Microservicios | Hecho; demostrado el 2026-11-16 (`docs/pruebas/fallos/2026-11-16`) |
| RNF-C03 | Una corrida interrumpida no se queda colgada | Al arrancar, el simulador cierra como fallidas las que quedaron `ejecutando` y vuelve a encolar las `encolado` de su motor (D19) | Microservicios | En parte: falta reencolar (ver RF-E19) |
| RNF-C07 | Perder Redis no pierde datos | Redis solo guarda lo temporal y reconstruible: la gente vuelve a iniciar sesión y las cachés se rellenan solas (D19) | Bases de datos | Hecho |
| RNF-C08 | Si MongoDB no responde, lo demás sigue | La captura de casos no depende de MongoDB. La corrida termina con su resumen en `simulation_runs` y el panel marca la dependencia caída. Propuesta: la serie se reintenta | Microservicios, Bases de datos | Hecho (D-1): la serie se reintenta cada 30 s; `test_compose_mongo.py` |
| RNF-C09 | Cada archivo guarda su huella para comprobar que no cambió | `case_attachments` lleva la huella SHA-256 del archivo, y se revisa al subirlo | Microservicios, Seguridad | Hecho (D2): la huella se guarda en `case_attachments` y `comparison_reports`, y si el cliente manda `X-Content-SHA256` y no coincide, la subida es 422 |
| RNF-C10 | Una llamada entre servicios no espera para siempre | `llamar()` corta a los 5 s y responde 503. nginx corta cualquier petición a los `NGINX_TIEMPO_MAXIMO` (30 s) con 504 | Microservicios | Hecho: `test_nginx_corta_una_peticion_colgada` (2026-11-19) |
| RNF-C13 | Sincronizar dos veces el mismo lote no duplica nada | Ver RF-C09 | Microservicios | Hecho |
| RNF-C16 | Los fallos se demuestran | Se demuestra la caída de un servicio, de Redis, de MongoDB, de PostgreSQL, del bucket y un tiempo de espera excedido, con lo que debe pasar en cada caso | Infraestructura | En parte: demostrados el 2026-11-16 un servicio, Redis (con la web), PostgreSQL, el tiempo excedido, y MongoDB y el bucket solo en `/health` y panel (emuladores de la demostración); falta la lógica que los usa (bloque D) |
| RNF-C17 | Si Redis no responde, las rutas protegidas fallan cerradas | Responden 503 en vez de dejar pasar sin revisar la sesión; `corridas` no deja una corrida colgada | Seguridad, Microservicios | Hecho |
| RNF-C18 | Si PostgreSQL no responde, ninguna escritura queda a medias | `/health` responde 503, el panel marca los servicios degradados y cada escritura es una sola transacción | Bases de datos | Hecho; demostrado el 2026-11-16: `/health` 503 y sin datos a medias, y las lecturas responden 503 `SERVICIO_NO_DISPONIBLE` (un 500 inicial se corrigió en `fabrica.py`) |
| RNF-C19 | Si el bucket no está disponible, el archivo no se pierde | La subida responde 503, la app conserva el archivo para reintentar y el caso ya creado se queda | Microservicios, Móvil | Hecho en el servicio (D2): con el bucket caído la subida es 503 y no deja registro; el caso se queda (`test_compose_evidencias.py`). Reintentar es de la app (B) |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RNF-C01 | Disponibilidad de 99.5 % | No hay con qué medirla en un proyecto de un parcial |
| RNF-C04 | La cola sobrevive a un reinicio de Redis | La cola se reconstruye desde PostgreSQL (RNF-C03, D19) |
| RNF-C05 | Respaldo diario de PostgreSQL | No lo pide la rúbrica ni ninguna decisión |
| RNF-C06 | Restaurar en menos de 4 horas | Igual que RNF-C05 |
| RNF-C11 | Health checks continuos | Pasa a RNF-J05 |
| RNF-C12 | Recuperación en menos de 2 minutos | No hay con qué medirla; la recuperación se reporta en Locust (RNF-A16) |
| RNF-C14 | Sin punto único de fallo | El despliegue decidido es una máquina principal (arquitectura v3, §8) |
| RNF-C15 | Logs en JSON | Pasa a RNF-J06 |
