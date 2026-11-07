package com.estudiante.simuladorepidemico.ui.casos

import com.estudiante.simuladorepidemico.CasosDaoFalso
import com.estudiante.simuladorepidemico.CatalogoDaoFalso
import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.casoDePrueba
import com.estudiante.simuladorepidemico.contenedorDePrueba
import com.estudiante.simuladorepidemico.local.ConteoFotos
import com.estudiante.simuladorepidemico.local.Enfermedad
import com.estudiante.simuladorepidemico.local.EstadoCaso
import com.estudiante.simuladorepidemico.local.FotoLocal
import com.estudiante.simuladorepidemico.local.Municipio
import com.estudiante.simuladorepidemico.tokens
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class MisCasosViewModelTest {
    private val servidor = ServidorFalso()
    private val casos = CasosDaoFalso()
    private val catalogo = CatalogoDaoFalso(listOf(Enfermedad(1, "Dengue")), listOf(Municipio(10, "Monterrey")))
    private var envios = 0
    private val contenedor = contenedorDePrueba(servidor, casos, catalogo) { envios++ }

    @Before
    fun principal() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        runBlocking {
            contenedor.almacen.abrir(tokens("a1", "r1"), cuenta = 12)
            casos.insertar(casoDePrueba("a", capturadoEn = 1))
            casos.insertar(casoDePrueba("b", capturadoEn = 2, municipio = 77).copy(estado = EstadoCaso.RECHAZADO, error = "Mal."))
            casos.insertar(casoDePrueba("c", cuenta = 13))
        }
    }

    @After
    fun apagar() {
        servidor.apagar()
        Dispatchers.resetMain()
    }

    private fun MisCasosViewModel.esperaFilas(condicion: (List<FilaCaso>) -> Boolean) = runBlocking {
        withTimeout(5_000) { filas.filterNotNull().first(condicion) }
    }

    @Test
    fun solo_los_de_la_cuenta_con_sus_nombres_y_el_mas_nuevo_arriba() {
        val modelo = MisCasosViewModel(contenedor.sesion, casos, catalogo, contenedor.fotos, contenedor.programarEnvio)

        val filas = modelo.esperaFilas { it.isNotEmpty() }

        assertEquals(listOf("b", "a"), filas.map { it.caso.localUuid })
        assertEquals("Dengue" to "Monterrey", filas[1].enfermedad to filas[1].municipio)
        // Un municipio que ya no está en el catálogo sale con su número.
        assertEquals("Municipio 77", filas[0].municipio)
    }

    @Test
    fun descartar_quita_solo_un_rechazado_y_enviar_ahora_pide_el_envio() = runBlocking<Unit> {
        val modelo = MisCasosViewModel(contenedor.sesion, casos, catalogo, contenedor.fotos, contenedor.programarEnvio)

        modelo.descartar(casos.caso("b"))
        modelo.descartar(casos.caso("a"))
        modelo.enviarAhora()

        assertEquals(listOf("a", "c"), casos.filas.value.map { it.localUuid })
        assertEquals(1, envios)
    }

    @Test
    fun cada_caso_dice_como_van_sus_fotos_y_descartarlo_las_borra() = runBlocking<Unit> {
        casos.insertarFotos(listOf(FotoLocal("f1", "b", 0), FotoLocal("f2", "b", 1)))
        casos.marcarFotoRechazada("f2", "Mal.")
        contenedor.fotos.archivo("f1").apply { parentFile!!.mkdirs() }.writeText("foto")
        val modelo = MisCasosViewModel(contenedor.sesion, casos, catalogo, contenedor.fotos, contenedor.programarEnvio)

        val filas = modelo.esperaFilas { lista -> lista.any { it.fotos != null } }
        assertEquals("1 foto por subir · 1 foto rechazada", textoDeFotos(filas.single { it.caso.localUuid == "b" }.fotos!!))
        assertEquals(null, filas.single { it.caso.localUuid == "a" }.fotos)

        modelo.descartar(casos.caso("b"))

        assertEquals(emptyList<FotoLocal>(), casos.fotos.value)
        assertEquals(false, contenedor.fotos.archivo("f1").exists())
    }

    @Test
    fun el_texto_de_las_fotos() {
        assertEquals("2 fotos subidas", textoDeFotos(ConteoFotos("a", 2, 2, 0)))
        assertEquals("1 foto subida · 2 fotos por subir", textoDeFotos(ConteoFotos("a", 3, 1, 0)))
    }
}
