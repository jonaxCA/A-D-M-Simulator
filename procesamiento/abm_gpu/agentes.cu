// Funciones de agente de abm-gpu (FLAME GPU 2). Las compila NVRTC al armar el modelo.
//
// modelo.py antepone tres #define:
//   AGENTES   número de agentes; da el tamaño de las propiedades macro por agente y por grupo
//             de contacto (nunca hay más grupos que agentes)
//   GRUPOS    grupos de edad
//   GRUPOS_M  tamaño de las propiedades macro por grupo de edad: GRUPOS, y al menos 2, porque
//             FLAME GPU trata una de un elemento como valor simple y no deja indexarla
//   CAMPANAS  campañas de vacunación del escenario (0 si no hay)
//
// Cada función empieza en una línea "//@funcion <nombre>"; lo de antes es común a todas.
// Las fórmulas son las de procesamiento/abm/modelo.py (abm-ref). Si cambia algo que altere los
// números, sube ENGINE_VERSION en modelo.py.

#define ESTADO_S 0
#define ESTADO_E 1
#define ESTADO_I 2
#define ESTADO_R 3
#define ESTADO_H 4
#define ESTADO_D 5
#define ESTADO_V 6

// Columnas de la propiedad macro "poblacion", que llega de NumPy (modelo.py, _POBLACION).
#define COL_GRUPO 0
#define COL_HOGAR 1
#define COL_SALON 2
#define COL_TRABAJO 3
#define COL_INFECTADO 4

// Lo que le toca a un susceptible de un grupo de contacto: infecciosos entre los demás vivos.
#define FRACCION(INF, VIV) ((float)(INF) / (float)((VIV) > 1u ? (VIV) - 1u : 1u))

//@funcion cuenta
// Cuenta infecciosos y vivos de cada hogar, salón y centro de trabajo al empezar el día.
// El día 1, antes, cada agente toma sus datos de la población que armó NumPy.
FLAMEGPU_AGENT_FUNCTION(cuenta, flamegpu::MessageNone, flamegpu::MessageNone) {
    if (FLAMEGPU->environment.getProperty<unsigned int>("dia") == 1u) {
        const unsigned int i = FLAMEGPU->getIndex();
        auto pob = FLAMEGPU->environment.getMacroProperty<int, AGENTES, 5>("poblacion");
        FLAMEGPU->setVariable<int>("grupo", pob[i][COL_GRUPO]);
        FLAMEGPU->setVariable<int>("hogar", pob[i][COL_HOGAR]);
        FLAMEGPU->setVariable<int>("salon", pob[i][COL_SALON]);
        FLAMEGPU->setVariable<int>("trabajo", pob[i][COL_TRABAJO]);
        FLAMEGPU->setVariable<int>("estado", (int)pob[i][COL_INFECTADO] ? ESTADO_I : ESTADO_S);
        FLAMEGPU->setVariable<float>("escala",
            FLAMEGPU->environment.getMacroProperty<float, AGENTES>("escala_de")[i]);
        FLAMEGPU->setVariable<int>("vacunado", 0);
    }
    const int estado = FLAMEGPU->getVariable<int>("estado");
    if (estado == ESTADO_D) {
        return flamegpu::ALIVE;
    }
    const bool infeccioso = estado == ESTADO_I;
    const int hogar = FLAMEGPU->getVariable<int>("hogar");
    const int salon = FLAMEGPU->getVariable<int>("salon");
    const int trabajo = FLAMEGPU->getVariable<int>("trabajo");
    if (hogar >= 0) {
        FLAMEGPU->environment.getMacroProperty<unsigned int, AGENTES>("viv_hogar")[hogar] += 1u;
        if (infeccioso)
            FLAMEGPU->environment.getMacroProperty<unsigned int, AGENTES>("inf_hogar")[hogar] += 1u;
    }
    if (salon >= 0) {
        FLAMEGPU->environment.getMacroProperty<unsigned int, AGENTES>("viv_salon")[salon] += 1u;
        if (infeccioso)
            FLAMEGPU->environment.getMacroProperty<unsigned int, AGENTES>("inf_salon")[salon] += 1u;
    }
    if (trabajo >= 0) {
        FLAMEGPU->environment.getMacroProperty<unsigned int, AGENTES>("viv_trabajo")[trabajo] += 1u;
        if (infeccioso)
            FLAMEGPU->environment.getMacroProperty<unsigned int, AGENTES>("inf_trabajo")[trabajo] += 1u;
    }
    return flamegpu::ALIVE;
}

