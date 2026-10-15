# AGENTS.md — infra

> **Estado: Vigente** · 2026-10-12 · Complementa `microservicios/AGENTS.md`. Las tareas son
> el bloque J del checklist (`docs/CHECKLIST_SEGUNDO_PARCIAL.md`).

Aquí viven la imagen base de Docker y el `docker-compose.yml` que levanta los 26
microservicios, la consola, PostgreSQL y Redis. **Un contenedor por microservicio.**

## Reglas

1. Todos los servicios parten de la imagen `epidemia/base` (`docker/base.Dockerfile`), con
   usuario no root. Una dependencia se agrega en la base, no en el `Dockerfile` de un
   servicio.
2. Cada servicio escucha en 8000 dentro de su contenedor y publica el puerto del catálogo
   (`docs/arquitectura/microservicios.md`). No inventes puertos.
3. Cada servicio tiene `HEALTHCHECK` a `/health`, y sus dependencias van con
   `depends_on: condition: service_healthy`.
4. PostgreSQL y Redis quedan en la red interna; no publiques sus puertos fuera de la
   máquina.
5. Los secretos van en el `.env` del compose, que no se versiona; solo `.env.example`.
   Nunca escribas un secreto en un `Dockerfile`, en el compose ni en una imagen.
6. Redis ya está en el compose, con contraseña, `appendonly yes`, `maxmemory 256mb` y
   `noeviction`, para que no se expulsen sesiones ni revocaciones. Se publica solo en
   `127.0.0.1:6380`, para no chocar con Memurai. No le quites nada de eso; los servicios lo
   alcanzan como `redis:6379`.
7. La base se inicializa con el dump, las semillas y las migraciones desde la 026, en ese
   orden, igual que el Paso 2 de `docs/INSTALACION.md`.
8. Las pruebas de integración usan su propio compose, sobre `simulador_epidemico_pruebas` y
   un Redis aparte. Nunca sobre la base de la demostración.
9. Cada servicio tiene un perfil de dominio (`identidad`, `catalogos`, `vigilancia`,
   `escenarios`, `simulacion`, `analitica`, `plataforma`), para que nadie tenga que
   levantar los 28 contenedores en una máquina con poca memoria.
10. Si cambias el compose, `docker compose up` desde cero tiene que dejar los 26
    *healthchecks* en verde. Si no, no está terminado.
