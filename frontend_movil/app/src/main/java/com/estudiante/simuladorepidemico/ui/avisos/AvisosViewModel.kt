package com.estudiante.simuladorepidemico.ui.avisos

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.estudiante.simuladorepidemico.avisos.Avisos
import com.estudiante.simuladorepidemico.red.Aviso
import com.estudiante.simuladorepidemico.red.mensajeDeError
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import java.io.IOException

data class EstadoAvisos(
    val cargando: Boolean = true,
    val avisos: List<Aviso> = emptyList(),
    // De todos los de la cuenta, aunque la lista muestre solo los últimos 50.
    val noLeidos: Int = 0,
    val error: String? = null,
    val marcandoTodos: Boolean = false,
)

private const val SIN_RED = "Sin conexión: los avisos se consultan con red."

class AvisosViewModel(private val avisos: Avisos) : ViewModel() {
    var estado by mutableStateOf(EstadoAvisos())
        private set

    init {
        cargar()
    }

    fun cargar() {
        estado = estado.copy(cargando = true, error = null)
        viewModelScope.launch {
            estado = try {
                val lista = avisos.lista()
                estado.copy(cargando = false, avisos = lista.avisos, noLeidos = lista.noLeidas)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                estado.copy(cargando = false, error = mensaje(e))
            }
        }
    }

    // Tocar uno sin leer lo marca como leído.
    fun abrir(aviso: Aviso) {
        if (aviso.leido) return
        viewModelScope.launch {
            try {
                reemplazar(avisos.marcarLeido(aviso.id))
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                estado = estado.copy(error = mensaje(e))
            }
        }
    }

    // Uno por uno: notificaciones no tiene una ruta para todos. Si uno falla, se queda ahí.
    fun marcarTodos() {
        if (estado.marcandoTodos) return
        val pendientes = estado.avisos.filterNot { it.leido }
        estado = estado.copy(marcandoTodos = true, error = null)
        viewModelScope.launch {
            try {
                pendientes.forEach { reemplazar(avisos.marcarLeido(it.id)) }
                estado = estado.copy(marcandoTodos = false)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                estado = estado.copy(marcandoTodos = false, error = mensaje(e))
            }
        }
    }

    private fun reemplazar(nuevo: Aviso) {
        val antes = estado.avisos.firstOrNull { it.id == nuevo.id }
        val menos = if (antes != null && !antes.leido && nuevo.leido) 1 else 0
        estado = estado.copy(
            avisos = estado.avisos.map { if (it.id == nuevo.id) nuevo else it },
            noLeidos = maxOf(0, estado.noLeidos - menos),
        )
    }

    private fun mensaje(e: Exception) = if (e is IOException) SIN_RED else mensajeDeError(e)
}
