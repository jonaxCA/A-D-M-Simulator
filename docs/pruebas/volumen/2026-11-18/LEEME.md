# Volumen de datos en MongoDB (2026-11-18)

Cierra D-6 y D29: el conjunto de alto volumen en `series_corridas` y sus mediciones con y sin índice y con y sin la caché de Redis.

- Rama `feat/bloque-B-y-D3`, sobre el commit `c1599fa`.
- **Se midió antes de que cada documento llevara `scenario_id`** (D5 del checklist, que llegó con `segundo-parcial-correccion`). El script ya lo agrega desde el 2026-11-19; los documentos crecen un campo, así que la inserción y el disco hay que medirlos otra vez con el comando de abajo. Los índices y las consultas no cambian.
- Entorno: Docker Desktop en Windows 11 (20 CPU, 7.6 GiB para Docker), solo los contenedores `mongodb` (`mongo:7.0`, caché de WiredTiger de 0.25 GB, como en el compose) y `redis`. El script corre en la misma máquina.
- Datos: 100 versiones × 100 réplicas (el tope de D8) = 10,000 corridas de 180 días de `seir-ref`. Cada versión cambia la R0 del escenario de ejemplo del contrato del motor (de 1.20 a 2.19, parámetros supuestos); cada réplica, la semilla. Son datos de prueba: van a la base `epidemia_pruebas`, nunca a la de la demostración.
- El script usa las mismas funciones que el simulador y `resultados`: `series_corridas.documentos`, `leer` y `banda`, los índices de `mongo.INDICES` y `cache.obtener`.

## Resultados

| Medición | Resultado |
|---|---|
| Volumen | 10000 corridas de 180 días: 1810000 documentos en 100 versiones |
| Tiempo total (simular e insertar) | 267 s |
| Inserción con los dos índices (`insert_many`) | 29.3 s, 61814 documentos/s |
| Inserción sin índices (181000 documentos) | 1.9 s, 97547 documentos/s |
| Una corrida como la guarda el simulador (`guardar`, 181 `replace_one`) | 351 ms |
| Serie de una corrida (`leer`), con `{run_id, dia}` | 5.0 ms |
| Serie de una corrida, sin índice | 849.2 ms |
| Banda p5-p95 de una versión (`banda`), con `{scenario_version_id, motor, dia}` | 38.3 ms |
| Banda p5-p95, sin índice | 995.0 ms |
| Serie sin caché (Redis vacío: lee MongoDB y guarda) | 4.8 ms |
| Serie con caché (Redis) | 1.1 ms |
| Disco: datos / comprimido / índices | 570 MB / 114 MB / 49 MB |
| Contenedor de MongoDB durante la carga | CPU media 20 %, máxima 82 %; memoria al final 338.7MiB; disco leído / escrito desde que arrancó 0B / 372MB (133 muestras) |

Las consultas son la mediana de 20 corridas o versiones distintas. «Sin índice» quita el índice, mide y lo vuelve a crear: reconstruirlos sobre 1.81 millones de documentos tomó 2.8 y 2.7 s.

## Interpretación

- **El índice `{run_id, dia}` es el que importa.** Sin él, pedir la serie de una corrida recorre la colección completa: 849 ms contra 5 ms, unas 170 veces más. Es la consulta de `/runs/{id}/curves` y `/results`.
- **La banda p5–p95** (la agregación de D28) baja de 995 ms a 38 ms con `{scenario_version_id, motor, dia}`: agrupa 18,100 documentos de una versión en lugar de 1.81 millones.
- **Redis** baja la serie de 4.8 ms a 1.1 ms. Con el índice, MongoDB ya responde rápido; la caché importa más con muchas consultas a la vez (la prueba de Locust) y si se cae el índice.
- **Inserción:** en bloque (`insert_many`), los dos índices cuestan alrededor de un tercio de la velocidad (62 mil contra 98 mil documentos por segundo). El simulador guarda una corrida con 181 `replace_one`, uno por día, para que un reintento no duplique: 351 ms por corrida, muy por debajo de lo que tarda simularla.
- **Disco:** 570 MB de documentos quedan en 114 MB comprimidos más 49 MB de índices; unos 90 bytes en disco por día de corrida. La memoria de MongoDB se quedó en 339 MiB, con el tope de caché del compose.
- **Cómo escala:** lo que crece con el número de corridas es la consulta sin índice (lineal) y el disco (unos 17 KB por corrida de 180 días). Con índice, la serie de una corrida tarda lo mismo con 12 corridas (4.5 ms, prueba corta) que con 10,000.

## Cómo repetirlo

1. Levanta MongoDB y Redis: `docker compose -f infra/docker-compose.yml up -d --wait mongodb redis` (con `infra/.env`, ver `docs/INSTALACION.md`).
2. Con el entorno de Python activo y las dependencias de `microservicios/comun/requirements.txt`, desde la raíz (en PowerShell, pon las contraseñas de `infra/.env` a mano):

```bash
MONGO_URL="mongodb://epidemia:$(grep '^MONGO_PASSWORD=' infra/.env | cut -d= -f2-)@127.0.0.1:27018/epidemia_pruebas?authSource=epidemia" \
REDIS_URL="redis://:$(grep '^REDIS_PASSWORD=' infra/.env | cut -d= -f2-)@127.0.0.1:6380/0" \
python datos/scripts/volumen_mongo.py > resultados.md
```

Tarda unos 5 minutos. `--versiones`, `--replicas`, `--dias` y `--muestras` cambian el tamaño (`--help`). El script borra `series_corridas` de `epidemia_pruebas` al empezar y se niega a correr contra `epidemia`. En Redis usa llaves `cache:volumen:*`, que borra al terminar, para no tocar la caché de `resultados`.
