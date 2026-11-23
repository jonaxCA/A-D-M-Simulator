> **Estado: Vigente** · 2026-11-19 · Cierra la brecha A2 (§10.4 de [`brechas_v3.md`](brechas_v3.md)) y la validación científica que pidió la retroalimentación del segundo parcial (§13 a §17). Las mediciones se repiten con `python -m procesamiento.mediciones`.

# Ficha del simulador

El algoritmo complejo del proyecto es la simulación de un brote bajo un paquete de intervenciones. Lo hacen tres motores con el mismo contrato ([`docs/contratos/motor/README.md`](../contratos/motor/README.md)):

- **`seir-ref`** (`procesamiento/motor/`): SEIR estocástico por grupo de edad. Queda como control experimental (D2).
- **`abm-ref`** (`procesamiento/abm/`): modelo basado en agentes en Python (D22). Cada persona es un agente con su hogar, su salón o su centro de trabajo.
- **`abm-gpu`** (`procesamiento/abm_gpu/`): el mismo modelo en FLAME GPU 2, en una GPU de NVIDIA (D23). `abm-ref` queda como su respaldo en CPU.

Sobre sus resultados trabajan dos cálculos de `procesamiento/analitica/`: la frontera de Pareto (costo contra impacto, D3) y el factor de escala (D6).

## 1. Problema que resuelve

Para una enfermedad y una región de Nuevo León, estimar cómo evolucionaría un brote (casos, hospitalizaciones, fallecimientos, vacunados) con y sin intervenciones: cierre de escuelas o trabajos, reducción de aforo, cubrebocas, testeo con aislamiento y vacunación. Así se comparan paquetes de intervenciones por su impacto contra su costo, y la frontera de Pareto muestra cuáles no son peores que otro en los dos ejes.

Los resultados son **escenarios, no pronósticos**: no hay calibración contra datos observados (D24).
- Toda corrida es *exploratoria* (D39, §17): el modelo está verificado (§13 a §15), no validado.
- Por eso `resultados`, `comparacion`, `pareto` y la web ponen ese aviso junto a cada resultado (`AVISO_SIMULACION`).
- La ficha de cada modelo está en la §16.

`abm-ref` existe para medir lo que el SEIR no ve. El SEIR mezcla a toda la población por igual; en el ABM el contagio se queda en hogares, salones y centros de trabajo, y se agota antes. La diferencia entre los dos, en los mismos escenarios y con las mismas semillas, es el aporte del ABM (D2).

## 2. Dónde corre

```mermaid
flowchart LR
    E[App de escritorio] -->|POST /api/v1/runs| C[corridas]
    C -->|corrida encolada| PG[(PostgreSQL)]
    C -->|id| Q[(Redis<br/>queue:simulaciones:motor)]
    Q --> S1[simulador<br/>seir-ref]
    Q --> S2[simulador-abm<br/>abm-ref]
    Q --> S3[simulador-gpu<br/>abm-gpu]
    S1 & S2 & S3 -->|ejecutar_run| M[motor.simular]
    M --> PG
    S1 & S2 & S3 -->|avance| R[(Redis)]
    S1 & S2 & S3 -->|aviso| N[notificaciones]
    PG --> RS[resultados<br/>comparacion<br/>pareto]
    RS --> E
    PG --> W[Web]
```

1. `corridas` revisa que la versión esté aprobada (D5), registra la corrida en PostgreSQL con su motor y su versión, y la mete a la cola de Redis de ese motor.
2. El `simulador` de ese motor (`SIMULADOR_MOTOR`) la toma y llama a `ejecutar_run` (`backend_web/simulaciones.py`):
   - arma la entrada desde la versión, con los parámetros que se congelaron al enviarla a revisión;
   - corre `simular()` del motor del lote (`procesamiento/motores.py`);
   - guarda la serie diaria en la colección `series_corridas` de MongoDB y, después, el resumen en `simulation_runs` (D28); audita y avisa.
3. `resultados`, `comparacion` y `pareto` leen lo guardado. El factor de escala (D6) se calcula ahí, fuera del motor.

## 3. Entradas

`simular(escenario, semilla)`. El detalle de cada campo está en el contrato del motor.

| Entrada | Qué es |
|---|---|
| `poblacion` | Agentes simulados (D6): un total, o un conteo por grupo de edad (por ejemplo, del Censo 2020). |
| `infectados_iniciales` | Infectados el día 0, repartidos al azar entre los grupos según su tamaño. |
| `dias` | Horizonte, de 1 a 1 095. |
| `enfermedad` | `r0`, `incubacion_dias`, `infeccioso_dias`, `dias_hospitalizacion`, `tasa_hospitalizacion` y `letalidad`; las dos tasas, por grupo de edad. Cada uno con su fuente o marcado como supuesto. |
| `intervenciones` | Tipo, días de inicio y fin, cobertura, cumplimiento y los parámetros de su tipo. |
| `poblacion_edad_desconocida`, `politica_edad_desconocida` | Gente sin edad declarada en el censo, y si se excluye o se prorratea. |
| `capas_contacto` | Opcional: cómo se reparten los contactos entre hogar, escuela, trabajo y comunidad. |
| `semilla` | Entero mayor o igual a 0. Con ella, la corrida es reproducible. |

Fuera del motor, Pareto recibe además el costo unitario de cada tipo de intervención, y la escala, los habitantes de la región.

## 4. Salidas

| Salida | Qué es |
|---|---|
| `serie` | Una fila por día con `S`, `E`, `I`, `R`, `H`, `D`, `V`, los casos activos y lo nuevo de ese día (casos, hospitalizaciones, defunciones, dosis). |
| `resumen` | Casos acumulados, pico de casos activos y su día, hospitalizaciones, pico de hospitalizados, fallecimientos, tasa de ataque, vacunados protegidos y dosis, con su desglose por grupo de edad. |
| `trazabilidad_parametros` | De dónde salió cada parámetro (con fuente, sin fuente o supuesto). En `abm-ref` incluye los supuestos de la estructura de contactos. |
| `simplificaciones`, `avisos` | Lo que el modelo simplifica, y lo que se corrió distinto de lo pedido. |
| `engine_version`, `huella_escenario` | Qué motor y versión corrió, y la SHA-256 de la entrada. |

