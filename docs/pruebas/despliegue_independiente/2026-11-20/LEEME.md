# Despliegue independiente de un servicio (E8)

Fecha: 2026-11-20. Pregunta: ¿se puede construir y desplegar un servicio sin tocar a los demás, y
sin llevarse `backend_web`? Se probó con uno de identidad (`usuarios`) y uno de simulación
(`corridas`), con el compose de `infra/` y los 34 contenedores arriba (todos los perfiles menos `gpu`).

## Qué se hizo

```bash
# Antes: id, hora de arranque e imagen de cada contenedor en marcha
docker ps --format '{{.Names}}' | sort | while read n; do
  docker inspect -f '{{.Name}} {{printf "%.12s" .Id}} {{.State.StartedAt}} {{printf "%.19s" .Image}}' $n; done > antes.txt

# Construir y desplegar solo esos dos servicios
docker compose -f infra/docker-compose.yml <perfiles> build usuarios
docker compose -f infra/docker-compose.yml <perfiles> up -d --no-deps --force-recreate --wait usuarios corridas
# (corridas: build corridas, igual)

# Después, la misma lista, y se compara
diff antes.txt despues.txt
```

`--no-deps` evita que Compose toque las dependencias (PostgreSQL, Redis, otros servicios).
`--force-recreate` fue necesario porque no hubo cambio de código: sin él Compose deja el
contenedor como está (`Container epidemia-usuarios-1 Running`), que también es una prueba de que
reconstruir sin cambios no mueve nada.

## Resultado: solo cambiaron esos dos contenedores

```
 Container epidemia-corridas-1 Recreated
 Container epidemia-usuarios-1 Recreated
 Container epidemia-corridas-1 Healthy
 Container epidemia-usuarios-1 Healthy

6c6
< /epidemia-corridas-1 e41ca6a411d5 2026-11-21T00:30:44.861183251Z sha256:f0a5a1b837f7
---
> /epidemia-corridas-1 a22767992fda 2026-11-21T00:32:21.03452992Z sha256:2fae5809cad8
31c31
< /epidemia-usuarios-1 39a81e9b57b9 2026-11-21T00:30:44.736827834Z sha256:98af3d909e8f
---
> /epidemia-usuarios-1 cd18a22807bc 2026-11-21T00:32:20.972392337Z sha256:700eba27d044
```

Las otras 32 líneas (otros 32 contenedores, con PostgreSQL, Redis y MongoDB) salen idénticas:
mismo id y misma hora de arranque. Los dos servicios quedaron `healthy`.

## Las imágenes no llevan `backend_web`

```bash
docker run --rm --entrypoint sh epidemia-usuarios -c 'ls /app; python -c "import backend_web"; ls /app/microservicios'
docker run --rm --entrypoint sh epidemia-corridas -c 'ls /app; python -c "import backend_web"; ls /app/microservicios'
```

```
usuarios                          corridas
  /app: docs microservicios         /app: docs microservicios procesamiento
  ModuleNotFoundError:              ModuleNotFoundError:
    No module named 'backend_web'     No module named 'backend_web'
  /app/microservicios: comun usuarios   /app/microservicios: comun corridas
```

- `usuarios` parte de `epidemia/base-identidad` (281 MB): solo `epidemia_comun` y su carpeta.
- `corridas` parte de `epidemia/base-simulacion` (368 MB): agrega `procesamiento/` (el motor), que
  no importa Flask ni toca la base.
- Los dos se construyen con `additional_contexts` desde su propia base; ninguno copia otro servicio.

## Límites

- Los servicios fuera de identidad y simulación siguen en `epidemia/base`, que todavía lleva
  `backend_web` (pendiente en el checklist E8 para los bloques D y F).
- `epidemia_comun` es compartido por todos: un cambio ahí sí obliga a reconstruir todos los
  servicios que lo copian. Es la biblioteca técnica, no reglas de negocio.