//@funcion avanza
// Las transiciones del día, sobre el estado con que empezó. Los días de vacunación, además,
// cuenta a quién se puede vacunar y le da a cada agente la clave con que se ordenan.
FLAMEGPU_AGENT_FUNCTION(avanza, flamegpu::MessageNone, flamegpu::MessageNone) {
    const int estado = FLAMEGPU->getVariable<int>("estado");
    const int g = FLAMEGPU->getVariable<int>("grupo");
    int nuevo = estado;

    if (estado == ESTADO_S) {
        // lambda_j = escala_j * (lam_mezcla + sum_capa w_capa * x_capa_j); w ya trae beta,
        // aislamiento, peso y lo que dejan las intervenciones de esa capa.
        float lam = FLAMEGPU->environment.getProperty<float>("lam_mezcla");
        const float w_hogar = FLAMEGPU->environment.getProperty<float>("w_hogar");
        const float w_escuela = FLAMEGPU->environment.getProperty<float>("w_escuela");
        const float w_trabajo = FLAMEGPU->environment.getProperty<float>("w_trabajo");
        const int hogar = FLAMEGPU->getVariable<int>("hogar");
        const int salon = FLAMEGPU->getVariable<int>("salon");
        const int trabajo = FLAMEGPU->getVariable<int>("trabajo");
        if (w_hogar > 0.0f && hogar >= 0) {
            const unsigned int inf = FLAMEGPU->environment.getMacroProperty<unsigned int, AGENTES>("inf_hogar")[hogar];
            const unsigned int viv = FLAMEGPU->environment.getMacroProperty<unsigned int, AGENTES>("viv_hogar")[hogar];
            lam += w_hogar * FRACCION(inf, viv);
        }
        if (w_escuela > 0.0f && salon >= 0) {
            const unsigned int inf = FLAMEGPU->environment.getMacroProperty<unsigned int, AGENTES>("inf_salon")[salon];
            const unsigned int viv = FLAMEGPU->environment.getMacroProperty<unsigned int, AGENTES>("viv_salon")[salon];
            lam += w_escuela * FRACCION(inf, viv);
        }
        if (w_trabajo > 0.0f && trabajo >= 0) {
            const unsigned int inf = FLAMEGPU->environment.getMacroProperty<unsigned int, AGENTES>("inf_trabajo")[trabajo];
            const unsigned int viv = FLAMEGPU->environment.getMacroProperty<unsigned int, AGENTES>("viv_trabajo")[trabajo];
            lam += w_trabajo * FRACCION(inf, viv);
        }
        lam *= FLAMEGPU->getVariable<float>("escala");
        if (lam > 0.0f && FLAMEGPU->random.uniform<float>() < -expm1f(-lam)) {
            nuevo = ESTADO_E;
            FLAMEGPU->environment.getMacroProperty<unsigned int, 3>("eventos")[0] += 1u;
            FLAMEGPU->environment.getMacroProperty<unsigned int, GRUPOS_M>("casos_grupo")[g] += 1u;
        }
    } else if (estado == ESTADO_E) {
        if (FLAMEGPU->random.uniform<float>() < FLAMEGPU->environment.getProperty<float>("p_ei"))
            nuevo = ESTADO_I;
    } else if (estado == ESTADO_I) {
        if (FLAMEGPU->random.uniform<float>() < FLAMEGPU->environment.getProperty<float>("p_sale_i")) {
            const float sorteo = FLAMEGPU->random.uniform<float>();
            if (sorteo < FLAMEGPU->environment.getProperty<float>("hasta_h", g)) {
                nuevo = ESTADO_H;
                FLAMEGPU->environment.getMacroProperty<unsigned int, 3>("eventos")[1] += 1u;
            } else if (sorteo < FLAMEGPU->environment.getProperty<float>("hasta_d", g)) {
                nuevo = ESTADO_D;
            } else {
                nuevo = ESTADO_R;
            }
        }
    } else if (estado == ESTADO_H) {
        if (FLAMEGPU->random.uniform<float>() < FLAMEGPU->environment.getProperty<float>("p_sale_h")) {
            nuevo = FLAMEGPU->random.uniform<float>() < FLAMEGPU->environment.getProperty<float>("muerte_en_h", g)
                ? ESTADO_D : ESTADO_R;
        }
    }
    if (nuevo == ESTADO_D) {
        FLAMEGPU->environment.getMacroProperty<unsigned int, 3>("eventos")[2] += 1u;
        FLAMEGPU->environment.getMacroProperty<unsigned int, GRUPOS_M>("muertes_grupo")[g] += 1u;
    }
    if (nuevo != estado)
        FLAMEGPU->setVariable<int>("estado", nuevo);

#if CAMPANAS > 0
    if (FLAMEGPU->environment.getProperty<unsigned int>("vacuna_hoy")) {
        // Se puede vacunar a quien sigue vivo, no está hospitalizado y no tiene dosis. La clave
        // ordena por grupo de edad, primero los que se pueden vacunar y, entre ellos, al azar.
        const bool disponible = nuevo != ESTADO_D && nuevo != ESTADO_H
            && !FLAMEGPU->getVariable<int>("vacunado");
        uint64_t clave = (uint64_t)(2 * g + (disponible ? 0 : 1)) << 32;
        if (disponible) {
            FLAMEGPU->environment.getMacroProperty<unsigned int, GRUPOS_M>("disp_grupo")[g] += 1u;
            clave |= (uint64_t)(FLAMEGPU->random.uniform<double>() * 4294967295.0);
        }
        FLAMEGPU->setVariable<uint64_t>("clave", clave);
    }
#endif
    return flamegpu::ALIVE;
}