La analítica agrega la frontera de Pareto (costo contra una métrica de impacto) y la `escala` (cuántos habitantes representa cada agente y los conteos llevados a habitantes).

## 5. Variables

| Variable | Definición |
|---|---|
| Estado | `seir-ref`: cuántas personas hay en cada compartimento de cada grupo de edad. `abm-ref`: el compartimento de cada agente. |
| β | `r0 / infeccioso_dias`, la tasa de contagio por día de una persona infecciosa. |
| Probabilidades diarias | p_EI = 1 − e^(−1/incubación); p_sale_I = 1 − e^(−1/infeccioso); p_sale_H = 1 − e^(−1/hospitalización). |
| Reparto de quien sale de I | A H con `tasa_hospitalizacion`, a D directo con max(0, `letalidad` − `tasa_hospitalizacion`), a R el resto. En H muere con min(`letalidad`, `tasa_hospitalizacion`) / `tasa_hospitalizacion`. |
| Pesos de las capas | Hogar 0.35, escuela 0.15, trabajo 0.20 y comunidad 0.30 (supuesto, `CAPAS_CONTACTO_SUPUESTO`). |
| Efecto de una intervención | reducción × cobertura × cumplimiento, sobre su capa (o sobre todas); el testeo y aislamiento reduce la transmisión de todos los infecciosos. |
| Vacunación | Dosis diarias, tope por grupo (cobertura), prioridad (`edad_desc` o `aleatorio`) y eficacia. |
| Grupos de contacto (`abm-ref`) | Hogar, salón y centro de trabajo de cada agente, con tamaños medios de 3.5, 25 y 15 (supuestos). |
| escala_j (`abm-ref`) | Reparte el peso de las capas a las que el agente no pertenece entre las suyas, para que su contacto total sea el del SEIR. |
| Factor de escala (D6) | Habitantes de la región (Censo 2020) / agentes. |

**Fuerza de infección.** En `seir-ref` es la misma para todos:

    λ(t) = β · aislamiento(t) · Σ_capa peso_capa · contactos_capa(t) · I / vivos

En `abm-ref` es de cada susceptible j, con la fracción de infecciosos entre los demás vivos de su hogar, salón o trabajo, y entre todos los vivos en la comunidad:

    λ_j(t) = β · aislamiento(t) · escala_j · Σ_capa peso_capa · contactos_capa(t) · x_capa,j

Con un solo grupo por capa, λ_j es la λ del SEIR (sección 10). Cada susceptible se contagia con probabilidad 1 − e^(−λ).

## 6. Restricciones

- **Validación de la entrada** (`resolver`, igual en los tres motores): población de 1 000 a 20 000 000; horizonte de 1 a 1 095 días; ningún parámetro epidemiológico tiene valor por omisión; las tasas van entre 0 y 1; cada intervención trae sus parámetros obligatorios; priorizar por edad exige grupos de edad. Un escenario inválido regresa todos sus errores juntos.
- **Reproducibilidad:** la misma entrada con la misma semilla y la misma `engine_version` da exactamente la misma salida. En `seir-ref` y `abm-ref` todo el azar sale de `np.random.default_rng(semilla)`, en un orden fijo. En `abm-gpu` la población sale de ese mismo generador y la epidemia del de FLAME GPU (cuRAND), así que la corrida se repite en la misma GPU y con la misma versión de FLAME GPU.
- **Trazabilidad (regla 8):** cada parámetro y cada supuesto lleva su fuente o la marca de supuesto. No hay calibración (D24).
- **Solo versiones aprobadas** (D5): lo revisa `corridas` y, como última defensa, el trigger `fn_version_aprobada`.
- **Recursos de `abm-ref`:** la memoria crece con los agentes, unos 88 MB por millón (sección 12).
- **Recursos de `abm-gpu`:** una GPU de NVIDIA con CUDA 13, y unos 230 MB de su memoria por millón de agentes (sección 12).

## 7. Complejidad

T es el número de días, G el de grupos de edad, N el de agentes, I el de intervenciones y k el de escenarios comparados.

| Cálculo | Tiempo | Memoria |
|---|---|---|
| `seir-ref` | O(T · (G + I)): cada día son sorteos binomiales por grupo, sin importar cuántas personas tenga. | O(G + T) |
| `abm-ref`: armar la población | O(N): permutaciones al azar y agrupación por tamaños. | O(N) |
| `abm-ref`: la corrida | O(T · N): cada día recorre a los agentes (estados, conteos por grupo con `bincount` en tres capas, un sorteo por susceptible). | O(N): unos 20 bytes por agente durante toda la corrida, y unos 88 en el pico por los arreglos de cada día |
| `abm-gpu`: la corrida | O(T · N) operaciones, como `abm-ref`, pero en paralelo: un hilo de la GPU por agente. Cada día son tres funciones de agente y tres o cuatro funciones de host; los días de vacunación, además, un ordenamiento de los agentes, O(N). | O(N) en la GPU: unos 230 MB por millón de agentes. En la CPU, la población que arma NumPy |
| Costo de un escenario (Pareto) | O(I · T) | O(I) |
| Frontera de Pareto | O(k²): cada escenario se compara con los demás; `comparacion` acepta hasta 50. | O(k) |
| Comparación con r réplicas de v versiones (D8) | r · v corridas independientes; se reparten entre simuladores. | Lo de una corrida por simulador |

## 8. Pseudocódigo

