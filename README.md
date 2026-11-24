# EPIDEMIA — Simulador de respuesta a epidemias v0.0.1

Una plataforma para la vigilancia epidemiológica y la comparación de intervenciones políticas.
Con ella se arma un escenario, se simula un brote, se prueban medidas (cierres, vacunación) y se
comparan sus resultados y su costo. Los modelos son exploratorios: sirven para comparar opciones,
no predicen cifras reales ni dicen cuál conviene. Trabajamos con datos de demostración de Nuevo León.

Es un proyecto universitario, programado por Rolando Rivas Dávalos, Carlos Rodrigo Gómez González,
Jonathan Correa Ascencio, Mauricio Gallardo Barbosa, Luz Colunga, Victor Hugo Gutierrez Cavazos y
Enrique Ortiz Davila.

## Cómo está armado

En el sistema cuenta con 31 microservicios Flask, cada uno en su contenedor de Docker, con
PostgreSQL, MongoDB, Redis y JWT. Las tres aplicaciones hablan solo con ellos: el escritorio en XML y
el móvil en JSON.

| Carpeta                         | Qué hay                                                                                         |
|---------------------------------|-------------------------------------------------------------------------------------------------|
| `microservicios/`               | Los servicios: identidad, catálogos, vigilancia, escenarios, simulación, analítica y plataforma |
| `procesamiento/`                | Los motores: SEIR de referencia (`motor/`), modelo basado en agentes (`abm/`) y calibración     |
| `frontend_desktop/`             | App de escritorio (PySide6) para crear escenarios, lanzar corridas, compararlas y calibrar      |
| `frontend_web/`, `backend_web/` | Sitio web (Flask) para consultar, aprobar, ver el mapa y administrar                            |
| `frontend_movil/`               | App Android (Kotlin y Compose) para capturar casos en campo                                     |
| `datos/`                        | Migraciones y semillas de PostgreSQL, datos geográficos y scripts                               |
| `infra/`                        | Docker Compose, nginx, MongoDB, bucket y despliegue en la nube                                  |
| `pruebas_carga/`                | Pruebas de carga con Locust                                                                     |
| `docs/`                         | Arquitectura, contratos de cada servicio, decisiones, manuales, pruebas y el checklist          |

## Para correrlo

Necesitas Docker y Python 3.9 o superior. Desde la raíz del repositorio:

```bash
python -m venv .venv 
source .venv/bin/activate      # en Windows: .venv\Scripts\activate

pip install -r frontend_web/requerimientos.txt -r frontend_desktop/requerimientos.txt

python epidemia.py up        # levanta los microservicios (crea infra/.env con las contraseñas si falta)
python epidemia.py web       # el sitio queda en http://localhost:5000
python epidemia.py desktop   # abre la app de escritorio
python epidemia.py estado    # cómo van los contenedores (también: logs [servicio], pruebas, down)
```

Para entrar puedes usar la cuenta de prueba `diana.flores` / `Epidemia2026!`. La app móvil se abre con
Android Studio desde la carpeta `frontend_movil/` (ver su [README](frontend_movil/README.md)).

## Pruebas

```bash
python epidemia.py pruebas                  # motor, microservicios y escritorio
python -m pytest frontend_web backend_web   # estas usan la base de pruebas (docs/INSTALACION.md)
```

## Dónde seguir leyendo

- Instalación a mano, base de pruebas y problemas frecuentes: [docs/INSTALACION.md](docs/INSTALACION.md).
- Despliegue de la nube (https://epidemos.app): [docs/DESPLIEGUE_GCP.md](docs/DESPLIEGUE_GCP.md).
- Funciones de cada servicio: [docs/arquitectura/microservicios.md](docs/arquitectura/microservicios.md).
- Decisiones arquitecturales: [docs/decisiones/decisiones.md](docs/decisiones/decisiones.md).
- Cómo colaborar: [CONTRIBUTING.md](CONTRIBUTING.md).
