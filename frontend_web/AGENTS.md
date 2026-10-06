# AGENTS.md — frontend_web

> **Estado: Vigente** · 2026-10-06 · Complementa el `AGENTS.md` de la raíz.

- Para una ruta con formulario, sigue `reporte_nuevo` en `app/routes.py`.
- Lo que solo existe por cómo funciona la página (campos ocultos de concurrencia, semilla en
  blanco, casillas marcadas) se lee con `app/formularios.py`. Convertir texto a número o fecha
  es de `backend_web/conversion.py`, porque una API también lo necesitaría.
- Los candados actuales mandan al dashboard a quien rechazan. Si un rol no puede ver el
  dashboard, usa `abort(403)` para no crear un ciclo de redirecciones.
