package com.estudiante.simuladorepidemico.ui.casos

import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.contenedorDePrueba
import com.estudiante.simuladorepidemico.red.json
import com.estudiante.simuladorepidemico.tokens
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.jsonObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SeguimientoViewModelTest {
    private val servidor = ServidorFalso()
    private val contenedor = contenedorDePrueba(servidor)

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

    private fun modelo() = SeguimientoViewModel(contenedor.apis, contenedor.sesion, 41)

    private fun SeguimientoViewModel.espera(condicion: (EstadoSeguimiento) -> Boolean) = runBlocking {
        withTimeout(5_000) { while (!condicion(estado)) delay(10) }
        estado
    }

    @Test
    fun muestra_el_estado_del_servidor_y_su_historial() {
        val estado = modelo().espera { !it.cargando }

        assertEquals("pendiente", estado.caso!!.status)
        assertTrue(estado.puedeCorregir)
        assertEquals("edad: 33 → 34", textoDeCambios(estado.historial.single().cambios))
    }

    @Test
    fun corrige_solo_lo_que_cambio_con_la_version_que_leyo() {
        val modelo = modelo()
        modelo.espera { !it.cargando }

        modelo.corregir()
        modelo.cambiar { copy(edad = "35", motivo = "Edad mal capturada") }
        modelo.guardar()
        val estado = modelo.espera { !it.cargando && it.correccion == null }

        val pedido = servidor.correcciones.single()
        assertEquals("\"1\"", pedido.getHeader("If-Match"))
        val cuerpo = json.parseToJsonElement(pedido.body.readUtf8()).jsonObject
        assertEquals(setOf("age", "reason"), cuerpo.keys)
        assertEquals(2, estado.caso!!.version)
        assertNull(estado.conflicto)
    }

    @Test
    fun si_otra_persona_lo_cambio_no_lo_pisa_y_muestra_como_quedo() {
        val modelo = modelo()
        modelo.espera { !it.cargando }
        servidor.versionRemota = 2

        modelo.corregir()
        modelo.cambiar { copy(edad = "35") }
        modelo.guardar()
        val estado = modelo.espera { it.conflicto != null }

        assertEquals("Detalle de CONFLICTO.", estado.conflicto)
        assertEquals(2, estado.caso!!.version)
        assertNull(estado.correccion)
    }

    @Test
    fun sin_cambios_no_manda_nada() {
        val modelo = modelo()
        modelo.espera { !it.cargando }

        modelo.corregir()
        modelo.guardar()

        assertTrue(servidor.correcciones.isEmpty())
        assertNull(modelo.estado.correccion)
    }

    @Test
    fun un_caso_ajeno_no_se_puede_corregir() {
        runBlocking { contenedor.almacen.abrir(tokens("a1", "r1"), cuenta = 99) }

        assertFalse(modelo().espera { !it.cargando }.puedeCorregir)
    }
}