**Un día de `seir-ref`** (`procesamiento/motor/modelo.py`):

```
para cada día t = 1..T:
    activas ← intervenciones vigentes en t
    λ ← β · aislamiento(activas) · contactos(activas) · I_total / vivos
    nuevos_E ← Binomial(S, 1 − e^(−λ))                        por grupo
    nuevos_I ← Binomial(E, p_EI)
    salen_I  ← Binomial(I, p_sale_I);  destino ← Multinomial(salen_I, [a H, a D, a R])
    salen_H  ← Binomial(H, p_sale_H);  mueren_H ← Binomial(salen_H, muerte en H)
    actualizar S, E, I, H, D, R
    para cada campaña de vacunación activa:
        repartir las dosis del día por prioridad, hasta el tope de cada grupo
        las que caen en susceptibles protegen con probabilidad = eficacia (S → V)
    revisar que S + E + I + R + H + D + V = población
    anotar la fila del día
resumen ← indicadores de la serie
```

**`abm-ref`** (`procesamiento/abm/`):

```
agentes ← un agente por persona, con su grupo de edad
hogares ← agentes al azar en grupos de tamaño 1 + Poisson(2.5)
salones ← agentes en edad escolar, en grupos de 1 + Poisson(24)
trabajos ← agentes en edad laboral, en grupos de 1 + Poisson(14)
escala_j ← peso total / peso de las capas del agente
infectar al azar a infectados_iniciales agentes
para cada día t = 1..T:
    para cada capa agrupada: contar infecciosos y vivos por grupo
    para cada susceptible j:
        λ_j ← β · aislamiento(t) · escala_j · Σ_capa peso · contactos_capa(t) · infecciosos_del_grupo / (vivos_del_grupo − 1)
        se contagia si un número al azar < 1 − e^(−λ_j)
    E → I, I → H/D/R y H → D/R con las mismas probabilidades que seir-ref, un sorteo por agente
    vacunación: el cupo de cada grupo como en seir-ref, a agentes al azar sin dosis previa
    anotar la fila del día con los conteos por estado
resumen ← los mismos indicadores que seir-ref
```

**Un día de `abm-gpu`** (`procesamiento/abm_gpu/`). La población inicial es la de `abm-ref`, armada con el mismo código; las capas corren en este orden:

```
prepara_dia (host):  pesos del día de cada capa con las intervenciones activas;
                     conteos por grupo de contacto en cero
cuenta (agentes):    cada agente vivo suma 1 a los vivos de su hogar, salón y trabajo,
                     y si es infeccioso también a sus infecciosos (sumas atómicas)
avanza (agentes):    cada agente aplica su transición con la fórmula de abm-ref
                     (λ_j del susceptible con los conteos de cuenta)
si hay vacunación hoy:
  reparte_vacunas (host): dosis por grupo de edad como en abm-ref; ordena a los agentes
                          por (grupo de edad, se puede vacunar, número al azar)
  vacuna (agentes):       el agente cuyo lugar en su grupo cae en el corte de una campaña
                          recibe la dosis, y queda protegido con probabilidad = eficacia
fin del día (host):  contar agentes por estado y anotar la fila del día
```

**Frontera de Pareto** (`procesamiento/analitica/pareto.py`):

```
para cada escenario p:
    p está dominado si algún otro q tiene costo(q) ≤ costo(p) e impacto(q) ≤ impacto(p),
    y es estrictamente menor en al menos uno de los dos
frontera ← los no dominados, ordenados por costo
```

## 9. Casos de prueba

Desde la raíz: `python -m pytest procesamiento/tests`. Son 113 pruebas. Las de `abm-gpu` solo corren con `pyflamegpu` y una GPU de NVIDIA (`procesamiento/abm_gpu/README.md`); sin ellos se saltan y lo reportan.

| Archivo | Pruebas | Qué revisa |
|---|---|---|
| `test_motor.py` | 40 | `seir-ref`: misma semilla, misma corrida; la población se conserva todos los días; con R0 menor que 1 no hay brote; más R0, más ataque; cerrar escuelas reduce casos; vacunar a mayores de 60 reduce muertes; priorizar por edad salva más que al azar; las dosis no pasan la cobertura; la validación junta todos los errores y no inventa valores. |
| `test_caracterizacion_motor.py` | 4 | Salidas de referencia guardadas: cualquier cambio en los números se nota. |
| `test_resolver_robustez.py` | 1 | Un corpus de entradas raras: la validación nunca truena. |
| `test_contrato_motor.py` | 17 | Los motores que corren en la máquina cumplen el contrato, son reproducibles, no modifican su entrada y fallan igual ante un escenario o una semilla inválidos. Un motor que no corre ahí (`abm-gpu` sin GPU) no se entrega. |
| `test_abm.py` | 9 | Con un solo grupo por capa, `abm-ref` da lo mismo que el SEIR; con grupos reales el contagio se agota antes; cerrar escuelas protege más a los escolares; vacunar reduce los casos; la vacunación por edad empieza por los mayores y nadie pasa del tope ni recibe dos dosis; los grupos de contacto siguen la edad y su tamaño medio; sin grupos de edad, el reparto se sortea con el censo y se avisa. |
| `test_abm_gpu.py` | 9 | `abm-gpu` arranca con la misma población que `abm-ref`; con un solo grupo por capa da lo mismo que el SEIR, y con grupos reales lo mismo que `abm-ref`; cerrar escuelas protege más a los escolares; da las mismas dosis por grupo que `abm-ref`; con dos campañas a la vez nadie recibe dos dosis; corre sin grupos de edad; la telemetría de FLAME GPU está apagada. |
| `test_escala.py` | 5 | El factor de D6 y los conteos llevados a habitantes. |
| `test_pareto.py` | 28 | Dominancia, frontera, costo de cada intervención, comparación y que la analítica solo use nombres públicos del motor. |

