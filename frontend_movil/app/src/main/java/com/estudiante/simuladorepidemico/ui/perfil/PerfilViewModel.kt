package com.estudiante.simuladorepidemico.ui.perfil

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.estudiante.simuladorepidemico.red.Perfil
import com.estudiante.simuladorepidemico.red.mensajeDeError
import com.estudiante.simuladorepidemico.sesion.Sesion
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

data class EstadoPerfil(
    val cargando: Boolean = true,
    val perfil: Perfil? = null,
    val vence: Long? = null,
    val error: String? = null,
    val cerrando: Boolean = false,
    val dispositivo: Long? = null,
    val registrando: Boolean = false,
    val errorTelefono: String? = null,
)

// Si la sesión ya no sirve (revocada o vencida, o el teléfono revocado al reintentar su
// registro), se borra y la navegación regresa sola al login.
class PerfilViewModel(private val sesion: Sesion) : ViewModel() {
    var estado by mutableStateOf(EstadoPerfil())
        private set

    init {
        cargar()
    }

    fun cargar() {
        estado = estado.copy(cargando = true, error = null)
        viewModelScope.launch {
            try {
                val perfil = sesion.perfil()
                val vence = sesion.vence()
                val dispositivo = sesion.dispositivo()
                estado = estado.copy(cargando = false, perfil = perfil, vence = vence, dispositivo = dispositivo)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                estado = estado.copy(cargando = false, error = mensajeDeError(e))
            }
        }
    }

    fun registrarTelefono() {
        if (estado.registrando) return
        estado = estado.copy(registrando = true, errorTelefono = null)
        viewModelScope.launch {
            try {
                val id = sesion.registrarTelefono()
                estado = estado.copy(registrando = false, dispositivo = id)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                estado = estado.copy(registrando = false, errorTelefono = mensajeDeError(e))
            }
        }
    }

    fun cerrarSesion() {
        if (estado.cerrando) return
        estado = estado.copy(cerrando = true)
        viewModelScope.launch { sesion.cerrar() }
    }
}
