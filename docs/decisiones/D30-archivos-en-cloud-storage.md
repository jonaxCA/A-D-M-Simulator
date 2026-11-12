# D30 - Archivos en Cloud Storage

Fecha: 2026-11-11 · Estado: Aceptada

## Contexto

## Opciones consideradas

## Decisión
Evidencias pasa de disco local a un bucket, con URLs firmadas para los archivos privados. 
PostgreSQL guarda solo identificador, ruta, tipo, tamaño, propietario, fecha, hash y privacidad.
En local se puede simular con un emulador de GCS o con una interfaz que cambie de disco a bucket por variable de entorno.


## Consecuencias
