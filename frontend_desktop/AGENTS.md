# AGENTS.md — frontend_desktop

> **Estado: Vigente** · 2026-11-08 · Complementa el `AGENTS.md` de la raíz.

App de escritorio del tercer parcial (D10), para ANALISTA y ADMINISTRADOR. El proceso que
atiende lo fija D4. Cómo instalarla y qué hace: `README.md`.

```
run.py            python -m frontend_desktop.run
app/
  config.py       URL del directorio, ruta a los XSD, roles, motores y réplicas
  xmlio.py        leer/escribir el XML de los servicios (mismo formato que epidemia_comun)
  esquemas.py     qué XSD de docs/contratos valida cada respuesta
  api.py          Cliente: directorio, token, renovación, errores RFC 7807, bitácora
  servicios.py    una función por ruta de servicio
  resumen.py      D8 en el cliente: réplicas por semilla, media/mediana/p5–p95, frontera
  exportar.py     CSV, reporte HTML, PDF
  bitacora.py     registro local de actividad
  ui/             PySide6: login, ventana y una vista por pantalla
tests/            pytest; test_humo.py usa los ejemplos de docs/contratos
```

## Reglas

1. **Solo XML y solo microservicios.** No importes `backend_web`, `procesamiento` ni
   `epidemia_comun`. Si un dato no lo da un servicio, se pide al servicio; no se calcula aquí.
2. **Todas las peticiones pasan por `Cliente.pedir()` o `Cliente.enviar()`.** Ahí van el token,
   el `X-Correlation-ID`, la validación XSD y la bitácora.
3. **Un XSD nuevo en `docs/contratos` se registra en `esquemas.POR_RESPUESTA`,** por servicio y
   raíz.
4. **La red nunca corre en el hilo de la interfaz.** Usa `ui/tareas.en_hilo()`.
5. **La bitácora no guarda tokens, contraseñas ni cuerpos de petición.**
6. **Las pantallas de resultados muestran el `aviso` que manda el servidor** (regla 9), y la
   comparación no recomienda (regla 10).
7. **Python 3.9.** Las dependencias van en `requerimientos.txt`.
