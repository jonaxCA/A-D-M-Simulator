package com.estudiante.simuladorepidemico.ui.casos

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.estudiante.simuladorepidemico.local.CasoLocal
import com.estudiante.simuladorepidemico.local.CasosDao
import com.estudiante.simuladorepidemico.local.CatalogoDao
import com.estudiante.simuladorepidemico.local.ConteoFotos
import com.estudiante.simuladorepidemico.local.Fotos
import com.estudiante.simuladorepidemico.sesion.Sesion
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class FilaCaso(
    val caso: CasoLocal,
    val enfermedad: String,
    val municipio: String,
    val fotos: ConteoFotos? = null,
)

// Solo los casos de la cuenta de la sesión: en un teléfono compartido, cada quien ve los suyos.
@OptIn(ExperimentalCoroutinesApi::class)
class MisCasosViewModel(
    sesion: Sesion,
    private val casos: CasosDao,
    catalogo: CatalogoDao,
    private val fotos: Fotos,
    private val programarEnvio: () -> Unit,
) : ViewModel() {
    // null mientras carga.
    val filas: StateFlow<List<FilaCaso>?> = flow { emit(sesion.cuenta()) }
        .flatMapLatest { cuenta ->
            if (cuenta == null) return@flatMapLatest flowOf(emptyList())
            combine(
                casos.deLaCuenta(cuenta), casos.conteoDeFotos(cuenta), catalogo.enfermedades(), catalogo.municipios(),
            ) { lista, conteos, enfermedades, municipios ->
                val nombresE = enfermedades.associate { it.id to it.nombre }
                val nombresM = municipios.associate { it.id to it.nombre }
                val porCaso = conteos.associateBy { it.caso }
                lista.map {
                    FilaCaso(
                        it,
                        nombresE[it.enfermedad] ?: "Enfermedad ${it.enfermedad}",
                        nombresM[it.municipio] ?: "Municipio ${it.municipio}",
                        porCaso[it.localUuid],
                    )
                }
            }
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    fun enviarAhora() = programarEnvio()

    // Solo un rechazado: lo pendiente se envía y lo enviado ya está en el servidor. Sus fotos se van
    // con él, también del almacenamiento.
    fun descartar(caso: CasoLocal) {
        viewModelScope.launch { fotos.borrar(casos.descartarConFotos(caso.localUuid)) }
    }
}