//@funcion vacuna
// Ya ordenados por clave, los disponibles de cada grupo de edad ocupan un bloque que empieza en
// inicio_grupo. La campaña c vacuna los lugares [corte_lo, corte_hi) de ese bloque.
FLAMEGPU_AGENT_FUNCTION(vacuna, flamegpu::MessageNone, flamegpu::MessageNone) {
#if CAMPANAS > 0
    if (!FLAMEGPU->environment.getProperty<unsigned int>("aplica_vacuna"))
        return flamegpu::ALIVE;
    const int g = FLAMEGPU->getVariable<int>("grupo");
    const int lugar = (int)FLAMEGPU->getIndex() - FLAMEGPU->environment.getProperty<int>("inicio_grupo", g);
    for (int c = 0; c < CAMPANAS; ++c) {
        const int lo = FLAMEGPU->environment.getProperty<int>("corte_lo", c * GRUPOS + g);
        const int hi = FLAMEGPU->environment.getProperty<int>("corte_hi", c * GRUPOS + g);
        if (lugar >= lo && lugar < hi) {
            FLAMEGPU->setVariable<int>("vacunado", 1);
            if (FLAMEGPU->getVariable<int>("estado") == ESTADO_S
                    && FLAMEGPU->random.uniform<float>() < FLAMEGPU->environment.getProperty<float>("eficacia", c)) {
                FLAMEGPU->setVariable<int>("estado", ESTADO_V);
                FLAMEGPU->environment.getMacroProperty<unsigned int, GRUPOS_M>("protegidos_grupo")[g] += 1u;
            }
            break;
        }
    }
#endif
    return flamegpu::ALIVE;
}
