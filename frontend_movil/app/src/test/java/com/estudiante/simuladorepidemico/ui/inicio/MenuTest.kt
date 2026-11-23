package com.estudiante.simuladorepidemico.ui.inicio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

// D54: lo que ofrece el inicio a cada perfil de D42.
class MenuTest {
    @Test
    fun el_capturista_captura_y_registra_lotes() {
        val menu = menuDe(setOf("CAPTURISTA"))

        assertTrue(menu.captura && menu.lotesRegistra)
        assertFalse(menu.revisa)
        assertEquals(
            setOf(Opcion.CAPTURAR, Opcion.MIS_CASOS, Opcion.CAMPANAS, Opcion.LOTES, Opcion.CONSULTA, Opcion.AVISOS, Opcion.PERFIL),
            menu.opciones,
        )
    }

    @Test
    fun el_epidemiologo_y_la_autoridad_consultan_sin_capturar_ni_aplicar_dosis() {
        for (rol in listOf("EPIDEMIOLOGO", "AUTORIDAD_SANITARIA")) {
            val menu = menuDe(setOf(rol))

            assertFalse(rol, menu.captura || menu.lotesRegistra)
            assertTrue(rol, menu.revisa)
            assertEquals(
                rol,
                setOf(Opcion.CASOS_SERVIDOR, Opcion.CAMPANAS, Opcion.LOTES, Opcion.CONSULTA, Opcion.AVISOS, Opcion.PERFIL),
                menu.opciones,
            )
        }
    }

    @Test
    fun el_administrador_revisa_y_registra_lotes_pero_no_captura() {
        val menu = menuDe(setOf("ADMINISTRADOR"))

        assertTrue(menu.revisa && menu.lotesRegistra)
        assertFalse(menu.captura)
    }

    @Test
    fun analista_e_investigador_solo_consultan_por_zona() {
        for (rol in listOf("ANALISTA", "INVESTIGADOR")) {
            assertEquals(rol, setOf(Opcion.CONSULTA, Opcion.AVISOS, Opcion.PERFIL), menuDe(setOf(rol)).opciones)
        }
    }

    @Test
    fun sin_roles_conocidos_queda_el_del_capturista() {
        assertEquals(menuDe(setOf("CAPTURISTA")), menuDe(null))
    }

    @Test
    fun un_perfil_que_la_app_no_conoce_solo_ve_avisos_y_perfil() {
        assertEquals(Menu(setOf(Opcion.AVISOS, Opcion.PERFIL), lotesRegistra = false), menuDe(setOf("OTRO")))
    }

    @Test
    fun con_dos_perfiles_ve_lo_de_los_dos() {
        val menu = menuDe(setOf("CAPTURISTA", "EPIDEMIOLOGO"))

        assertTrue(menu.captura && menu.revisa && menu.lotesRegistra)
    }
}
