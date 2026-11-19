package com.estudiante.simuladorepidemico.ui.login

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class FormularioLoginTest {
    @get:Rule
    val regla = createComposeRule()

    private var estado by mutableStateOf(EstadoLogin())
    private var entradas = 0
    private var captchasPedidos = 0

    private fun mostrar(inicial: EstadoLogin) {
        estado = inicial
        regla.setContent {
            TemaEpidemia {
                FormularioLogin(
                    estado = estado,
                    alCambiarUsuario = { estado = estado.copy(usuario = it) },
                    alCambiarPassword = { estado = estado.copy(password = it) },
                    alCambiarRespuesta = { estado = estado.copy(respuesta = it) },
                    alPedirOtroCaptcha = { captchasPedidos++ },
                    alEntrar = { entradas++ },
                )
            }
        }
    }

    @Test
    fun entrar_se_activa_solo_con_todo_lleno() {
        mostrar(EstadoLogin(pregunta = "3 + 5"))
        regla.onNodeWithText("¿Cuánto es 3 + 5?").assertIsDisplayed()
        regla.onNodeWithText("Entrar").assertIsNotEnabled()

        regla.onNodeWithText("Usuario").performTextInput("capturista1")
        regla.onNodeWithText("Contraseña").performTextInput("clave")
        regla.onNodeWithText("Respuesta").performTextInput("8")
        regla.onNodeWithText("Entrar").assertIsEnabled().performClick()

        assertEquals(1, entradas)
        assertEquals("capturista1", estado.usuario)
    }

    @Test
    fun sin_captcha_muestra_el_error_y_deja_reintentar() {
        mostrar(EstadoLogin(error = "No se pudo conectar con los servicios. Revisa tu conexión."))

        regla.onNodeWithText("No se pudo cargar la pregunta.").assertIsDisplayed()
        regla.onNodeWithText("No se pudo conectar con los servicios. Revisa tu conexión.").assertIsDisplayed()
        regla.onNodeWithText("Respuesta").assertIsNotEnabled()
        regla.onNodeWithText("Reintentar").performClick()

        assertEquals(1, captchasPedidos)
    }
}
