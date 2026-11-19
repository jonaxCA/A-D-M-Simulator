package com.estudiante.simuladorepidemico.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.Instant
import java.time.ZoneId

class FormatoTest {
    private val monterrey = ZoneId.of("America/Monterrey")

    @Test
    fun fecha_iso_en_espanol_y_en_la_zona_del_telefono() {
        assertEquals("6 de noviembre de 2026, 09:30", fechaYHora("2026-11-06T09:30:00-06:00", monterrey))
        assertEquals("6 de noviembre de 2026, 09:30", fechaYHora("2026-11-06T15:30:00Z", monterrey))
        assertNull(fechaYHora(null, monterrey))
        assertEquals("ayer", fechaYHora("ayer", monterrey))
    }

    @Test
    fun el_vencimiento_dice_solo_la_hora_si_es_hoy() {
        val ahora = Instant.parse("2026-11-06T15:00:00Z")
        assertEquals("hoy a las 17:30", momento(Instant.parse("2026-11-06T23:30:00Z").epochSecond, monterrey, ahora))
        assertEquals("7 de noviembre de 2026, 01:00", momento(Instant.parse("2026-11-07T07:00:00Z").epochSecond, monterrey, ahora))
    }

    @Test
    fun los_roles_con_su_nombre() {
        assertEquals("Capturista de campo", nombreDeRol("CAPTURISTA"))
        assertEquals("Epidemiólogo", nombreDeRol("EPIDEMIOLOGO"))
        assertEquals("NUEVO_ROL", nombreDeRol("NUEVO_ROL"))
    }
}