Además, `backend_web` prueba una corrida completa de `seir-ref` y de `abm-ref` contra la base de pruebas. En contenedores, `test_compose_abm.py` y `test_compose_gpu.py` (de `microservicios/pruebas_integracion/contenedores/`) corren una de `abm-ref` y una de `abm-gpu` de punta a punta; la de GPU solo con `python infra/pruebas_integracion.py --gpu`.

## 10. Métricas

**De resultado**, las que se comparan entre escenarios: casos acumulados, pico de casos activos y su día, hospitalizaciones, pico de hospitalizados, fallecimientos, tasa de ataque y dosis aplicadas. Con D6 también se muestran llevadas a habitantes.

**De una comparación (D8):** 30 réplicas por omisión, con las mismas semillas (1 a N) en todos los escenarios. Por escenario se resumen la media, la mediana y la banda del percentil 5 al 95, y la frontera de Pareto se calcula sobre las medianas. Este parcial lo calcula el escritorio (`frontend_desktop/app/resumen.py`); el aviso de bandas encimadas está pendiente (integrante 6).

**De validación.** Que los ABM con un solo grupo por capa den la tasa de ataque de `seir-ref` prueba que su fórmula no cambia nada más que la agrupación. Con hogares, salones y trabajos el ataque baja, sobre todo cerca del umbral. Y `abm-gpu` da lo mismo que `abm-ref` dentro del ruido entre semillas: los dos son el mismo modelo.

<!-- python -m procesamiento.mediciones validacion · Python 3.14.4, NumPy 2.3.5, pyflamegpu 2.0.0rc5, Windows 11 -->
| R0 | `seir-ref` | `abm-ref`, un grupo por capa | `abm-ref`, hogares, salones y trabajos | `abm-gpu`, un grupo por capa | `abm-gpu`, hogares, salones y trabajos |
|---|---|---|---|---|---|
| 1.3 | 0.496 | 0.496 | 0.157 | 0.504 | 0.146 |
| 1.6 | 0.718 | 0.721 | 0.590 | 0.718 | 0.586 |
| 2.5 | 0.922 | 0.921 | 0.882 | 0.921 | 0.883 |

Tasa de ataque media de 5 semillas, con 100 000 agentes, 180 días y sin intervenciones.

**De rendimiento:** segundos por corrida y memoria pico (sección 12).

## 11. Limitaciones

- **Sin calibración (D24):** no hay serie histórica ni fuente para ajustar los parámetros. Los que no tienen fuente van marcados como supuesto, y los resultados se leen como escenarios.
- **Duraciones geométricas** en pasos de un día: de cada distribución solo se usa la media.
- **El R0 que corre no es el nominal (§13):**
  - Quien entra a I se queda en promedio 1 / (1 − e^(−1/D)) días, no D. Con D = 5 son 5.52 días.
  - Con β = R0 / D, cada caso contagia en promedio β · 5.52, unos 10 % más que el R0 capturado (`r0_efectivo` en `procesamiento/mediciones.py`).
  - Afecta a los tres motores, porque comparten las probabilidades diarias.
  - Corregirlo (por ejemplo, con β = R0 · p_sale_I) cambia los resultados, así que pide subir `engine_version`. Es una decisión del equipo, pendiente.
  - Mientras tanto, el R0 de un escenario se lee como «R0 nominal», y la ficha da el efectivo.
- **Mezcla homogénea:** en `seir-ref` entre toda la población; en `abm-ref`, dentro de cada grupo de contacto y en la comunidad.
- **Estructura supuesta en `abm-ref`:** los tamaños de hogar, salón y trabajo y los pesos de las capas son supuestos, y los hogares se arman al azar, sin la composición por edad real. Quién estudia o trabaja sale del grupo de edad.
- **Testeo y aislamiento** como un factor sobre todos los infecciosos; no se aísla a personas concretas.
- **Enfermedades transmitidas por vector** (dengue, zika, malaria) aproximadas como contagio directo, sin mosquitos ni estacionalidad.
- **El factor de escala (D6) es una extrapolación:** supone que los habitantes no simulados se comportan como los simulados.
- **`abm-ref` corre en un solo núcleo:** Nuevo León completo tarda más de un minuto por corrida, y 30 réplicas de varias versiones, decenas de minutos. Para eso está `abm-gpu`; sin GPU, se simulan menos agentes que habitantes (D6) o se reparten las corridas entre varios `simulador-abm`.
- **`abm-gpu` necesita una GPU de NVIDIA:** en la PC de desarrollo corre con el venv de `procesamiento/abm_gpu/README.md`, y en Docker Desktop con WSL 2 corre la imagen `simulador-gpu` (probada de punta a punta el 2026-11-14). Falta la máquina con GPU en GCP.
- **`abm-gpu` no sigue la misma corrida que `abm-ref`:** usa otro generador de azar. Se comparan promedios de varias semillas, no corridas.
- **La primera corrida de cada tamaño de población en `abm-gpu`** tarda de 9 a 17 s más, porque FLAME GPU compila sus funciones para ese tamaño. Lo compilado queda en caché, así que las réplicas de una versión compilan una sola vez.

## 12. Tiempo de ejecución

Medido con `python -m procesamiento.mediciones tiempos`: el escenario del contrato a 180 días, con cierre de escuelas y vacunación. Mediana de 3 corridas. Equipo: Intel Core i5-12450HX (8 núcleos, 12 hilos), 15.7 GB de RAM, Windows 11, Python 3.14.4 y NumPy 2.3.5, en un solo hilo; `abm-gpu` en una GeForce RTX 4050 Laptop (6 GB, driver 621.14) con pyflamegpu 2.0.0rc5 y CUDA 13.0. La memoria pico es la de Python; la de la GPU va aparte, abajo.

