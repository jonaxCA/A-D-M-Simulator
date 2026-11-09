package com.estudiante.simuladorepidemico.ui.avisos

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.estudiante.simuladorepidemico.red.Aviso
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ListaDeAvisosTest {
    @get:Rule
    val regla = createComposeRule()

    private val acciones = mutableListOf<String>()

    private val nuevo = Aviso(7, "RUN_FINISHED", "La corrida SIM-00042 terminó", "Brote de influenza en Monterrey.", null, "2026-10-20T15:02:00+00:00")
    private val viejo = Aviso(6, "SCENARIO_APPROVED", "Versión 2 aprobada", null, "2026-10-20T14:30:00+00:00", "2026-10-20T14:10:00+00:00")

    private fun mostrar(estado: EstadoAvisos, notificaciones: Notificaciones = Notificaciones.ACTIVAS) = regla.setContent {
        TemaEpidemia {
            ListaDeAvisos(
                estado = estado,
                notificaciones = notificaciones,
                acciones = AccionesAvisos(
                    recargar = { acciones += "recargar" },
                    abrir = { acciones += "abrir ${it.id}" },
                    marcarTodos = { acciones += "todos" },
                    permitirNotificaciones = { acciones += "permitir" },
                ),
            )
        }
    }

    private fun estado(texto: String) = SemanticsMatcher.expectValue(SemanticsProperties.StateDescription, texto)

    @Test
    fun los_sin_leer_se_distinguen_y_se_marcan_al_tocarlos() {
        mostrar(EstadoAvisos(cargando = false, avisos = listOf(nuevo, viejo), noLeidos = 1))

        // Para un lector de pantalla, cada fila dice si está leída.
        regla.onNode(hasText("La corrida SIM-00042 terminó").and(estado("Sin leer"))).assertExists()
        regla.onNode(hasText("Versión 2 aprobada").and(estado("Leído"))).assertExists()
        regla.onNodeWithText("Corrida terminada · 20 de octubre de 2026", substring = true).assertIsDisplayed()
        regla.onNodeWithText("Versión aprobada · 20 de octubre de 2026", substring = true).assertIsDisplayed()
        regla.onNodeWithText("La corrida SIM-00042 terminó").performClick()
        regla.onNodeWithText("Versión 2 aprobada").performClick()
        regla.onNodeWithText("Marcar leídos").performClick()
        regla.onNodeWithContentDescription("Actualizar").performClick()

        // El leído no responde al toque.
        assertEquals(listOf("abrir 7", "todos", "recargar"), acciones)
    }

    @Test
    fun ofrece_permitir_las_notificaciones() {
        mostrar(EstadoAvisos(cargando = false, avisos = listOf(viejo)), Notificaciones.PEDIR)

        regla.onNodeWithText("Para que el teléfono te avise cuando llegue uno nuevo, permite las notificaciones.").assertIsDisplayed()
        regla.onNodeWithText("Marcar leídos").assertDoesNotExist()
        regla.onNodeWithText("Permitir notificaciones").performClick()

        assertEquals(listOf("permitir"), acciones)
    }

    @Test
    fun sin_red_lo_dice_y_deja_reintentar() {
        mostrar(EstadoAvisos(cargando = false, error = "Sin conexión: los avisos se consultan con red."))

        regla.onNodeWithText("Sin conexión: los avisos se consultan con red.").assertIsDisplayed()
        regla.onNodeWithText("Reintentar").performClick()

        assertEquals(listOf("recargar"), acciones)
    }

    @Test
    fun sin_avisos() {
        mostrar(EstadoAvisos(cargando = false))

        regla.onNodeWithText("No tienes avisos.").assertIsDisplayed()
    }
}
