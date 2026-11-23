# AGENTS.md — infra

> **Estado: Vigente** · 2026-10-12 · Complementa `microservicios/AGENTS.md`. Las tareas son
> el bloque J del checklist (`docs/parciales/parcial-2/checklist.md`).

Aquí viven la imagen base de Docker y el `docker-compose.yml` que levanta los 30
microservicios, la consola, PostgreSQL y Redis. **Un contenedor por microservicio.**

## Reglas

1. Todos los servicios parten de la imagen `epidemia/base` (`docker/base.Dockerfile`), con
   usuario no root. Una dependencia se agrega en la base, no en el `Dockerfile` de un
   servicio.
   - El compose la construye primero: es el servicio `base`, con cero réplicas, y cada
     servicio la pide con `additional_contexts` (`epidemia/base: service:base`). Así nunca
     se busca en Docker Hub. No la publiques ahí.
   - Los servicios de simulación (`corridas`, `simulador`, `resultados`, `comparacion` y `pareto`)
     parten de `epidemia/base-simulacion` (`docker/base-simulacion.Dockerfile`): lo mismo, sin
     `backend_web` (E8). Los de identidad, de `epidemia/base-identidad`, y los de F (vigilancia,
     analítica y plataforma), de `epidemia/base-vigilancia`, igual que `evidencias` (D, sin
     `backend_web` desde D2). Los demás de D siguen en `epidemia/base` mientras no se les quite
     `backend_web`.
   - El `Dockerfile` de un servicio solo copia su carpeta y su contrato. Úsalo igual que los
     demás, o el que genera `nuevo_servicio.py`.
2. Cada servicio escucha en 8000 dentro de su contenedor y publica el puerto del catálogo
   (`docs/arquitectura/microservicios.md`). No inventes puertos.
3. Cada servicio tiene `HEALTHCHECK` a `/health`, y sus dependencias van con
   `depends_on: condition: service_healthy`.
4. PostgreSQL, Redis y MongoDB quedan en la red interna; no publiques sus puertos fuera de la
   máquina. MongoDB (D28) se publica solo en `127.0.0.1:27018`; los servicios lo alcanzan como
   `mongodb:27017` con el usuario `epidemia`, que crea `mongo/10-usuario.js` con el volumen
   vacío. Un servicio que lo use lleva `MONGO_URL` y `depends_on: mongodb`.
   - El emulador de Cloud Storage (`bucket`, `fake-gcs-server`, D30) se publica solo en
     `127.0.0.1:4443`, porque las URLs firmadas apuntan ahí para que las abra el navegador. Crea el
     bucket `epidemia-archivos` con `bucket/` y guarda los objetos en el volumen `bucket-datos`.
     En GCP no se levanta: `docker-compose.gcs.yml` pone el bucket real (`crea_bucket.sh`).
5. Los secretos van en el `.env` del compose, que no se versiona; solo `.env.example`.
   Nunca escribas un secreto en un `Dockerfile`, en el compose ni en una imagen.
6. Redis ya está en el compose, con contraseña, `appendonly yes`, `maxmemory 256mb` y
   `noeviction`, para que no se expulsen sesiones ni revocaciones. Se publica solo en
   `127.0.0.1:6380`, para no chocar con Memurai. No le quites nada de eso; los servicios lo
   alcanzan como `redis:6379`.
7. La base se inicializa con `postgres/10-inicializa.sh`, solo con el volumen vacío: el dump
   (que trae todas las migraciones), las semillas y los permisos del monolito, igual que los
   pasos 1 a 3 de `docs/INSTALACION.md`, y la contraseña de cada rol `svc_*`.
   - Las contraseñas se leen del entorno con `\getenv`; nunca las pases por la línea de
     comandos de `psql`.
   - Un servicio nuevo necesita su `DB_PASSWORD_<SERVICIO>` en `postgres` y en su
     `DATABASE_URL`, como los demás, y su rol en una migración.
8. Las pruebas de integración usan su propio compose, sobre `simulador_epidemico_pruebas` y
   un Redis aparte. Nunca sobre la base de la demostración.
   - Lo arma `pruebas_integracion.py`: proyecto `epidemia-pruebas` (otros volúmenes),
     `POSTGRES_DB` en `.env.pruebas` y `docker-compose.pruebas.yml`, que solo agrega lo que
     necesitan las pruebas (un segundo `simulador`).
   - Por eso la base del compose sale de `POSTGRES_DB`: si agregas un servicio, su
     `DATABASE_URL` termina en `/${POSTGRES_DB:-simulador_epidemico}` como los demás.
9. Cada servicio tiene un perfil de dominio (`identidad`, `catalogos`, `vigilancia`,
   `escenarios`, `simulacion`, `analitica`, `plataforma`), para que nadie tenga que
   levantar todos los contenedores en una máquina con poca memoria.
10. Si cambias el compose, `docker compose up` desde cero tiene que dejar los 30
    *healthchecks* en verde. Si no, no está terminado.
