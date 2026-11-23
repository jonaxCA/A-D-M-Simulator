# D54 - El menú de la app móvil por perfil

Fecha: 2026-11-23 · Estado: Aceptada (la correspondencia de perfiles la aprobó el líder; el alcance de la app, el dueño del bloque F) · Atiende B4 «Menú para cada perfil de campo» · Amplía D1, D42, D43 y D49

## Contexto
La retroalimentación pide que la app tenga un menú para capturistas, personal de vigilancia,
supervisores regionales y responsables de campañas. D42 tiene seis perfiles y ninguno se llama así.
La app solo distinguía al CAPTURISTA del resto, y el servidor negaba casi todo a INVESTIGADOR y
AUTORIDAD_SANITARIA (no estaban en los candados de `casos`, `vacunas` ni `dispositivos`), así que
ni siquiera registraban su teléfono.

## Opciones consideradas
- A) Emparejar los perfiles de campo con los de D42 y armar el menú con eso.
- B) Perfiles nuevos (supervisor regional, responsable de campaña): cambia D42, pide migración y
  nadie los tiene.
- Para el EPIDEMIOLOGO: 1) que no entre a la app; 2) que entre solo a consultar; 3) que además
  valide y descarte desde la app (D47 lo permite en el servidor); 4) que capture (cambia D1).

## Decisión
**A**, y el EPIDEMIOLOGO entra **solo a consultar** (2): validar y descartar se quedan en la web y
capturar sigue siendo solo del CAPTURISTA (D1, migración 034).

| Perfil de campo | Perfil (D42) |
|---|---|
| Capturista | CAPTURISTA |
| Personal de vigilancia | EPIDEMIOLOGO |
| Supervisor regional | AUTORIDAD_SANITARIA, con su región (D42) y su alcance (D43) |
| Responsable de campaña | EPIDEMIOLOGO, que crea y cancela las campañas (D49); las dosis las aplica el CAPTURISTA |

ANALISTA, INVESTIGADOR y ADMINISTRADOR no son de campo.

| En el inicio | CAPTURISTA | EPIDEMIOLOGO | AUTORIDAD_SANITARIA | ANALISTA / INVESTIGADOR | ADMINISTRADOR |
|---|---|---|---|---|---|
| Capturar caso | ✓ | — | — | — | — (D1) |
| Mis casos, seguimiento y fotos | ✓ | — | — | — | — |
| Casos del servidor (el seguimiento, solo para leer) | — | ✓ | ✓ su alcance | — | ✓ |
| Campañas | ✓ | ✓ | ✓ | — | ✓ |
| Lotes de vacuna | registrar y aplicar | consultar | consultar | — | registrar y aplicar |
| Consulta por zona | ✓ | ✓ | ✓ su alcance | ✓ | ✓ |
| Avisos y Mi perfil | ✓ | ✓ | ✓ | ✓ | ✓ |

- El panel del inicio cambia: el CAPTURISTA ve lo que tiene por enviar, sus datos faltantes y sus
  formularios; quien revisa, los casos por validar de su alcance y las campañas activas.
- Sin roles conocidos (una sesión de antes de guardarlos y sin red) queda el menú del CAPTURISTA,
  como antes (RF-I19). Quien niega es el servidor; el menú solo ordena el inicio.
- En el servidor (bloque F): INVESTIGADOR y AUTORIDAD_SANITARIA leen en `casos` (cases.read de D42)
  y en `vacunas` (lotes y campañas), y registran su teléfono en `dispositivos`. Y el alcance por
  región (D43) se aplica en todas las lecturas de `casos` (lista, incompletos, detalle e historial)
  y en la tabla de `zonas` y su exportación: una cuenta con alcance solo ve sus municipios y pedir
  uno ajeno es 403.

## Consecuencias
- La app suma dos pantallas, Casos y Campañas, y los lotes en modo de consulta.
- Las fotos de un caso las lee `evidencias` (bloque D), que todavía no deja a AUTORIDAD_SANITARIA ni
  a INVESTIGADOR: en el seguimiento, la app dice que su perfil no ve fotos. Abrirles la lectura es
  de D.
- D43 queda aplicado en `casos` y en la tabla de `zonas`; falta en el mapa, el mapa de calor, las
  jurisdicciones, `series` e `indicadores`.
- `notificaciones` todavía no tiene avisos para AUTORIDAD_SANITARIA (TIPOS_POR_ROL): su bandeja
  funciona, pero no le llega nada propio.
