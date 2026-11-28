> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RNF-H: Despliegue

Dónde corre el sistema: igual en la máquina de cada quien que en Google Cloud. El diagrama está en [`arquitectura_v3.md`](../../arquitectura/arquitectura_v3.md) (§8). Cómo leer la tabla: [`README.md`](../README.md).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Componente | Estado |
|---|---|---|---|---|
| RNF-H01 | El sistema corre con Docker en la máquina de cualquier integrante | Las imágenes se construyen desde sus Dockerfile, sin pasos a mano | Infraestructura | Hecho |
| RNF-H02 | El sistema se despliega en Compute Engine | La máquina principal corre el mismo `infra/docker-compose.yml` que en local, con nginx enfrente y una IP fija | Infraestructura | Falta (N1) |
| RNF-H05 | Un solo comando levanta todo en local | `docker compose -f infra/docker-compose.yml --profile identidad --profile catalogos --profile vigilancia --profile escenarios --profile simulacion --profile analitica --profile plataforma up -d --build --wait` levanta PostgreSQL con la base de la demostración, Redis, MongoDB y los servicios; `simulador-gpu` va aparte, con `--profile gpu` | Infraestructura | Hecho; falta agregar nginx (D25) |
| RNF-H06 | La GPU es opcional | Sin GPU, `abm-ref` hace lo mismo que `abm-gpu`, más despacio | Microservicios, Infraestructura | Hecho |
| RNF-H07 | La máquina con GPU está separada de la principal | Corre solo `simulador-gpu` y llega a PostgreSQL y a Redis por la red interna | Infraestructura | Falta (N1) |
| RNF-H16 | nginx es la única entrada (D25) | `https://<dominio>/<servicio>/api/v1/...` llega a cada servicio sin cambiar sus rutas. nginx no valida tokens ni tiene lógica | Infraestructura | Falta (S6) |
| RNF-H17 | Las bases corren en contenedores en la máquina principal | PostgreSQL, Redis y MongoDB van en el mismo compose; la justificación está en la arquitectura v3 (§8) | Infraestructura, Bases de datos | Falta (N1) |
| RNF-H18 | Hay un diagrama de distribución en la nube | Muestra la web, los servicios, PostgreSQL, MongoDB, Redis, los archivos y el monitoreo | Infraestructura | En parte: está como propuesta en la arquitectura v3 (N2) |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RNF-H03 | Red privada | Pasa a RNF-D09 |
| RNF-H04 | Secret Manager | Pasa a RNF-D03 |
| RNF-H08 | Entornos de desarrollo, pruebas y producción | Hay dos: local y la nube, con el mismo compose |
| RNF-H09 | Imágenes reproducibles | Se cubre con RNF-H01 |
| RNF-H10 | Regresar a la versión anterior de un servicio | No lo pide la rúbrica |
| RNF-H11 | Sin atarse a un proveedor | La materia pide Google Cloud (RNF-L09) |
| RNF-H12 | Almacenamiento compatible con S3 | D30 fija Cloud Storage, con un emulador o disco en local |
| RNF-H13 | Desarrollo en Windows, macOS y Linux | No se comprobó en los tres |
| RNF-H14 | Imágenes de menos de 1 GB | No hay con qué exigirlo; la imagen con GPU es más grande |
| RNF-H15 | Arranque completo en menos de 5 minutos | No está medido |
