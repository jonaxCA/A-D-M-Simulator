package com.estudiante.simuladorepidemico.local

import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith

// Las consultas de verdad, en SQLite del teléfono. Las pruebas locales usan un DAO falso.
@RunWith(AndroidJUnit4::class)
class CasosDaoTest {
    private val base = Room.inMemoryDatabaseBuilder(
        InstrumentationRegistry.getInstrumentation().targetContext, BaseLocal::class.java,
    ).build()
    private val dao = base.casos()

    @After
    fun cerrar() = base.close()

    private fun caso(uuid: String, cuenta: Long = 12, capturadoEn: Long = 1) = CasoLocal(
        localUuid = uuid, cuenta = cuenta, enfermedad = 1, municipio = 10, fechaReporte = "2026-11-05",
        edad = 34, sexo = "F", latitud = 25.67, longitud = -100.31, capturadoEn = capturadoEn,
    )

    @Test
    fun el_lote_lleva_los_pendientes_mas_viejos_de_la_cuenta_y_se_reusa_sin_respuesta() = runBlocking {
        dao.insertar(caso("c", capturadoEn = 3))
        dao.insertar(caso("a", capturadoEn = 1))
        dao.insertar(caso("b", capturadoEn = 2))
        dao.insertar(caso("x", cuenta = 13))

        val lote = dao.siguienteLote(12, "L1", maximo = 2)!!

        assertEquals("L1", lote.id)
        assertEquals(listOf("a", "b"), lote.casos.map { it.localUuid })
        // Mientras no responde, vuelve el mismo lote aunque se pida otro id.
        assertEquals(listOf("a", "b"), dao.siguienteLote(12, "L2", maximo = 2)!!.casos.map { it.localUuid })
        assertNull(dao.siguienteLote(14, "L3"))
    }

    @Test
    fun aplicar_deja_el_comprobante_y_suelta_lo_que_no_se_resolvio() = runBlocking {
        listOf("a", "b", "c").forEachIndexed { i, uuid -> dao.insertar(caso(uuid, capturadoEn = i.toLong())) }
        val lote = dao.siguienteLote(12, "L1")!!

        dao.aplicar(lote.id, enviados = mapOf("a" to 41L), rechazados = mapOf("b" to "Mal."))

        val porId = dao.deLaCuenta(12).first().associateBy { it.localUuid }
        val enviado = porId.getValue("a")
        assertEquals(EstadoCaso.ENVIADO to 41L, enviado.estado to enviado.caseId)
        // Lo que identifica a la persona ya no se queda en el teléfono.
        assertEquals(listOf(null, null, null, null), listOf(enviado.edad, enviado.sexo, enviado.latitud, enviado.longitud))
        assertEquals("2026-11-05", enviado.fechaReporte)
        assertEquals(EstadoCaso.RECHAZADO to "Mal.", porId.getValue("b").let { it.estado to it.error })
        assertEquals(34, porId.getValue("b").edad)
        assertEquals(EstadoCaso.PENDIENTE to null, porId.getValue("c").let { it.estado to it.lote })
        assertEquals(1, dao.porEnviar(12).first())
        assertEquals("L2", dao.siguienteLote(12, "L2")!!.id)
    }

    @Test
    fun descartar_solo_borra_un_rechazado() = runBlocking {
        dao.insertar(caso("a"))
        dao.insertar(caso("b", capturadoEn = 2))
        dao.aplicar(dao.siguienteLote(12, "L1")!!.id, emptyMap(), mapOf("b" to "Mal."))

        dao.descartar("a")
        dao.descartar("b")

        assertEquals(listOf("a"), dao.deLaCuenta(12).first().map { it.localUuid })
    }
}
