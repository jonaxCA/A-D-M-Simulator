package com.estudiante.simuladorepidemico.ui

import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.PressInteraction
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuAnchorType
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SelectableDates
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

// Los campos que comparten los formularios (captura de casos, registro de lotes).

// Una lista para elegir. Con alQuitar, la primera opción deja el campo sin valor.
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun <T> Selector(
    etiqueta: String,
    opciones: List<Pair<T, String>>,
    elegido: T?,
    alElegir: (T) -> Unit,
    alQuitar: (() -> Unit)? = null,
) {
    var abierto by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = abierto, onExpandedChange = { abierto = it }) {
        OutlinedTextField(
            value = opciones.firstOrNull { it.first == elegido }?.second ?: "",
            onValueChange = {},
            readOnly = true,
            label = { Text(etiqueta) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = abierto) },
            modifier = Modifier.menuAnchor(ExposedDropdownMenuAnchorType.PrimaryNotEditable).fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = abierto, onDismissRequest = { abierto = false }) {
            if (alQuitar != null) {
                DropdownMenuItem(text = { Text("Sin especificar") }, onClick = { alQuitar(); abierto = false })
            }
            opciones.forEach { (valor, nombre) ->
                DropdownMenuItem(text = { Text(nombre) }, onClick = { alElegir(valor); abierto = false })
            }
        }
    }
}

// Una fecha con el calendario de Material. Con `hasta`, no se puede elegir una posterior (los
// casos no aceptan fechas futuras); `inicial` es donde abre si el campo está vacío.
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun CampoFecha(
    etiqueta: String,
    dia: LocalDate?,
    alElegir: (LocalDate) -> Unit,
    inicial: LocalDate,
    hasta: LocalDate? = null,
    alQuitar: (() -> Unit)? = null,
) {
    var abierto by remember { mutableStateOf(false) }
    // El campo es de solo lectura: tocarlo abre el calendario. Con lector de pantalla, el botón
    // del calendario hace lo mismo y el campo se sigue leyendo.
    val toques = remember { MutableInteractionSource() }
    LaunchedEffect(toques) {
        toques.interactions.collect { if (it is PressInteraction.Release) abierto = true }
    }
    OutlinedTextField(
        value = dia?.let { fecha(it) } ?: "",
        onValueChange = {},
        readOnly = true,
        label = { Text(etiqueta) },
        trailingIcon = {
            IconButton(onClick = { abierto = true }) {
                Icon(Icons.Filled.DateRange, contentDescription = "Elegir ${etiqueta.lowercase()}")
            }
        },
        interactionSource = toques,
        modifier = Modifier.fillMaxWidth(),
    )
    if (!abierto) return
    val limite = hasta?.enMilisegundos()
    val calendario = rememberDatePickerState(
        initialSelectedDateMillis = (dia ?: inicial).enMilisegundos(),
        selectableDates = object : SelectableDates {
            override fun isSelectableDate(utcTimeMillis: Long) = limite == null || utcTimeMillis <= limite
        },
    )
    DatePickerDialog(
        onDismissRequest = { abierto = false },
        confirmButton = {
            TextButton(onClick = {
                calendario.selectedDateMillis?.let { alElegir(it.enDia()) }
                abierto = false
            }) { Text("Aceptar") }
        },
        dismissButton = {
            Row {
                if (alQuitar != null && dia != null) {
                    TextButton(onClick = { alQuitar(); abierto = false }) { Text("Quitar") }
                }
                TextButton(onClick = { abierto = false }) { Text("Cancelar") }
            }
        },
    ) {
        DatePicker(state = calendario)
    }
}

// El calendario de Material trabaja en milisegundos UTC a medianoche.
private fun LocalDate.enMilisegundos() = atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()
private fun Long.enDia(): LocalDate = Instant.ofEpochMilli(this).atOffset(ZoneOffset.UTC).toLocalDate()
