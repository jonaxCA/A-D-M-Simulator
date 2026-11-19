<!-- Python 3.14.4, NumPy 2.5.5, Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43 -->
**Tamaño final.** Tasa de ataque media de 5 semillas, 1,000,000 agentes, 365 días, sin intervenciones, contra z = 1 − e^(−R0·z) con el R0 nominal y con el efectivo.

| R0 nominal | R0 efectivo | z con R0 nominal | z con R0 efectivo | seir-ref | Diferencia con el efectivo |
|---|---|---|---|---|---|
| 0.8 | 0.883 | 0.000 | 0.000 | 0.003 | +0.003 |
| 1.3 | 1.434 | 0.423 | 0.537 | 0.537 | +0.000 |
| 1.6 | 1.765 | 0.642 | 0.719 | 0.720 | +0.001 |
| 2.5 | 2.758 | 0.893 | 0.921 | 0.922 | +0.000 |

**Letalidad y hospitalización acumuladas.** Con R0 2.5 y 365 días casi todos los contagiados terminan su curso: fallecimientos / Σ casos·IFR y hospitalizaciones / Σ casos·IHR deben ser cercanos a 1.

| Semilla | Fallecimientos | Esperados | Razón | Hospitalizaciones | Esperadas | Razón |
|---|---|---|---|---|---|---|
| 1 | 363 | 379.5 | 0.957 | 7335 | 7118.4 | 1.030 |
| 2 | 405 | 380.2 | 1.065 | 7129 | 7125.3 | 1.001 |
| 3 | 393 | 379.7 | 1.035 | 7124 | 7124.4 | 1.000 |
| 4 | 357 | 378.8 | 0.943 | 7193 | 7109.3 | 1.012 |
| 5 | 372 | 379.4 | 0.980 | 7017 | 7114.9 | 0.986 |

**Casos límite.**

| Caso | Esperado | seir-ref (5 semillas) |
|---|---|---|
| Letalidad 0 | 0 fallecimientos | 0 |
| Letalidad y hospitalización 0 | 0 hospitalizaciones | 0 |
| R0 0.8 (subumbral) | Sin brote: tasa de ataque I0/N / (1 − R0 efectivo) = 0.0034 | 0.0034 |
