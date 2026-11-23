package com.estudiante.simuladorepidemico.ui.inicio

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.estudiante.simuladorepidemico.avisos.Avisos
import com.estudiante.simuladorepidemico.local.CatalogoDao
import com.estudiante.simuladorepidemico.local.Catalogos
import com.estudiante.simuladorepidemico.red.Apis
import com.estudiante.simuladorepidemico.local.CasosDao
import com.estudiante.simuladorepidemico.sesion.Sesion
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

// Al llegar al inicio (al abrir la app con sesión, o al entrar) se manda lo pendiente de la cuenta,
// se ponen al día los catálogos, se programa la consulta de avisos y se cuentan los no leídos. Sin
// red, todo espera sin molestar.
@OptIn(ExperimentalCoroutinesApi::class)
class InicioViewModel(
    private val sesion: Sesion,
    casos: CasosDao,
    catalogos: Catalogos,
    private val avisos: Avisos,
    private val apis: Apis,
    catalogo: CatalogoDao,
    programarEnvio: () -> Unit,
    programarAvisos: () -> Unit,
) : ViewModel() {
    val porEnviar: StateFlow<Int> = flow { emit(sesion.cuenta()) }
        .flatMapLatest { cuenta -> if (cuenta == null) flowOf(0) else casos.porEnviar(cuenta) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0)

    // null mientras no se sabe (sin red, por ejemplo).
    private val avisosNoLeidos = MutableStateFlow<Int?>(null)
    val noLeidos: StateFlow<Int?> = avisosNoLeidos.asStateFlow()

    // Los casos de la cuenta a los que el servidor les marca datos faltantes (D49). null sin red.
    private val casosIncompletos = MutableStateFlow<Int?>(null)
    val incompletos: StateFlow<Int?> = casosIncompletos.asStateFlow()

    // Las enfermedades con formulario propio ya guardado para capturar sin red (D48).
    val formularios: StateFlow<Int> = catalogo.formularios().map { it.size }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0)

    // D56: lo que ofrece el inicio según el perfil. RF-I19: la captura es solo del CAPTURISTA;
    // mientras no se saben los roles se queda su menú (menuDe(null)): el servidor es quien niega a
    // los demás, y un CAPTURISTA sin red no se queda sin capturar.
    private val menuActual = MutableStateFlow(menuDe(null))
    val menu: StateFlow<Menu> = menuActual.asStateFlow()
    val capturista: StateFlow<Boolean> = menuActual.map { it.captura }
        .stateIn(viewModelScope, SharingStarted.Eagerly, true)

    // Para quien revisa (EPIDEMIOLOGO, AUTORIDAD_SANITARIA, ADMINISTRADOR): los casos por validar de
    // su alcance y las campañas activas. null sin red.
    private val casosPorValidar = MutableStateFlow<Int?>(null)
    val porValidar: StateFlow<Int?> = casosPorValidar.asStateFlow()
    private val campanasEnCurso = MutableStateFlow<Int?>(null)
    val campanasActivas: StateFlow<Int?> = campanasEnCurso.asStateFlow()

    init {
        programarEnvio()
        programarAvisos()
        viewModelScope.launch {
            try {
                menuActual.value = menuDe(sesion.roles())
                contarPanel()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // Una sesión sin roles guardados y sin red: se queda como estaba.
            }
        }
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

    // Al volver al inicio, por ejemplo desde los avisos.
    fun contarAvisos() {
        viewModelScope.launch {
            try {
                avisosNoLeidos.value = avisos.noLeidos()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // Se queda lo que se sabía.
            }
        }
        contarPanel()
    }

    // Lo que el panel de cada perfil cuenta en el servidor. Sin red, se queda lo que se sabía.
    private fun contarPanel() {
        val menu = menuActual.value
        fun cuenta(destino: MutableStateFlow<Int?>, consulta: suspend () -> Int) = viewModelScope.launch {
            try {
                destino.value = consulta()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // Se queda lo que se sabía.
            }
        }
        if (menu.captura) cuenta(casosIncompletos) { apis.casos().incompletos().total }
        if (menu.revisa) cuenta(casosPorValidar) { apis.casos().lista(estado = "pendiente", tamano = 1).total }
        if (menu.revisa) cuenta(campanasEnCurso) { apis.vacunas().campanas(estado = "activa").total }
    }
}