<!-- python -m procesamiento.mediciones tiempos · Python 3.14.4, NumPy 2.3.5, pyflamegpu 2.0.0rc5, Windows 11 -->
| Motor | Agentes | Días | Segundos | Memoria pico (MB) |
|---|---|---|---|---|
| `seir-ref` | 10,000 | 180 | 0.02 | 0 |
| `seir-ref` | 100,000 | 180 | 0.02 | 0 |
| `seir-ref` | 500,000 | 180 | 0.02 | 0 |
| `seir-ref` | 1,000,000 | 180 | 0.02 | 0 |
| `seir-ref` | 2,000,000 | 180 | 0.02 | 0 |
| `abm-ref` | 10,000 | 180 | 0.09 | 1 |
| `abm-ref` | 100,000 | 180 | 0.88 | 9 |
| `abm-ref` | 500,000 | 180 | 6.61 | 44 |
| `abm-ref` | 1,000,000 | 180 | 13.58 | 88 |
| `abm-ref` | 2,000,000 | 180 | 28.47 | 177 |
| `abm-gpu` | 10,000 | 180 | 0.31 | 0 |
| `abm-gpu` | 100,000 | 180 | 0.45 | 4 |
| `abm-gpu` | 500,000 | 180 | 0.73 | 22 |
| `abm-gpu` | 1,000,000 | 180 | 1.21 | 44 |
| `abm-gpu` | 2,000,000 | 180 | 2.38 | 89 |

- `seir-ref` tarda lo mismo con cualquier población: sus sorteos son por grupo, no por persona.
- `abm-ref` crece en proporción a los agentes: de 13 a 14 s y unos 88 MB por millón, o entre 12 y 14 millones de agentes-día por segundo.
- Por extrapolación, Nuevo León completo (5 784 442 habitantes, un agente por habitante) tardaría de 80 a 90 s y usaría unos 510 MB.
- 30 réplicas de una versión con un millón de agentes son unos 7 minutos en un solo `simulador-abm`.
- `abm-gpu` es de 9 a 12 veces más rápido que `abm-ref` desde medio millón de agentes. Con pocos agentes no conviene: con 10 000 pesa más lo fijo de cada día (las funciones de host en Python) que el trabajo de los agentes.
- Nuevo León completo en `abm-gpu`, medido: 7.7 s por corrida y unos 1 324 MiB de memoria de la GPU (230 MiB con un millón). 30 réplicas son unos 4 minutos, contra unos 45 de `abm-ref`.
- La primera corrida de cada tamaño suma la compilación (de 9 a 17 s); las tablas la dejan fuera con la mediana. El renglón de 100 000 agentes de `abm-gpu` se volvió a medir, porque en la primera pasada dos de las tres corridas compilaron.
- El máximo del validador, 20 millones de agentes, necesitaría por extrapolación unos 4.6 GB de la GPU: cabe en la de 6 GB, pero justo.

## 13. Validación contra resultados esperados

[Retro: «validación frente a resultados esperados»]. Lo que el modelo debe dar por matemáticas, sin datos observados:
- el tamaño final de un brote SEIR;
- que la letalidad y la tasa de hospitalización acumuladas sean las que entran;
- los casos límite.

Se repite con `python -m procesamiento.mediciones esperados`, y lo esencial lo revisa `procesamiento/tests/test_validacion_cientifica.py`. `abm-ref` contra `seir-ref` está en la §10: con un solo grupo por capa dan la misma tasa de ataque.

**Tamaño final.**
- En un SEIR con mezcla homogénea y sin intervenciones, la fracción que se contagia es la z de z = 1 − e^(−R0·z) (Kermack y McKendrick, 1927).
- El periodo latente no la cambia, y los hospitalizados y fallecidos ya salieron de I.
- `seir-ref` la reproduce con una diferencia de 0.001 o menos, **con el R0 efectivo** (§11).
- Con el nominal se queda corto: por ejemplo, 0.642 contra 0.720.

<!-- python -m procesamiento.mediciones esperados · Python 3.14.4, NumPy 2.5.5, WSL 2 (Linux) -->
| R0 nominal | R0 efectivo | z con R0 nominal | z con R0 efectivo | seir-ref | Diferencia con el efectivo |
|---|---|---|---|---|---|
| 0.8 | 0.883 | 0.000 | 0.000 | 0.003 | +0.003 |
| 1.3 | 1.434 | 0.423 | 0.537 | 0.537 | +0.000 |
| 1.6 | 1.765 | 0.642 | 0.719 | 0.720 | +0.001 |
| 2.5 | 2.758 | 0.893 | 0.921 | 0.922 | +0.000 |

Tasa de ataque media de 5 semillas, con 1 000 000 de agentes, 365 días, sin intervenciones y el resto de los parámetros del escenario del contrato (D = 5 días).

**Letalidad y hospitalización acumuladas.**
- Con R0 2.5 y 365 días, casi todos los contagiados terminan su curso.
- Los fallecimientos deben ser Σ casos_g · IFR_g, y las hospitalizaciones, Σ casos_g · IHR_g.
- Resultado: de 0.94 a 1.07 en fallecimientos (unos 380 esperados, cuyo ruido de Poisson es de ±5 %) y de 0.99 a 1.03 en hospitalizaciones, en 5 semillas.
- El modelo entrega la IFR y la IHR que recibe.

**Casos límite.**

| Caso | Esperado | seir-ref (5 semillas) |
|---|---|---|
| Letalidad 0 | 0 fallecimientos | 0 |
| Letalidad y hospitalización 0 | 0 hospitalizaciones | 0 |
| R0 0.8 (bajo el umbral) | Sin brote: el total de una ramificación subcrítica, I0/N / (1 − R0 efectivo) = 0.0034 | 0.0034 |
| R0 menor que 1, más R0 más ataque, población conservada cada día, dosis que no pasan la cobertura | Lo que dice cada prueba | `test_motor.py` (§9) |

