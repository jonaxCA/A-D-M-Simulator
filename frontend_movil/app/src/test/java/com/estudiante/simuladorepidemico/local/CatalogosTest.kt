package com.estudiante.simuladorepidemico.local

import com.estudiante.simuladorepidemico.CatalogoDaoFalso
import com.estudiante.simuladorepidemico.ServidorFalso
import com.estudiante.simuladorepidemico.contenedorDePrueba
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test
import java.io.IOException

class CatalogosTest {
    private val servidor = ServidorFalso()
    private val catalogo = CatalogoDaoFalso()
    private val contenedor = contenedorDePrueba(servidor, catalogo = catalogo)

    @After
    fun apagar() = servidor.apagar()

    @Test
    fun baja_todas_las_paginas_de_enfermedades_activas_y_los_municipios() = runBlocking<Unit> {
        servidor.enfermedades = (1L..150L).map { it to "Enfermedad %03d".format(it) }

        contenedor.catalogos.actualizar()

        val paginas = servidor.pedidosA("/api/v1/diseases").map { it.requestUrl!! }
        assertEquals(listOf("1", "2"), paginas.map { it.queryParameter("page") })
        assertEquals(setOf("activa"), paginas.map { it.queryParameter("status") }.toSet())
        assertEquals(setOf("100"), paginas.map { it.queryParameter("size") }.toSet())
        assertEquals(150, catalogo.enfermedades().first().size)
        assertEquals(listOf("Apodaca", "Monterrey"), catalogo.municipios().first().map { it.nombre })
        // Son públicos: no llevan token.
        assertNull(servidor.pedidosA("/api/v1/regions").single().getHeader("Authorization"))
    }

    @Test
    fun sin_red_se_queda_lo_que_habia() {
        catalogo.listaEnfermedades.value = listOf(Enfermedad(1, "Dengue"))
        servidor.apagar()

        assertThrows(IOException::class.java) { runBlocking { contenedor.catalogos.actualizar() } }

        assertEquals(listOf(Enfermedad(1, "Dengue")), catalogo.listaEnfermedades.value)
    }
}
