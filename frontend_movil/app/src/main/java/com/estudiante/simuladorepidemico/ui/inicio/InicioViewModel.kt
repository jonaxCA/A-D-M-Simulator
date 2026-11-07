package com.estudiante.simuladorepidemico.ui.inicio

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.estudiante.simuladorepidemico.local.Catalogos
import com.estudiante.simuladorepidemico.local.CasosDao
import com.estudiante.simuladorepidemico.sesion.Sesion
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

// Al llegar al inicio (al abrir la app con sesión, o al entrar) se manda lo pendiente de la cuenta y
// se ponen al día los catálogos. Sin red, las dos cosas esperan sin molestar.
@OptIn(ExperimentalCoroutinesApi::class)
class InicioViewModel(
    sesion: Sesion,
    casos: CasosDao,
    catalogos: Catalogos,
    programarEnvio: () -> Unit,
) : ViewModel() {
    val porEnviar: StateFlow<Int> = flow { emit(sesion.cuenta()) }
        .flatMapLatest { cuenta -> if (cuenta == null) flowOf(0) else casos.porEnviar(cuenta) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0)

    init {
        programarEnvio()
        viewModelScope.launch {
            try {
                catalogos.actualizar()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // Se queda el catálogo que ya había; la captura ofrece descargarlo si no hay ninguno.
            }
        }
    }
}