**Qué demuestra y qué no.** Esto muestra que el modelo es *matemáticamente consistente*: está verificado. No muestra que reproduzca un brote real, porque eso exige compararlo con datos observados, y no los hay (§11). Por eso sus corridas se presentan como exploratorias (§17 y D39).

## 14. Análisis de sensibilidad

[Retro: «pruebas de sensibilidad de parámetros»; RF-F12].
- Se cambia un parámetro a la vez (un factor a la vez, OAT) a 0.8 y 1.2 veces su valor; los demás quedan como en el caso base.
- Cada celda es la métrica media de 5 semillas dividida entre la del caso base.
- Se repite con `python -m procesamiento.mediciones sensibilidad`.

<!-- python -m procesamiento.mediciones sensibilidad · Python 3.14.4, NumPy 2.5.5, WSL 2 (Linux) -->
| Parámetro | Factor | Tasa de ataque | Pico de casos activos | Día del pico | Hospitalizaciones | Fallecimientos |
|---|---|---|---|---|---|---|
| (base) | 1.0 | 0.7201 | 112 200 | 88.4 | 5 562 | 294.4 |
| r0 | 0.8 | 0.722 | 0.424 | 1.495 | 0.708 | 0.729 |
| r0 | 1.2 | 1.147 | 1.557 | 0.765 | 1.139 | 1.129 |
| incubacion_dias | 0.8 | 0.998 | 1.001 | 0.950 | 1.002 | 0.993 |
| incubacion_dias | 1.2 | 0.999 | 1.006 | 1.050 | 0.998 | 1.016 |
| infeccioso_dias | 0.8 | 1.021 | 1.069 | 0.839 | 1.012 | 1.046 |
| infeccioso_dias | 1.2 | 0.983 | 0.957 | 1.127 | 0.992 | 1.022 |
| tasa_hospitalizacion | 0.8 | 1.000 | 1.003 | 0.991 | 0.796 | 0.982 |
| tasa_hospitalizacion | 1.2 | 0.999 | 1.005 | 0.993 | 1.198 | 0.997 |
| letalidad | 0.8 | 0.999 | 0.999 | 0.998 | 1.004 | 0.824 |
| letalidad | 1.2 | 0.999 | 1.000 | 0.998 | 1.004 | 1.229 |

1 000 000 de agentes, 365 días, sin intervenciones, escenario del contrato (R0 1.6).

**Lo que se esperaba y lo que dio:**
- **R0** es el parámetro que más pesa.
  - Con 0.8 veces (R0 efectivo 1.41), el ataque baja 28 % y el pico de casos activos, 58 %; el pico llega 50 % más tarde.
  - Con 1.2 veces, el ataque sube 15 % y el pico llega 24 % antes.
  - Es lo que da el tamaño final de la §13: la respuesta no es proporcional y es mayor cerca del umbral.
- **Incubación:** no cambia cuántos se contagian (±0.2 %), solo cuándo. El pico se mueve ±5 %, como se espera de un periodo latente.
- **Periodo infeccioso, con R0 fijo:** cambia β y, por el paso de un día, un poco el R0 efectivo. Por eso el ataque se mueve ±2 % y el pico se mueve en el tiempo.
- **Tasa de hospitalización y letalidad:** escalan su propia métrica casi en proporción (0.80 y 1.20 de hospitalizaciones; 0.82 y 1.23 de fallecimientos, con el ruido de unos 300 fallecimientos) y no cambian la transmisión, porque el modelo no deja transmitir a los hospitalizados y la duración en I es la misma.

**Qué usar de esto:** el R0 es el parámetro cuya incertidumbre más cambia los resultados, y es supuesto en todas las enfermedades sin calibración. Por eso los escenarios se comparan con la misma enfermedad y las mismas semillas (D8), y no como cifras absolutas. El escritorio mostrará este análisis (A4).

## 15. Reproducibilidad

[Retro: «reproducibilidad de corridas»; aceptación: «Reproducibilidad» y «Modelo estocástico»].
- Los tres motores son estocásticos. Con la misma entrada, la misma semilla y la misma `engine_version`, la corrida es determinista: da la misma salida bit a bit (§6).
- Cada corrida guarda en `simulation_runs` lo necesario para repetirla: semilla, `engine_version`, `scenario_checksum` (la huella SHA-256 de la entrada) y la versión del escenario, que congela sus parámetros (D5).
- `GET /api/v1/runs/{id}/equivalent` (`corridas`) busca otra corrida con la misma versión, semilla y huella para comparar sus resúmenes.

<!-- python -m procesamiento.mediciones reproducibilidad · Python 3.14.4, NumPy 2.5.5, WSL 2 (Linux) -->
| Motor | engine_version | Semilla | Huella de la salida, 1.ª corrida | 2.ª corrida | Iguales | Otra semilla da otra salida |
|---|---|---|---|---|---|---|
| `seir-ref` | seir-ref-0.1 | 20261112 | `7d7eaf0e8618a104…` | `7d7eaf0e8618a104…` | sí | sí |
| `abm-ref` | abm-ref-0.1 | 20261112 | `9defb805a4d2a0ff…` | `9defb805a4d2a0ff…` | sí | sí |
| `abm-gpu` | — | — | no corre en esta máquina | | | |

- La huella es la SHA-256 de la salida completa: serie, resumen, trazabilidad y avisos.
- La evidencia de la entrega está en [`docs/pruebas/validacion/2026-11-19`](../pruebas/validacion/2026-11-19/LEEME.md).
- `abm-gpu` solo se repite exacto en la misma GPU y con la misma versión de FLAME GPU (§6). Su prueba de contrato (`test_contrato_motor.py`) corre donde hay GPU.
- Entre máquinas, la salida depende también de la versión de NumPy, que cada corrida anota (`numpy_version`).

## 16. Ficha de cada modelo

