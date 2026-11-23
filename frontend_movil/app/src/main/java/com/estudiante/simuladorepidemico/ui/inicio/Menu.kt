package com.estudiante.simuladorepidemico.ui.inicio

// Lo que ofrece el inicio (D54).
enum class Opcion { CAPTURAR, MIS_CASOS, CASOS_SERVIDOR, CAMPANAS, LOTES, CONSULTA, AVISOS, PERFIL }

// `lotesRegistra`: registra lotes y aplica dosis (los que vacunas deja escribir); si no, los consulta.
data class Menu(val opciones: Set<Opcion>, val lotesRegistra: Boolean) {
    val captura: Boolean get() = Opcion.CAPTURAR in opciones
    val revisa: Boolean get() = Opcion.CASOS_SERVIDOR in opciones
}

// D54, con los perfiles de D42. Los de campo: el CAPTURISTA captura; el EPIDEMIOLOGO (personal de
// vigilancia y responsable de campaña) y la AUTORIDAD_SANITARIA (supervisor regional, con el alcance
// de su región, D43) consultan. Validar y descartar se queda en la web. ANALISTA e INVESTIGADOR no
// son de campo: consulta por zona y avisos. Quien niega es el servidor; esto solo ordena el inicio.
private val POR_PERFIL: Map<String, Set<Opcion>> = mapOf(
    "CAPTURISTA" to setOf(
        Opcion.CAPTURAR, Opcion.MIS_CASOS, Opcion.CAMPANAS, Opcion.LOTES, Opcion.CONSULTA, Opcion.AVISOS, Opcion.PERFIL,
    ),
    "EPIDEMIOLOGO" to setOf(
        Opcion.CASOS_SERVIDOR, Opcion.CAMPANAS, Opcion.LOTES, Opcion.CONSULTA, Opcion.AVISOS, Opcion.PERFIL,
    ),
    "AUTORIDAD_SANITARIA" to setOf(
        Opcion.CASOS_SERVIDOR, Opcion.CAMPANAS, Opcion.LOTES, Opcion.CONSULTA, Opcion.AVISOS, Opcion.PERFIL,
    ),
    "ADMINISTRADOR" to setOf(
        Opcion.CASOS_SERVIDOR, Opcion.CAMPANAS, Opcion.LOTES, Opcion.CONSULTA, Opcion.AVISOS, Opcion.PERFIL,
    ),
    "ANALISTA" to setOf(Opcion.CONSULTA, Opcion.AVISOS, Opcion.PERFIL),
    "INVESTIGADOR" to setOf(Opcion.CONSULTA, Opcion.AVISOS, Opcion.PERFIL),
)

// Los que vacunas deja registrar lotes y aplicar dosis (ROLES_ESCRIBEN).
private val REGISTRAN_LOTES = setOf("CAPTURISTA", "ADMINISTRADOR")

private val SIEMPRE = setOf(Opcion.AVISOS, Opcion.PERFIL)

// Sin roles conocidos (una sesión de antes de guardarlos, sin red) queda el del CAPTURISTA, como
// antes (RF-I19): el servidor niega a quien no debe y un CAPTURISTA sin red no se queda sin capturar.
fun menuDe(roles: Set<String>?): Menu {
    val conocidos = roles ?: setOf("CAPTURISTA")
    return Menu(
        opciones = conocidos.flatMap { POR_PERFIL[it].orEmpty() }.toSet() + SIEMPRE,
        lotesRegistra = conocidos.any { it in REGISTRAN_LOTES },
    )
}
