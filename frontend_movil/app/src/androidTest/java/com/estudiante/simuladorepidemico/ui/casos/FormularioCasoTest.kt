package com.estudiante.simuladorepidemico.ui.casos

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.estudiante.simuladorepidemico.local.Enfermedad
import com.estudiante.simuladorepidemico.local.Municipio
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia
import com.estudiante.simuladorepidemico.ubicacion.Ubicacion
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.time.LocalDate

@RunWith(AndroidJUnit4::class)
class FormularioCasoTest {
    @get:Rule
    val regla = createComposeRule()

    private val hoy = LocalDate.of(2026, 11, 7)
    private val acciones = mutableListOf<String>()

    private fun mostrar(estado: EstadoCaptura) = regla.setContent {
        TemaEpidemia {
            FormularioCaso(
                estado = estado,
                hoy = hoy,
                acciones = AccionesCaptura(
                    cambiarFechaReporte = { acciones += "reporte $it" },
                    elegirMunicipio = { acciones += "municipio $it" },
                    elegirSexo = { acciones += "sexo $it" },
                    guardar = { acciones += "guardar" },
                    descargarCatalogos = { acciones += "descargar" },
                    ubicar = { acciones += "ubicar" },
                    quitarUbicacion = { acciones += "quitar" },
                    abrirAjustes = { acciones += "ajustes" },
                ),
            )
        }
    }

    private val conCatalogos = EstadoCaptura(
        fechaReporte = hoy,
        enfermedades = listOf(Enfermedad(1, "Dengue")),
        municipios = listOf(Municipio(10, "Monterrey")),
    )

    @Test
    fun la_ubicacion_muestra_las_coordenadas_y_su_precision() {
        mostrar(conCatalogos.copy(ubicacion = Ubicacion(25.686613, -100.316116, 12.4f)))

        regla.onNodeWithText("25.686613, -100.316116").performScrollTo().assertIsDisplayed()
        regla.onNodeWithText("Precisión: ± 12 m").assertIsDisplayed()
        regla.onNodeWithText("Agregar mi ubicación").assertDoesNotExist()
        regla.onNodeWithText("Quitar ubicación").performClick()

        assertEquals(listOf("quitar"), acciones)
    }

    @Test
    fun sin_permiso_de_ubicacion_ofrece_los_ajustes() {
        mostrar(conCatalogos.copy(sinPermisoDeUbicacion = true, errorUbicacion = "Sin permiso de ubicación: el caso se guarda sin ella."))

        regla.onNodeWithText("Sin permiso de ubicación: el caso se guarda sin ella.").performScrollTo().assertIsDisplayed()
        regla.onNodeWithText("Agregar mi ubicación").performClick()
        regla.onNodeWithText("Abrir ajustes").performScrollTo().performClick()

        assertEquals(listOf("ubicar", "ajustes"), acciones)
    }

    @Test
    fun elige_de_los_catalogos_muestra_los_errores_y_guarda() {
        mostrar(
            EstadoCaptura(
                fechaReporte = hoy,
                enfermedades = listOf(Enfermedad(1, "Dengue")),
                municipios = listOf(Municipio(10, "Monterrey"), Municipio(11, "Apodaca")),
                enfermedad = 1,
                errores = listOf("Elige el municipio."),
            )
        )

        regla.onNodeWithText("Dengue").assertIsDisplayed()
        regla.onNodeWithText("7 de noviembre de 2026").assertIsDisplayed()
        regla.onNodeWithText("Municipio").performClick()
        regla.onNodeWithText("Apodaca").performClick()
        regla.onNodeWithText("Femenino").performScrollTo().performClick()
        regla.onNodeWithText("Elige el municipio.").performScrollTo().assertIsDisplayed()
        regla.onNodeWithText("Guardar caso").performScrollTo().performClick()

        assertEquals(listOf("municipio 11", "sexo F", "guardar"), acciones)
    }

    // El botón del calendario es el camino de un lector de pantalla; el campo se sigue leyendo.
    @Test
    fun la_fecha_se_elige_en_el_calendario() {
        mostrar(
            EstadoCaptura(
                fechaReporte = hoy.minusDays(1),
                enfermedades = listOf(Enfermedad(1, "Dengue")),
                municipios = listOf(Municipio(10, "Monterrey")),
            )
        )

        regla.onNodeWithText("6 de noviembre de 2026").assertIsDisplayed()
        regla.onNodeWithContentDescription("Elegir fecha de reporte").performClick()
        regla.onNodeWithText("Aceptar").performClick()

        assertEquals(listOf("reporte 2026-11-06"), acciones)
    }

    @Test
    fun sin_catalogos_ofrece_descargarlos() {
        mostrar(EstadoCaptura(fechaReporte = hoy, errorCatalogos = "No se pudo conectar con los servicios. Revisa tu conexión."))

        regla.onNodeWithText("No se pudo conectar con los servicios. Revisa tu conexión.").assertIsDisplayed()
        regla.onNodeWithText("Guardar caso").assertDoesNotExist()
        regla.onNodeWithText("Descargar catálogos").performClick()

        assertEquals(listOf("descargar"), acciones)
    }
}
