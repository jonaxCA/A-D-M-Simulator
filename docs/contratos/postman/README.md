# Postman · tipos-intervencion, indicadores, series y zonas

Colección para comprobar que los servicios 5215, 5251, 5252 y 5253 cumplen su contrato:
salud, Swagger, XML y JSON, permisos y errores RFC 7807. Son 51 peticiones con pruebas
automáticas.

| Archivo | Qué es |
|---|---|
| `catalogos_analitica.postman_collection.json` | La colección, una carpeta por servicio |
| `local.postman_environment.json` | URLs de los servicios en `localhost`, `token` vacío y `disease_id` |

## 1. Levantar Redis y los servicios

```bash
cp infra/.env.example infra/.env          # escribe REDIS_PASSWORD
docker compose -f infra/docker-compose.yml up -d redis

export PYTHONPATH="$PWD:$PWD/microservicios/comun"
export DATABASE_URL="postgresql://epidemia_app:<contraseña>@localhost:5432/simulador_epidemico"
export REDIS_URL="redis://:<REDIS_PASSWORD>@127.0.0.1:6380/0"
export JWT_SECRET_KEY="<una cadena larga, solo para tu máquina>"

python -m microservicios.tipos_intervencion.app &   # 5215
python -m microservicios.indicadores.app &          # 5251
python -m microservicios.series.app &               # 5252
python -m microservicios.zonas.app &                # 5253
```

## 2. Sacar un token

Mientras no exista `auth`, este script abre una sesión real en Redis y firma un access con
los mismos claims. Usa las mismas variables de arriba:

```bash
TOKEN=$(python microservicios/comun/scripts/token_pruebas.py --roles ANALISTA)
```

## 3. Correr la colección

**En Postman:** importa los dos archivos, elige el entorno *EPIDEMIA local*, pega el token
en la variable `token` y corre la colección completa con el *Runner*. El orden importa:
la carpeta de zonas guarda el municipio que usa la de series.

**Desde la terminal:**

```bash
npx newman run docs/contratos/postman/catalogos_analitica.postman_collection.json \
  -e docs/contratos/postman/local.postman_environment.json --env-var "token=$TOKEN"
```

## Swagger

Cada servicio sirve su Swagger en `/docs`, con los ejemplos de `docs/contratos/<servicio>/ejemplos/`:

- http://localhost:5215/docs
- http://localhost:5251/docs
- http://localhost:5252/docs
- http://localhost:5253/docs

Ábrelo con `localhost`, no con `127.0.0.1`: el contrato declara `http://localhost:<puerto>`,
y con otro origen el navegador bloquea "Try it out". En `series` y `zonas`, pega el token
en **Authorize** (sin escribir `Bearer`).

## Si algo falla

- **Todo da 401 `TOKEN_REVOCADO`:** el token venció (20 min por omisión) o se generó con
  otro `JWT_SECRET_KEY` o contra otro Redis. Genera otro con las mismas variables.
- **`/health` da 503:** revisa en la respuesta si el que falla es `postgresql` o `redis`.
- **Series y zonas salen en ceros con 7 o 30 días:** la base no tiene casos recientes. La
  colección usa 90 días donde necesita datos.
