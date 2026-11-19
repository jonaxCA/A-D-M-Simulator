package com.estudiante.simuladorepidemico.ui.vacunas

import com.estudiante.simuladorepidemico.CatalogoDaoFalso
import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.contenedorDePrueba
import com.estudiante.simuladorepidemico.local.Enfermedad
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
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.time.LocalDate

@OptIn(ExperimentalCoroutinesApi::class)
class VacunasViewModelTest {
    private val servidor = ServidorFalso()
    private val catalogo = CatalogoDaoFalso(listOf(Enfermedad(1, "Influenza A")))
    private val contenedor = contenedorDePrueba(servidor, catalogo = catalogo)

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

    private fun modelo() = VacunasViewModel(contenedor.apis, catalogo)

    private fun VacunasViewModel.espera(condicion: (EstadoVacunas) -> Boolean): EstadoVacunas = runBlocking {
        withTimeout(5_000) {
            while (!condicion(estado)) delay(10)
            estado
        }
    }

    private fun dosisPedidas() = servidor.pedidos.filter { it.path.orEmpty().endsWith("/doses") }

    @Test
    fun un_codigo_registrado_muestra_el_lote() {
        servidor.nuevoLote("FL3239-2026", total = 500, usadas = 12)
        val modelo = modelo()

        modelo.leido(" FL3239-2026 ")

        val estado = modelo.espera { it.paso == Paso.LOTE }
        assertEquals("FL3239-2026" to 488, estado.lote!!.codigo to estado.lote.dosisRestantes)
        val busqueda = servidor.pedidosA("/api/v1/vaccine-lots").single()
        assertEquals("FL3239-2026", busqueda.requestUrl!!.queryParameter("lot_code"))
        assertEquals("Bearer a1", busqueda.getHeader("Authorization"))
    }

    @Test
    fun la_camara_lee_varias_veces_pero_solo_se_busca_una() {
        servidor.nuevoLote("FL-1", total = 5)
        val modelo = modelo()

        repeat(5) { modelo.leido("FL-1") }
        modelo.espera { it.paso == Paso.LOTE }
        modelo.leido("OTRO")

        assertEquals(1, servidor.pedidosA("/api/v1/vaccine-lots").size)
        assertEquals("FL-1", modelo.estado.lote!!.codigo)
    }

    @Test
    fun un_codigo_con_espacios_no_se_busca() {
        val modelo = modelo()

        modelo.leido("no es un lote")

        assertTrue(modelo.estado.error!!.startsWith("Ese código no parece de un lote"))
        assertEquals(Paso.ESCANEAR, modelo.estado.paso)
        assertTrue(servidor.pedidosA("/api/v1/vaccine-lots").isEmpty())
    }

    @Test
    fun uno_nuevo_se_registra_con_los_datos_de_la_caja() {
        val modelo = modelo()
        modelo.cambiarEscrito("NUEVO-01")
        modelo.buscarEscrito()
        modelo.espera { it.paso == Paso.REGISTRAR }

        modelo.registrar()
        assertEquals("Elige la enfermedad del lote.", modelo.estado.error)
        modelo.cambiarRegistro { copy(enfermedad = 1, dosisTotales = "0") }
        modelo.registrar()
        assertEquals("Las dosis del lote van de 1 a 1,000,000.", modelo.estado.error)
        modelo.cambiarRegistro { copy(dosisTotales = "200", fabricante = "  Pfizer ", caducidad = LocalDate.of(2027, 3, 31)) }
        modelo.registrar()

        val estado = modelo.espera { it.paso == Paso.LOTE }
        assertEquals("NUEVO-01" to 200, estado.lote!!.codigo to estado.lote.dosisRestantes)
        assertEquals("Lote registrado.", estado.aviso)
        val alta = servidor.pedidos.single { it.method == "POST" && it.path!!.startsWith("/api/v1/vaccine-lots") }
        val cuerpo = json.parseToJsonElement(alta.body.readUtf8()).jsonObject
        assertEquals("NUEVO-01", cuerpo["lot_code"]!!.jsonPrimitive.content)
        assertEquals(200, cuerpo["doses_total"]!!.jsonPrimitive.int)
        assertEquals(1L, cuerpo["disease_id"]!!.jsonPrimitive.long)
        assertEquals("Pfizer", cuerpo["manufacturer"]!!.jsonPrimitive.content)
        assertEquals("2027-03-31", cuerpo["expires_on"]!!.jsonPrimitive.content)
        assertTrue("region_id" !in cuerpo)
    }

