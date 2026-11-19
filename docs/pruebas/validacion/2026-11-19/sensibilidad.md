<!-- Python 3.14.4, NumPy 2.5.5, Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43 -->
Media de 5 semillas, 1,000,000 agentes, 365 días, sin intervenciones. Cada celda es la métrica con el parámetro cambiado dividida entre la del caso base.

| Parámetro | Factor | tasa_ataque | pico_casos_activos | dia_pico | hospitalizaciones | fallecimientos |
|---|---|---|---|---|---|---|
| (base) | 1.0 | 0.7201 | 1.122e+05 | 88.4 | 5562 | 294.4 |
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
