# Contrato del motor de simulación

> **Estado: Vigente** · 2026-11-12 · Sale de D2. La versión en código es
> `procesamiento/contrato.py`, y `procesamiento/tests/test_contrato_motor.py` revisa que cada
> motor lo cumpla.

A diferencia de las demás carpetas de `docs/contratos/`, esto no es una API HTTP: es la
interfaz en Python que cumplen los motores. La llama el `simulador` por cada corrida que toma
de la cola (`backend_web/simulaciones.py`, `ejecutar_run`), y `validacion` la usa para revisar
una versión antes de enviarla. Por eso no hay `openapi.json`.

## Motores

| Nombre | Qué es | Dónde | Estado |
|---|---|---|---|
| `seir-ref` | SEIR estocástico por grupo de edad. Queda como control experimental (D2) | `procesamiento/motor/` | Implementado |
| `abm-ref` | Modelo basado en agentes en Python, en CPU (D22): cada persona con su hogar, salón o centro de trabajo | `procesamiento/abm/` | Implementado; lo corre el contenedor `simulador-abm` |
| `abm-gpu` | El mismo modelo en FLAME GPU 2 (D23) | — | Solo si sobra tiempo |

- Los nombres son los de D2. Hasta la migración 035 eran `python-ref`, `numba` y `cuda`;
  `corridas` todavía acepta los anteriores en lo que manda el cliente y los traduce.
- `engine_version` es `<motor>-<mayor>.<menor>`, por ejemplo `seir-ref-0.1`. Sube cada vez que
  un cambio altera los números (`procesamiento/AGENTS.md`).
- Cómo funciona cada motor por dentro (variables, pseudocódigo, complejidad, validación y
  tiempos) está en la ficha del simulador,
  [`docs/arquitectura/ficha_simulador.md`](../../arquitectura/ficha_simulador.md).

## Interfaz

```python
simular(escenario: dict, semilla: int) -> dict
```

- **`semilla`:** entero mayor o igual a 0. Un `bool`, un flotante o un texto es `ValueError`.
- **Escenario inválido:** se levanta `procesamiento.motor.EscenarioInvalido` (subclase de
  `ValueError`), con todos los problemas en `.errores`, no solo el primero.
- **Falla durante la corrida:** se levanta `procesamiento.motor.ErrorMotor`.
- **Sin efectos:** no modifica el escenario que recibe, no toca la base ni la red, y todo el
  azar sale de la semilla.
- **Reproducible:** la misma entrada con la misma semilla y el mismo `engine_version` da
  exactamente la misma salida. Dos motores distintos no tienen por qué coincidir número por
  número; se comparan por distribución, con las mismas semillas (D8).

## Entrada

La arma `backend_web/queries.py` (`escenario_de_version`) a partir de la versión aprobada, con
los parámetros congelados al enviarla a revisión. La misma traducción sirve para revisar y para
correr. Las reglas completas están en `resolver` (`procesamiento/motor/parametros.py`): un
motor nuevo tiene que aceptar exactamente las mismas entradas, y lo más simple es que use
`resolver`.

| Campo | Qué es |
|---|---|
| `poblacion` | Personas simuladas: un entero o un objeto por grupo de edad (`{"0-19": …, "80+": …}`). Entre 1 000 y 20 000 000 (migración 023). Con D6 son agentes simulados; el factor de escala no entra al motor: lo calcula `procesamiento/analitica/escala.py`. |
| `infectados_iniciales` | Infectados el día 0. Se reparten entre los grupos según su tamaño. |
| `dias` | Horizonte, de 1 a 1 095. La serie tiene `dias + 1` filas. |
| `enfermedad` | `r0`, `incubacion_dias`, `infeccioso_dias`, `dias_hospitalizacion`, `tasa_hospitalizacion` y `letalidad`. Cada uno es un número, un objeto por grupo de edad (las dos tasas) o `{"valor", "fuente", "supuesto"}`. No hay valores por omisión: si falta uno, el escenario es inválido. |
| `intervenciones` | Lista de `{"tipo", "dia_inicio", "dia_fin", "cobertura", "cumplimiento", "params"}`. Los tipos son `CIERRE_ESCUELAS`, `CIERRE_TRABAJO`, `REDUCCION_AFORO`, `CUBREBOCAS`, `VACUNACION` y `TESTEO_AISLAMIENTO`; los `params` de cada uno están en `intervention_types.param_schema`. |
| `poblacion_edad_desconocida` y `politica_edad_desconocida` | Opcionales. La gente sin edad declarada y qué hacer con ella: `excluir` o `prorratear`. |
| `capas_contacto` | Opcional. Reparto de contactos entre hogar, escuela, trabajo y comunidad. Si no viene, se usa un supuesto que la salida reporta como tal. |

## Salida

Un diccionario que se puede serializar como JSON estricto (sin `NaN`). Estas llaves son
obligatorias y significan lo mismo en los tres motores. Un motor puede agregar llaves propias:
`seir-ref` agrega `numpy_version`.

