package com.estudiante.simuladorepidemico.ui.casos

import com.estudiante.simuladorepidemico.CasosDaoFalso
import com.estudiante.simuladorepidemico.CatalogoDaoFalso
import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.contenedorDePrueba
import com.estudiante.simuladorepidemico.local.Enfermedad
import com.estudiante.simuladorepidemico.local.EstadoCaso
import com.estudiante.simuladorepidemico.local.Municipio
import com.estudiante.simuladorepidemico.tokens
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.time.LocalDate

@OptIn(ExperimentalCoroutinesApi::class)
class CapturaViewModelTest {
    private val hoy = LocalDate.of(2026, 11, 7)
    private val servidor = ServidorFalso()
    private val casos = CasosDaoFalso()
    private val catalogo = CatalogoDaoFalso(listOf(Enfermedad(1, "Dengue")), listOf(Municipio(10, "Monterrey")))
    private var envios = 0
    private val contenedor = contenedorDePrueba(servidor, casos, catalogo) { envios++ }

    @Before
    fun principal() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        runBlocking { contenedor.almacen.abrir(tokens("a1", "r1"), cuenta = 12) }
    }

    @After
    fun apagar() {
        servidor.apagar()
        Dispatchers.resetMain()
    }

    private fun modelo() = CapturaViewModel(
        contenedor.sesion, casos, catalogo, contenedor.catalogos, contenedor.programarEnvio,
        hoy = { hoy }, ahora = { 1_000L },
    )

    private fun CapturaViewModel.espera(condicion: (EstadoCaptura) -> Boolean): EstadoCaptura = runBlocking {
        withTimeout(5_000) {
            while (!condicion(estado)) delay(10)
            estado
        }
    }

    @Test
    fun valida_lo_mismo_que_casos() {
        val vacio = EstadoCaptura(fechaReporte = hoy)
        assertEquals(listOf("Elige la enfermedad.", "Elige el municipio."), erroresDe(vacio, hoy))

        val elegido = vacio.copy(enfermedad = 1, municipio = 10)
        assertEquals(emptyList<String>(), erroresDe(elegido, hoy))
        assertEquals(
            listOf("La fecha de reporte no puede estar en el futuro."),
            erroresDe(elegido.copy(fechaReporte = hoy.plusDays(1)), hoy),
        )
        assertEquals(
            listOf("El inicio de síntomas no puede ser posterior a la fecha de reporte."),
            erroresDe(elegido.copy(fechaReporte = hoy.minusDays(2), inicioSintomas = hoy.minusDays(1)), hoy),
        )
        assertEquals(listOf("La edad va de 0 a 120 años."), erroresDe(elegido.copy(edad = "121"), hoy))
        assertEquals(emptyList<String>(), erroresDe(elegido.copy(edad = "0", inicioSintomas = hoy), hoy))
    }

    @Test
    fun con_errores_no_guarda() {
        val modelo = modelo()

        modelo.guardar()

        assertEquals(2, modelo.estado.errores.size)
        assertTrue(casos.filas.value.isEmpty())
        assertEquals(0, envios)
    }

    @Test
    fun guarda_el_caso_de_la_cuenta_y_pide_el_envio() {
        val modelo = modelo()
        modelo.espera { !it.sinCatalogos }
        modelo.elegirEnfermedad(1)
        modelo.elegirMunicipio(10)
        modelo.cambiarFechaReporte(hoy.minusDays(2))
        modelo.cambiarInicioSintomas(hoy.minusDays(4))
        modelo.cambiarEdad("34 años")
        modelo.elegirSexo("F")
        modelo.elegirSeveridad("leve")

        modelo.guardar()

        val estado = modelo.espera { it.guardados == 1 }
        val caso = casos.filas.value.single()
        assertEquals(12L, caso.cuenta)
        assertTrue(Regex("[0-9a-f-]{36}").matches(caso.localUuid))
        assertEquals("2026-11-05" to "2026-11-03", caso.fechaReporte to caso.inicioSintomas)
        assertEquals(Triple(34, "F", "leve"), Triple(caso.edad, caso.sexo, caso.severidad))
        assertEquals(EstadoCaso.PENDIENTE, caso.estado)
        assertEquals(1_000L, caso.capturadoEn)
        assertEquals(1, envios)
        // Para el siguiente: se quedan enfermedad, municipio y fecha; lo de la persona se limpia.
        assertEquals(Triple(1L, 10L, hoy.minusDays(2)), Triple(estado.enfermedad, estado.municipio, estado.fechaReporte))
        assertEquals("", estado.edad)
        assertNull(estado.sexo)
        assertNull(estado.inicioSintomas)
    }

    @Test
    fun tocar_el_sexo_elegido_lo_quita() {
        val modelo = modelo()

        modelo.elegirSexo("M")
        modelo.elegirSexo("M")

        assertNull(modelo.estado.sexo)
    }

    @Test
    fun sin_catalogos_los_descarga() {
        catalogo.listaEnfermedades.value = emptyList()
        catalogo.listaMunicipios.value = emptyList()
        val modelo = modelo()
        assertTrue(modelo.espera { true }.sinCatalogos)

        modelo.descargarCatalogos()

        val estado = modelo.espera { !it.descargando && !it.sinCatalogos }
        assertEquals(listOf("Dengue", "Influenza"), estado.enfermedades.map { it.nombre })
        assertEquals(listOf("Apodaca", "Monterrey"), estado.municipios.map { it.nombre })
        assertNull(estado.errorCatalogos)
    }

    @Test
    fun sin_red_no_hay_catalogos_y_lo_dice() {
        catalogo.listaEnfermedades.value = emptyList()
        servidor.apagar()
        val modelo = modelo()

        modelo.descargarCatalogos()

        val estado = modelo.espera { !it.descargando }
        assertEquals("No se pudo conectar con los servicios. Revisa tu conexión.", estado.errorCatalogos)
        assertFalse(estado.descargando)
    }
}
