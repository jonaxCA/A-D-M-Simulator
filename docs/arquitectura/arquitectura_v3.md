# Arquitectura v3

> **Estado: Borrador** · 2026-11-12. Mientras tanto manda `arquitectura_v2.md`.

Cada sección dice qué escribir y qué brechas (`brechas_v3.md`) y decisiones cubre. Borra la guía en cursiva al llenarla. Enlaza en vez de copiar.

## 1. Qué cambia respecto a la v2

_Tabla corta: tema, v2, v3, decisión (nginx, MongoDB, GCS, límites de consumo, ABM, GCP)._

## 2. Vista general

_Diagrama con clientes, nginx, servicios, simulador y almacenes. D4, D20, D25._

## 3. Procesos

_Resumen de P1, P2 y P3 y qué pieza les falta (Redis, MongoDB, GCS, auditoría, notificación). Detalle en `procesos_v3.md`. I1._

## 4. Clientes

_Web, Android y escritorio: qué hace cada uno y por qué rol. C3, C8, C9, C10, D-5._

## 5. Microservicios

_Solo lo que cambia: nginx, JWT con Redis, límites de consumo, servicios modificados. Catálogo en `microservicios.md`. I3, S2, N7, D25, D31._

## 6. Datos

_Qué va a PostgreSQL, Redis, MongoDB y GCS. Diseño de MongoDB (colecciones, índices, versionamiento, crecimiento) y URLs firmadas. D-1 a D-4, D28, D30._

## 7. Simulador

_Ciclo de una corrida, ficha del algoritmo (entradas, salidas, complejidad, pseudocódigo, pruebas, tiempos) y réplicas. A1 a A3, D6, D8, D22, D24._

## 8. Despliegue y seguridad

_Diagrama en GCP, firewall, HTTPS, secretos y logs. N1, N2, N6, S5, S6, D26._

## 9. Monitoreo, fallos y rendimiento

_Health check, panel, pruebas de caída, volumen de datos y Locust. N3 a N5, D-6, A4, A5, D29._

## 10. Fuera de alcance

_Calibración (D24), FLAME GPU (D23), resumen de réplicas en el servidor (D8)._

## 11. Cotejo con la rúbrica

_Cada punto del tercer parcial y la sección que lo cubre._
