package com.estudiante.simuladorepidemico.ui.vacunas

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.estudiante.simuladorepidemico.local.Enfermedad
import com.estudiante.simuladorepidemico.red.LoteVacuna
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.time.LocalDate

@RunWith(AndroidJUnit4::class)
class ContenidoVacunasTest {
    @get:Rule
    val regla = createComposeRule()

    private val acciones = mutableListOf<String>()

    private val lote = LoteVacuna(
        id = 5, codigo = "FL3239-2026", fabricante = "Sanofi Pasteur", enfermedad = 1,
        nombreEnfermedad = "Influenza A", nombreMunicipio = "Monterrey", dosisTotales = 500,
        dosisUsadas = 12, dosisRestantes = 488, caducidad = "2027-03-31",
    )

    private fun mostrar(estado: EstadoVacunas) = regla.setContent {
        TemaEpidemia {
            ContenidoVacunas(
                estado = estado,
                hoy = LocalDate.of(2026, 11, 7),
                acciones = AccionesVacunas(
                    cambiarEscrito = { acciones += "escrito $it" },
                    buscarEscrito = { acciones += "buscar" },
                    cambiarDosis = { acciones += "dosis $it" },
                    aplicar = { acciones += "aplicar" },
                    otroCodigo = { acciones += "otro" },
                    registrar = { acciones += "registrar" },
                ),
                camara = {},
            )
        }
    }

    // Aquí el estado cambia con lo que se escribe, como con el ViewModel.
    @Test
    fun sin_camara_el_codigo_se_puede_escribir() {
        var estado by mutableStateOf(EstadoVacunas())
        regla.setContent {
            TemaEpidemia {
                ContenidoVacunas(
                    estado = estado,
                    hoy = LocalDate.of(2026, 11, 7),
                    acciones = AccionesVacunas(
                        cambiarEscrito = { estado = estado.copy(escrito = it) },
                        buscarEscrito = { acciones += "buscar ${estado.escrito}" },
                    ),
                    camara = {},
                )
            }
        }

        regla.onNodeWithContentDescription("Cámara para leer el código del lote").assertIsDisplayed()
        regla.onNodeWithText("Buscar lote").assertIsNotEnabled()
        regla.onNodeWithText("O escribe el código").performTextInput("FL3239-2026")
        regla.onNodeWithText("Buscar lote").performScrollTo().performClick()

        assertEquals(listOf("buscar FL3239-2026"), acciones)
    }

    @Test
    fun el_lote_dice_cuantas_quedan_y_aplica() {
        mostrar(EstadoVacunas(paso = Paso.LOTE, lote = lote, dosis = 2, aviso = "Se aplicaron 3 dosis. Quedan 488."))

        regla.onNodeWithText("Quedan 488 de 500").assertIsDisplayed()
        regla.onNodeWithText("31 de marzo de 2027").assertIsDisplayed()
        regla.onNodeWithText("Se aplicaron 3 dosis. Quedan 488.").performScrollTo().assertIsDisplayed()
        regla.onNodeWithContentDescription("Una dosis más").performScrollTo().performClick()
        regla.onNodeWithText("Aplicar 2 dosis").performScrollTo().performClick()
        regla.onNodeWithText("Escanear otro lote").performScrollTo().performClick()

        assertEquals(listOf("dosis 3", "aplicar", "otro"), acciones)
    }

    @Test
    fun un_lote_caducado_no_ofrece_aplicar() {
        mostrar(EstadoVacunas(paso = Paso.LOTE, lote = lote.copy(caducidad = "2026-10-01", vencido = true)))

        regla.onNodeWithText("1 de octubre de 2026 · caducado").assertIsDisplayed()
        regla.onNodeWithText("Caducado: ya no se le pueden aplicar dosis.").performScrollTo().assertIsDisplayed()
        regla.onNodeWithText("Aplicar 1 dosis").assertDoesNotExist()
    }

    @Test
    fun uno_sin_registrar_pide_sus_datos() {
        mostrar(
            EstadoVacunas(
                paso = Paso.REGISTRAR, codigo = "NUEVO-01", enfermedades = listOf(Enfermedad(1, "Influenza A")),
                error = "Elige la enfermedad del lote.",
            )
        )

        regla.onNodeWithText("El lote NUEVO-01 no está registrado. Regístralo con los datos de la caja.").assertIsDisplayed()
        regla.onNodeWithText("Elige la enfermedad del lote.").performScrollTo().assertIsDisplayed()
        regla.onNodeWithText("Registrar lote").performScrollTo().performClick()

        assertEquals(listOf("registrar"), acciones)
    }

    @Test
    fun mientras_aplica_no_deja_tocar_de_nuevo() {
        mostrar(EstadoVacunas(paso = Paso.LOTE, lote = lote, dosis = 1, aplicando = true))

        regla.onNodeWithContentDescription("Una dosis más").performScrollTo().assertIsNotEnabled()
    }
}