[Retro: «cada modelo desarrollado deberá contar con una ficha»]. Lo que pide la retroalimentación para cada uno, con referencia a las secciones de arriba.

| | `seir-ref` | `abm-ref` | `abm-gpu` |
|---|---|---|---|
| **Formulación matemática** | SEIR-HDV estocástico de cadena binomial, en pasos de un día, por grupo de edad, con mezcla homogénea (§5 y §8; `procesamiento/motor/modelo.py`) | Modelo basado en agentes: cada persona tiene su hogar, su salón o su trabajo; la fuerza de infección λ_j es de cada susceptible (§5 y §8; `procesamiento/abm/`) | El mismo modelo que `abm-ref` en FLAME GPU 2, un hilo por agente (§8; `procesamiento/abm_gpu/`) |
| **Población representada** | Agentes simulados por grupo de edad (0-19 a 80+), del Censo 2020 o un total; la escala a habitantes es aparte (D6) | Igual, con un agente por persona simulada | Igual que `abm-ref` |
| **Variables** | Conteos S, E, I, R, H, D, V por grupo; β, probabilidades diarias, pesos de capas (§5) | El compartimento de cada agente y sus grupos de contacto (§5) | Las de `abm-ref`, en memoria de la GPU |
| **Supuestos** | Mezcla homogénea; duraciones geométricas; hospitalizados no transmiten; vacuna sin conocer el estado inmunológico; enfermedades por vector como contagio directo (§11; `SIMPLIFICACIONES`) | Los de `seir-ref`, más tamaños de hogar, salón y trabajo y pesos de capas supuestos; hogares armados al azar (§11) | Los de `abm-ref`; otro generador de azar para la epidemia (§11) |
| **Fuentes de parámetros** | Las de cada enfermedad en `diseases.default_params` (migraciones 017, 020 y 025): cada valor con su fuente o marcado como supuesto (regla 8). Población: Censo 2020 (021) | Las mismas, más los supuestos de estructura (`trazabilidad_parametros`) | Las mismas que `abm-ref` |
| **Límites de aplicación** | De 1 000 a 20 000 000 agentes y de 1 a 1 095 días (§6). Comparar escenarios entre sí; no anticipar cifras reales: sin calibración, el R0 es nominal y el efectivo es ~10 % mayor (§11) | Los de `seir-ref`; con más de un millón de agentes es lento (§12) | Necesita una GPU de NVIDIA con CUDA 13 (§6 y §12) |
| **Versión del algoritmo** | `seir-ref-0.1` | `abm-ref-0.1` | La de `procesamiento/abm_gpu/` (`engine_version` de su salida) |
| **Escenarios de prueba** | `test_motor.py`, `test_caracterizacion_motor.py`, `test_contrato_motor.py`, `test_validacion_cientifica.py` (§9) | `test_abm.py`, `test_contrato_motor.py` | `test_abm_gpu.py` (solo con GPU) |
| **Resultados de validación** | Tamaño final, letalidad, hospitalización y casos límite (§13); sensibilidad (§14); reproducibilidad (§15). Calibrado contra la serie de D50 (§19), con cobertura de validación de 71 %, debajo del 80 % de la tolerancia: **verificado, no validado** con datos observados | Con un solo grupo por capa da la tasa de ataque de `seir-ref` (§10); reproducible (§15). Verificado, no validado | Igual que `abm-ref` dentro del ruido entre semillas (§10). Verificado en la GPU de desarrollo, no validado |
| **Categoría de sus corridas (D39)** | Exploratoria | Exploratoria | Exploratoria |

## 17. Exploratoria, predicción y resultado validado (D39)

Ningún modelo está declarado calibrado ni validado contra datos observados en `estado_validacion.json`, así que **todas las corridas son exploratorias**: sirven para comparar escenarios entre sí, no para anticipar cifras reales. La primera calibración de `seir-ref` está en la §19; declararlo calibrado es un PR revisado (D50).
- Para que una corrida sea una *predicción*, el modelo tiene que calibrarse contra una serie observada de esa enfermedad y región (D50, §19).
- Para que sea un *resultado validado*, el modelo tiene que reproducir además datos que no se usaron para calibrar, dentro de la tolerancia que declare esta ficha.
- Las §13 a §15 hacen del modelo un modelo *verificado*, que se muestra junto a la categoría pero no la sube.

## 18. Serie observada (D50, D6)

Es la serie con la que se calibra y valida `seir-ref` (D50, §19), con el servicio `calibracion`
(E7). Entra con la migración 061, como el conjunto `COVID19_NL_2020_SINTOMAS` versión 1, y la sirve
`importacion` (D53).

- **Qué es:** los casos confirmados de COVID-19 de residentes de Nuevo León, por semana
  epidemiológica de inicio de síntomas (de domingo a sábado). Son conteos, sin registros por persona
  (RNF-I05).
- **Fuente:** Secretaría de Salud, Dirección General de Epidemiología, datos abiertos de COVID-19,
  cierre anual 2020 (`COVID19MEXICO2020.zip`). Corte: 2021-10-31 (`FECHA_ACTUALIZACION`).
  SHA-256: `64c90685b68a1164bfa093eeef8c8d33d35d93d9d8b8f3d2d6315359a18dab90`.
- **Filtro:** `ENTIDAD_RES` = 19 y `CLASIFICACION_FINAL` 1, 2 o 3: confirmado por asociación
  clínica epidemiológica, por dictaminación o por laboratorio (catálogo `CLASIFICACION_FINAL_COVID`
  del diccionario del 2024-07-08). El cierre 2021 no trae casos de Nuevo León con inicio en 2020.
- **Licencia:** datos abiertos, Decreto del DOF del 20-02-2015, art. 5, fr. III: «De libre uso:
  Citarán la fuente de origen como único requerimiento para ser utilizados libremente».