    @Test
    fun si_otro_lo_registro_distinto_muestra_el_suyo() {
        val modelo = modelo()
        modelo.leido("EW0153")
        modelo.espera { it.paso == Paso.REGISTRAR }
        // Mientras tanto, otro teléfono lo registró con otras dosis.
        servidor.nuevoLote("EW0153", total = 300)
        modelo.cambiarRegistro { copy(enfermedad = 1, dosisTotales = "200") }

        modelo.registrar()

        val estado = modelo.espera { it.paso == Paso.LOTE }
        assertEquals(300, estado.lote!!.dosisTotales)
        assertEquals("Detalle de CONFLICTO. Estos son sus datos.", estado.error)
    }

    @Test
    fun aplicar_descuenta_y_dice_cuantas_quedan() {
        servidor.nuevoLote("FL-1", total = 10)
        val modelo = modelo()
        modelo.leido("FL-1")
        modelo.espera { it.paso == Paso.LOTE }

        modelo.cambiarDosis(30)
        assertEquals(10, modelo.estado.dosis)
        modelo.cambiarDosis(0)
        assertEquals(1, modelo.estado.dosis)
        modelo.cambiarDosis(3)
        modelo.aplicar()

        val estado = modelo.espera { !it.aplicando && it.aviso != null }
        assertEquals("Se aplicaron 3 dosis. Quedan 7.", estado.aviso)
        assertEquals(7 to 1, estado.lote!!.dosisRestantes to estado.dosis)
        assertEquals(3, servidor.lotesVacuna.getValue("FL-1").usadas)
    }

    @Test
    fun si_otro_telefono_las_gasto_lo_dice_y_muestra_lo_que_queda() {
        val lote = servidor.nuevoLote("FL-1", total = 5)
        val modelo = modelo()
        modelo.leido("FL-1")
        modelo.espera { it.paso == Paso.LOTE }
        modelo.cambiarDosis(2)
        lote.usadas = 4

        modelo.aplicar()

        val estado = modelo.espera { !it.aplicando && it.lote!!.dosisRestantes == 1 }
        assertEquals("Detalle de CONFLICTO.", estado.error)
        assertEquals(1, estado.dosis)
        assertEquals(4, lote.usadas)
    }

    @Test
    fun si_se_corta_la_respuesta_no_se_vuelve_a_aplicar() {
        servidor.nuevoLote("FL-1", total = 10)
        val modelo = modelo()
        modelo.leido("FL-1")
        modelo.espera { it.paso == Paso.LOTE }
        modelo.cambiarDosis(2)
        servidor.cortarDosis = true

        modelo.aplicar()

        val estado = modelo.espera { !it.aplicando && it.error != null }
        // Una sola vez, aunque la respuesta nunca llegó.
        assertEquals(1, dosisPedidas().size)
        assertEquals(2, servidor.lotesVacuna.getValue("FL-1").usadas)
        assertTrue(estado.error!!.startsWith("No se pudo confirmar si se aplicaron."))
        assertEquals(8, modelo.espera { it.lote!!.dosisRestantes == 8 }.lote!!.dosisRestantes)
        assertNull(estado.aviso)
    }

    @Test
    fun un_lote_caducado_no_deja_aplicar() {
        servidor.nuevoLote("VIEJO", total = 10, vencido = true)
        val modelo = modelo()
        modelo.leido("VIEJO")
        modelo.espera { it.paso == Paso.LOTE }

        modelo.aplicar()

        assertEquals("Este lote caducó: ya no se le pueden aplicar dosis.", modelo.estado.error)
        assertTrue(dosisPedidas().isEmpty())
    }

    @Test
    fun sin_red_lo_dice_y_se_queda_escaneando() {
        servidor.apagar()
        val modelo = modelo()

        modelo.leido("FL-1")

        val estado = modelo.espera { it.paso == Paso.ESCANEAR && it.error != null }
        assertEquals("Sin conexión: consultar lotes y aplicar dosis necesita red.", estado.error)
    }

    @Test
    fun escanear_otro_empieza_de_nuevo_y_conserva_los_catalogos() {
        servidor.nuevoLote("FL-1", total = 10)
        val modelo = modelo()
        modelo.leido("FL-1")
        modelo.espera { it.paso == Paso.LOTE }

        modelo.otroCodigo()

        assertEquals(Paso.ESCANEAR, modelo.estado.paso)
        assertNull(modelo.estado.lote)
        assertEquals(listOf("Influenza A"), modelo.estado.enfermedades.map { it.nombre })
    }
}
