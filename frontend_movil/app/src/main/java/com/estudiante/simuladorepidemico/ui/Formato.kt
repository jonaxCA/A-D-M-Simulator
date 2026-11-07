package com.estudiante.simuladorepidemico.ui

import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.Locale

private val ESPANOL = Locale.forLanguageTag("es-MX")
private val FECHA_Y_HORA = DateTimeFormatter.ofPattern("d 'de' MMMM 'de' yyyy, HH:mm", ESPANOL)
private val HORA = DateTimeFormatter.ofPattern("HH:mm", ESPANOL)

private val ROLES = mapOf(
    "CAPTURISTA" to "Capturista de campo",
    "ANALISTA" to "Analista",
    "EPIDEMIOLOGO" to "Epidemiólogo",
    "ADMINISTRADOR" to "Administrador",
)

fun nombreDeRol(codigo: String): String = ROLES[codigo] ?: codigo

// Los servicios mandan fechas ISO 8601 con zona ("2026-11-06T09:30:00-06:00").
fun fechaYHora(iso: String?, zona: ZoneId = ZoneId.systemDefault()): String? = try {
    iso?.let { OffsetDateTime.parse(it).atZoneSameInstant(zona).format(FECHA_Y_HORA) }
} catch (e: DateTimeParseException) {
    iso
}

// Solo la hora si es hoy; si no, también la fecha.
fun momento(epoca: Long, zona: ZoneId = ZoneId.systemDefault(), ahora: Instant = Instant.now()): String {
    val cuando = Instant.ofEpochSecond(epoca).atZone(zona)
    val hoy = ahora.atZone(zona).toLocalDate()
    return if (cuando.toLocalDate() == hoy) "hoy a las ${cuando.format(HORA)}" else cuando.format(FECHA_Y_HORA)
}
