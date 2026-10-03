# AGENTS.md — frontend_web

> **Estado: Vigente** · 2026-09-25 · Complementa el `AGENTS.md` de la raíz.

- Para una ruta con formulario, sigue `reporte_nuevo` en `app/routes.py`.
- Los candados actuales mandan al dashboard a quien rechazan. Si un rol no puede ver el
  dashboard, usa `abort(403)` para no crear un ciclo de redirecciones.