| Llave | Qué es |
|---|---|
| `engine_version` | Nombre y versión del motor que corrió (`seir-ref-0.1`). |
| `semilla` | La semilla recibida. |
| `huella_escenario` | SHA-256 de la entrada canónica (`procesamiento.contrato.huella`). Todos los motores la calculan igual. Se guarda como `scenario_checksum`. |
| `dias` | El horizonte simulado. |
| `poblacion` | Personas o agentes simulados, sin factor de escala. |
| `serie` | Una fila por día (ver abajo). |
| `resumen` | Indicadores de la corrida (ver abajo). |
| `trazabilidad_parametros` | De dónde salió cada parámetro: `{"parametro", "valor", "fuente", "estado"}`, con `estado` igual a `con_fuente`, `sin_fuente` o `supuesto` (regla 8). |
| `simplificaciones` | Textos con lo que el modelo simplifica. Nunca va vacía; cada motor declara las suyas. |
| `avisos` | Textos con lo que se corrió distinto de lo pedido. Puede ir vacía. |

### `serie`

Del día 0 al último, todos los campos son enteros mayores o iguales a 0. Es la misma fila que
`docs/contratos/comun/serie.xsd` describe en XML.

| Campo | Qué es |
|---|---|
| `dia` | De 0 a `dias`. |
| `S`, `E`, `I`, `R`, `H`, `D`, `V` | Susceptibles, expuestos, infecciosos, recuperados, hospitalizados, fallecidos y vacunados protegidos al cierre del día. Su suma es `poblacion` todos los días. |
| `casos_activos` | `E + I + H`. |
| `nuevos_casos`, `nuevas_hospitalizaciones`, `nuevas_defunciones`, `dosis_aplicadas` | Lo que pasó ese día. El día 0 van en 0. |

### `resumen`

Sale de la serie con las mismas definiciones en todos los motores. `seir-ref` usa
`procesamiento/motor/indicadores.py` (`resumir`), y un motor nuevo puede usarla tal cual. Las
columnas generadas de `simulation_results` (migración 014) leen `casos_acumulados`,
`hospitalizaciones`, `fallecimientos`, `pico_casos_activos`, `dia_pico` y `tasa_ataque`: si
faltan, la base no da error, deja columnas vacías.

| Campo | Definición |
|---|---|
| `casos_acumulados` | `infectados_iniciales` más la suma de `nuevos_casos`. |
| `casos_activos_final` | `casos_activos` del último día. |
| `pico_casos_activos` y `dia_pico` | El máximo de `casos_activos` y el primer día en que se alcanza. |
| `pico_nuevos_casos` y `dia_pico_nuevos_casos` | Lo mismo con `nuevos_casos`. |
| `hospitalizaciones` | Suma de `nuevas_hospitalizaciones`. |
| `pico_hospitalizados` y `dia_pico_hospitalizados` | Lo mismo con `H`. |
| `fallecimientos` | `D` del último día. |
| `tasa_ataque` | `casos_acumulados / poblacion`, entre 0 y 1. |
| `vacunados_protegidos` | `V` del último día. |
| `dosis_aplicadas` | Suma de `dosis_aplicadas`. |
| `desglose_por_grupo` | Lista de `{"grupo", "poblacion", "casos", "fallecimientos", "vacunados_protegidos", "dosis_aplicadas"}`. Cada campo suma el total correspondiente. |

## Qué se guarda

`simulation_results` (migración 014) guarda `engine_version`, `huella_escenario`, `resumen`,
`serie` y `trazabilidad_parametros`. Con D28, la serie pasa a la colección `series_corridas` de
MongoDB, un documento por día con el `run_id` y el motor.

## Pendiente de acordar

- **Serie por grupo de edad.** D28 dice que `series_corridas` guarda los compartimentos por
  grupo de edad de cada día, pero la `serie` de hoy solo trae totales por día; por grupo solo
  vienen los totales finales de `desglose_por_grupo`. O se agrega una llave opcional con la
  serie por grupo, que tendrían que dar los tres motores, o MongoDB guarda totales. Se decide
  con quien implementa D28.

## Ejemplos

`ejemplos/entrada.json` (escenario y semilla) y `ejemplos/salida.json` son la salida real de
`seir-ref`. Una prueba revisa que sigan coincidiendo; si un cambio del motor altera los números,
se regeneran desde la raíz del repositorio:

```bash
python -m procesamiento.contrato --ejemplos
```

## Cómo se agrega un motor

1. Un paquete aparte en `procesamiento/` con `simular(escenario, semilla)`.
2. Valida y lee la entrada con `resolver`, y arma el resumen con `resumir` o con las mismas
   definiciones.
3. Su `engine_version` empieza con su nombre de esta tabla.
4. Se agrega a `IMPLEMENTADOS` en `procesamiento/motores.py`. Con eso pasa solo por las pruebas
   de conformidad, `corridas` registra su versión y `resultados` muestra sus simplificaciones.
5. Su simulador es otro contenedor del servicio `simulador` con `SIMULADOR_MOTOR=<nombre>`, y
   `corridas` lo acepta cuando `MOTORES_HABILITADOS` lo nombra.
