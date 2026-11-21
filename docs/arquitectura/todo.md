# Archivos a poner:

- vision_general.md
- diagramas/

# Nuevos microservicios:

App móvil: sí pide 3 servicios nuevos, que ya están entre los opcionales: dispositivos (sin él no se puede mandar device_id), evidencias (las fotos) y vacunas (los QR de lotes).

# Cambios de desarrollo-movil en arquitectura_v2.md

La rama `desarrollo-movil` cambia dos cosas en `arquitectura_v2.md`. Se conserva el `arquitectura_v2.md` de esta rama y estos cambios se aplican aquí, después de verificarlos:

- El encabezado dice «El plan de 26 servicios»; la rama de móvil lo cambia a 29. Verificar el número contra `microservicios.md` antes de aplicarlo.
- La fila de `usuarios` agrega `GET /api/v1/users/me`, con acceso para cualquier rol con token. Lo demás de la fila no cambia.
