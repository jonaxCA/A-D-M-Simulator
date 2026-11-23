# D52 - Retención de los datos

Fecha: 2026-11-22 · Estado: Aceptada · Atiende RNF-K07 (y RNF-I14, que pasó a él) · Amplía D19, D28 y D30

## Contexto
RNF-K07 pide que el inventario de datos (`docs/arquitectura/matrices_v3.md` §2) diga cuánto vive cada
tabla, colección y archivo. Redis ya tiene un TTL en cada llave (RNF-K05) y MongoDB lo tiene en
`historial_servicios` (30 días, D28), pero ningún documento fijaba plazos para PostgreSQL ni para el
bucket, y el inventario tenía 40 casillas «Por definir». La migración 010 trae
`system_settings.dias_retencion_evidencias` (1825 días), pero ningún código lo aplica, y no hay nada
que corra tareas programadas.

## Opciones consideradas
- Opción A: escribir la retención que ya tiene el sistema: cómo termina cada dato, sin purgas por
  antigüedad.
- Opción B: fijar plazos (por ejemplo, avisos leídos a los 90 días y evidencias a los 1825) y escribir
  una purga programada que los aplique.

## Decisión
Opción A. Mientras dure el proyecto, PostgreSQL y el bucket no borran nada por antigüedad. Cada dato
termina de una de estas formas, y el inventario dice cuál le toca:

- **No se borra.** `audit_log` (el trigger `tg_audit_log_inmutable` impide editarla o borrarla),
  `case_history` (solo se inserta), `cases` (se descarta o se marca duplicado, D47),
  `scenario_versions` (inmutable, D5), `simulation_batches`, `simulation_runs` y
  `schema_migrations`. Los catálogos que fijan las migraciones (`regions`, `region_age_groups`,
  `intervention_types`, `roles`, `permissions`, `role_permissions`, `system_settings`) tampoco.
- **Baja lógica.** `users.is_active`, `diseases.is_active`, `institutions.is_active`, la revocación de
  un dispositivo (`devices`, `session_devices`) y la cancelación de una campaña. La fila se queda.
- **Lo borra el ADMINISTRADOR, por error.** Una evidencia o un reporte (con su objeto en el bucket) y
  una cuenta sin dependencias (`usuarios` responde 409 si tiene casos, escenarios o corridas).
- **En cascada con su padre.** Lo que cuelga de una cuenta que se borra (dispositivos, roles,
  alcances, avisos, preferencias y MFA, `ON DELETE CASCADE`); `audit_log` conserva el asiento con
  `user_id` en nulo. Las evidencias, con su caso.
- **Se reemplaza.** `user_roles` y `user_scopes` al reasignarlos, los códigos de respaldo al volver a
  enrolar el MFA, el ajuste vigente de `region_population_adjustments` y las intervenciones de una
  versión en borrador. El cambio queda en `audit_log`.
- **TTL.** Las llaves de Redis (RNF-K05) y `historial_servicios` (30 días). La serie de
  `series_corridas` vive lo que su corrida, y se borra si la corrida se cierra como fallida (D38).
- **En el teléfono.** Los tokens, hasta cerrar sesión; los casos y fotos pendientes, hasta que se
  envían.

`dias_retencion_evidencias` queda sin aplicar. No se retira, porque la 010 no se edita (D7); si algún
día se purga, será otra decisión.

## Consecuencias
- RNF-K07 queda cubierto sin código nuevo: cada fila del inventario dice cómo termina su dato.
- El volumen crece sin tope. D29 midió que el sistema lo aguanta con 10 000 corridas de 180 días.
- Nada se pierde sin que alguien lo pida, y todo borrado deja su `DELETE` en la bitácora.
- Un despliegue real tendría que fijar plazos según la norma que le aplique a la vigilancia
  epidemiológica y a los datos personales; queda fuera de alcance. Archivar datos viejos (RNF-K06)
  sigue fuera.
