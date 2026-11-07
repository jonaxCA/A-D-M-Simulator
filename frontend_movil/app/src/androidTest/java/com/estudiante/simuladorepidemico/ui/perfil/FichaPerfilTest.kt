package com.estudiante.simuladorepidemico.ui.perfil

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.estudiante.simuladorepidemico.red.Perfil
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class FichaPerfilTest {
    @get:Rule
    val regla = createComposeRule()

    private val acciones = mutableListOf<String>()

    private fun mostrar(estado: EstadoPerfil) = regla.setContent {
        TemaEpidemia {
            FichaPerfil(
                estado = estado,
                alVolver = { acciones += "volver" },
                alReintentar = { acciones += "reintentar" },
                alRegistrarTelefono = { acciones += "registrar" },
                alCerrarSesion = { acciones += "cerrar" },
            )
        }
    }

    private val carla = Perfil(12, "capturista1", "Carla Captura", null, null, listOf("CAPTURISTA"))

    @Test
    fun muestra_la_cuenta_y_cierra_la_sesion() {
        mostrar(EstadoPerfil(cargando = false, perfil = carla, dispositivo = 3))

        regla.onNodeWithText("Carla Captura").assertIsDisplayed()
        regla.onNodeWithText("Capturista de campo").assertIsDisplayed()
        regla.onNodeWithText("Sin correo").assertIsDisplayed()
        regla.onNodeWithText("Registrado como dispositivo 3").performScrollTo().assertIsDisplayed()
        regla.onNodeWithText("Registrar este teléfono").assertDoesNotExist()
        regla.onNodeWithText("Cerrar sesión").performScrollTo().performClick()
        regla.onNodeWithContentDescription("Volver").performClick()

        assertEquals(listOf("cerrar", "volver"), acciones)
    }

    @Test
    fun sin_registro_del_telefono_deja_registrarlo() {
        mostrar(EstadoPerfil(cargando = false, perfil = carla, errorTelefono = "Detalle del error."))

        regla.onNodeWithText("Sin registrar").performScrollTo().assertIsDisplayed()
        regla.onNodeWithText("Detalle del error.").assertIsDisplayed()
        regla.onNodeWithText("Registrar este teléfono").performScrollTo().performClick()

        assertEquals(listOf("registrar"), acciones)
    }

    @Test
    fun sin_perfil_muestra_el_error_y_reintenta() {
        mostrar(EstadoPerfil(cargando = false, error = "No se pudo conectar con los servicios. Revisa tu conexión."))

        regla.onNodeWithText("No se pudo conectar con los servicios. Revisa tu conexión.").assertIsDisplayed()
        regla.onNodeWithText("Reintentar").performClick()

        assertEquals(listOf("reintentar"), acciones)
    }
}
