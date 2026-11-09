package com.estudiante.simuladorepidemico.ui

import java.time.Instant
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.Locale

private val ESPANOL = Locale.forLanguageTag("es-MX")
private val FECHA = DateTimeFormatter.ofPattern("d 'de' MMMM 'de' yyyy", ESPANOL)
private val FECHA_Y_HORA = DateTimeFormatter.ofPattern("d 'de' MMMM 'de' yyyy, HH:mm", ESPANOL)
private val HORA = DateTimeFormatter.ofPattern("HH:mm", ESPANOL)

private val ROLES = mapOf(
    "CAPTURISTA" to "Capturista de campo",
    "ANALISTA" to "Analista",
    "EPIDEMIOLOGO" to "Epidemiólogo",
    "ADMINISTRADOR" to "Administrador",
)

fun nombreDeRol(codigo: String): String = ROLES[codigo] ?: codigo

// Los tipos de aviso (CHECK de notifications, migraciones 003 y 029).
private val TIPOS_DE_AVISO = mapOf(
    "RUN_FINISHED" to "Corrida terminada",
    "RUN_FAILED" to "Corrida con error",
    "THRESHOLD_EXCEEDED" to "Umbral superado",
    "ASSIGNMENT" to "Asignación",
    "SCENARIO_PUBLISHED" to "Escenario publicado",
    "SCENARIO_APPROVED" to "Versión aprobada",
    "SYSTEM" to "Aviso del sistema",
)

fun nombreDeAviso(tipo: String): String = TIPOS_DE_AVISO[tipo] ?: "Aviso"

// Los valores que acepta casos (backend_web/queries.py), con su nombre.
val SEXOS = listOf("F" to "Femenino", "M" to "Masculino", "O" to "Otro")
val RESULTADOS_DE_PRUEBA = listOf(
    "positivo" to "Positivo", "negativo" to "Negativo", "pendiente" to "Pendiente", "sin_prueba" to "Sin prueba",
)
val SEVERIDADES = listOf(
    "asintomatico" to "Asintomático", "leve" to "Leve", "grave" to "Grave", "fallecido" to "Fallecido",
)

fun fecha(dia: LocalDate): String = dia.format(FECHA)

// Las fechas de los casos van como AAAA-MM-DD.
fun fecha(iso: String): String = try {
    fecha(LocalDate.parse(iso))
} catch (e: DateTimeParseException) {
    iso
}

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
