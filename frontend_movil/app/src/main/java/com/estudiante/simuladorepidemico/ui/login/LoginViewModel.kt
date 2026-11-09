package com.estudiante.simuladorepidemico.ui.login

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.estudiante.simuladorepidemico.red.Captcha
import com.estudiante.simuladorepidemico.red.mensajeDeError
import com.estudiante.simuladorepidemico.sesion.Sesion
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

data class EstadoLogin(
    val usuario: String = "",
    val password: String = "",
    val respuesta: String = "",
    val pregunta: String? = null,
    val cargandoCaptcha: Boolean = false,
    val entrando: Boolean = false,
    val error: String? = null,
    val dentro: Boolean = false,
) {
    val listo: Boolean
        get() = usuario.isNotBlank() && password.isNotEmpty() && respuesta.isNotEmpty() &&
            pregunta != null && !cargandoCaptcha && !entrando && !dentro
}

// `dentro` avisa a la pantalla que ya puede pasar al inicio: cuando el login y el registro del
// teléfono terminaron. Si la navegación siguiera a Sesion.activa, cambiaría de pantalla en
// cuanto se guardan los tokens y cancelaría el registro a la mitad.
// El estado es mutableStateOf y no un StateFlow: un TextField necesita que su valor cambie en
// el momento; con un StateFlow llega un cuadro tarde y al escribir rápido se pierden letras.
class LoginViewModel(private val sesion: Sesion) : ViewModel() {
    var estado by mutableStateOf(EstadoLogin())
        private set
    private var captcha: Captcha? = null

    init {
        otroCaptcha()
    }

    fun cambiarUsuario(valor: String) {
        estado = estado.copy(usuario = valor, error = null)
    }

    fun cambiarPassword(valor: String) {
        estado = estado.copy(password = valor, error = null)
    }

    // Las preguntas son sumas de un dígito: la respuesta es un número corto.
    fun cambiarRespuesta(valor: String) {
        estado = estado.copy(respuesta = valor.filter(Char::isDigit).take(3), error = null)
    }

    // Cada captcha sirve para un solo intento (auth lo borra al leerlo).
    fun otroCaptcha(error: String? = null) {
        captcha = null
        estado = estado.copy(pregunta = null, respuesta = "", cargandoCaptcha = true, error = error)
        viewModelScope.launch {
            try {
                val nuevo = sesion.captcha()
                captcha = nuevo
                estado = estado.copy(pregunta = nuevo.pregunta, cargandoCaptcha = false)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                estado = estado.copy(cargandoCaptcha = false, error = error ?: mensajeDeError(e))
            }
        }
    }

    fun entrar() {
        val usado = captcha ?: return
        val datos = estado
        if (!datos.listo) return
        estado = estado.copy(entrando = true, error = null)
        viewModelScope.launch {
            try {
                sesion.iniciar(datos.usuario.trim(), datos.password, usado, datos.respuesta)
                estado = estado.copy(password = "", respuesta = "", entrando = false, dentro = true)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                estado = estado.copy(entrando = false)
                otroCaptcha(mensajeDeError(e))
            }
        }
    }
}