- **Ventana:** empieza en la primera semana con casos. El pico de la primera ola es la primera
  semana seguida de tres descensos, y la ventana termina en el valle: la semana con menos casos
  después del pico, entre las semanas completas de 2020.
  - **Resultado:** del **2020-03-01 al 2020-07-26**, 22 semanas y 22 259 casos.
  - **Pico:** la semana del 2020-07-05, con 3 295 casos.
  - **Valle:** la semana del 2020-07-26, con 2 061 casos.
  - Con la separación de D50, las primeras ⅔ de las semanas calibran y el último ⅓, que cae en el
    pico y la primera bajada, valida.
- **Lo que la ventana deja fuera:** después del valle no hay un hueco claro entre olas. La serie se
  queda en una meseta de 2 200 a 2 800 casos por semana hasta septiembre, y sube en octubre y
  noviembre (4 138 en la del 2020-11-01).
- **Repetirla:** baja el zip a un directorio propio y corre
  `python -I datos/scripts/build_serie_observada.py agrega <zip>`. Escribe
  [`covid19_nl_2020_semanal.csv`](../../datos/observados/covid19_nl_2020_semanal.csv) con todas las
  semanas de 2020. `python datos/scripts/build_serie_observada.py` regenera la 061 desde ese CSV.

## 19. Calibración (D50, E7)

`seir-ref` se calibra contra una serie semanal observada con el servicio `calibracion`; la lógica es
`procesamiento/calibracion/`, sin base ni Flask. Solo `seir-ref`: con 15 000 corridas, `abm-ref`
tardaría unas 57 h con un millón de agentes (§12). Evidencia:
[`docs/pruebas/calibracion/2026-11-23`](../pruebas/calibracion/2026-11-23/LEEME.md).

- **Qué se estima:** `r0` (1 a 5), ρ, la fracción de contagios que se reporta (0.01 a 1), y φ, la
  reducción de contactos de la Jornada Nacional de Sana Distancia (0 a 1). Los tres rangos son
  supuestos del análisis (regla 8).
- **Qué queda fijo:** los parámetros de la enfermedad del catálogo, con sus supuestos; la población
  de la región por edad (la gente sin edad se prorratea, supuesto del método); las capas de contacto
  del motor; `CIERRE_ESCUELAS` desde el 23-03-2020 con reducción 1, y `CIERRE_TRABAJO` (30-03) y
  `REDUCCION_AFORO` (23-03) con reducción φ, las tres sin fin; e
  `infectados_iniciales = max(1, round(c₀/ρ))`, con c₀ los casos de la primera semana.
- **Modelo de observación:** el caso simulado de la semana *w* es ρ por los contagios (S → E) de esa
  semana desplazados 5 días, la mediana de incubación de Lauer et al. 2020. Los infectados
  iniciales ya son infecciosos el día 0, así que cuentan como inicio de síntomas ese día. ρ y el
  desfase viven en `procesamiento/calibracion/`, nunca en el motor.
- **Método:** ABC por rechazo (Toni et al. 2009) sobre un hipercubo latino (McKay et al. 1979): 5 000
  combinaciones, cada una con las semillas 1 a 3. La distancia es la pérdida media
  L = Σ_w (log(1 + o_w) − log(1 + s_w))² en la ventana de calibración, y se aceptan las 50 de menor
  distancia (1 %). Cada parámetro se reporta con la mediana y el p5–p95 de las aceptadas, y la banda
  semanal sale de sus 150 trayectorias.
- **Ventanas:** las primeras ⅔ de las semanas (`round(2W/3)`) calibran y el resto valida, sin entrar
  nunca a la pérdida. Con la serie de D50, 15 y 7 semanas.
- **Métricas:** RMSE y R² en conteos, con la mediana de la banda, y la cobertura: la fracción de
  semanas observadas dentro del p5–p95. Se calculan por separado en cada ventana.
- **Tolerancia para `validada`** (D50, fijada antes de correr la validación): cobertura de al menos
  **80 %** en las semanas de validación. La banda es un intervalo del 90 %; el margen es supuesto del
  equipo.
- **Reproducibilidad:** cada calibración guarda método y versión (`abc-rechazo`, `calibracion-0.1`),
  `engine_version`, el conjunto con su versión, los rangos, la semilla del muestreo, las semillas, el
  cuantil y las ventanas. Con eso sale idéntica bit a bit con la misma versión de NumPy. Solo vale
  para su `engine_version`: si se corrige el R0 efectivo (§11), se calibra otra vez.
- **Prueba sintética:** `procesamiento/tests/test_calibracion.py` genera una serie con parámetros
  conocidos y ruido de Poisson y revisa que el algoritmo los recupere dentro de su p5–p95. Una serie
  así no es observada, así que no sube ninguna categoría.

**Resultado con la serie de D50** (2026-11-23):

| Parámetro | Mediana | p5–p95 |
|---|---|---|
| r0 | 2.59 | 2.29–3.05 |
| ρ | 0.30 | 0.02–0.66 |
| φ | 0.37 | 0.12–0.63 |

| Ventana | Semanas | RMSE | R² | Cobertura |
|---|---|---|---|---|
| Calibración | 15 | 136 | 0.89 | 60 % |
| Validación | 7 | 3 041 | −25.9 | 71 % |

- El r0 calibrado cae dentro del IC de Billah et al. 2020 (2.39–3.44). r0 y φ se confunden
  (correlación de 0.96 entre las aceptadas), y ρ casi no se identifica.
- **No pasa la tolerancia:** el modelo sigue creciendo después del pico observado de julio, porque φ
  es constante y la Jornada no termina. `seir-ref` puede declararse *calibrado* para COVID-19 en
  Nuevo León (corridas `prediccion` con esa configuración), pero no *validado*. Declararlo es un PR
  revisado sobre `estado_validacion.json` (D39, D50); por ahora sigue sin calibrar.
