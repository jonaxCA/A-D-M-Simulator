package com.estudiante.simuladorepidemico.ui.casos

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.PressInteraction
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuAnchorType
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SelectableDates
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.estudiante.simuladorepidemico.local.Enfermedad
import com.estudiante.simuladorepidemico.local.Municipio
import com.estudiante.simuladorepidemico.ui.RESULTADOS_DE_PRUEBA
import com.estudiante.simuladorepidemico.ui.SEVERIDADES
import com.estudiante.simuladorepidemico.ui.SEXOS
import com.estudiante.simuladorepidemico.ui.fecha
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.util.Locale
import kotlin.math.roundToInt

class AccionesCaptura(
    val volver: () -> Unit = {},
    val elegirEnfermedad: (Long) -> Unit = {},
    val elegirMunicipio: (Long) -> Unit = {},
    val cambiarFechaReporte: (LocalDate) -> Unit = {},
    val cambiarInicioSintomas: (LocalDate?) -> Unit = {},
    val cambiarEdad: (String) -> Unit = {},
    val elegirSexo: (String) -> Unit = {},
    val elegirResultado: (String?) -> Unit = {},
    val elegirSeveridad: (String?) -> Unit = {},
    val guardar: () -> Unit = {},
    val descargarCatalogos: () -> Unit = {},
    val ubicar: () -> Unit = {},
    val quitarUbicacion: () -> Unit = {},
    val abrirAjustes: () -> Unit = {},
)

private const val PRECISA = Manifest.permission.ACCESS_FINE_LOCATION
private const val APROXIMADA = Manifest.permission.ACCESS_COARSE_LOCATION

private fun tiene(contexto: Context, permiso: String) =
    ContextCompat.checkSelfPermission(contexto, permiso) == PackageManager.PERMISSION_GRANTED

@Composable
fun PantallaCaptura(modelo: CapturaViewModel, alVolver: () -> Unit) {
    val contexto = LocalContext.current
    // El permiso se pide al tocar "Agregar mi ubicación", no al abrir la pantalla: la ubicación es
    // opcional. Con solo la aproximada también sirve.
    val pedirPermiso = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { dados ->
        when {
            dados[PRECISA] == true -> modelo.ubicar(precisa = true)
            dados[APROXIMADA] == true -> modelo.ubicar(precisa = false)
            else -> modelo.sinPermisoDeUbicacion()
        }
    }
    FormularioCaso(
        estado = modelo.estado,
        hoy = LocalDate.now(),
        acciones = AccionesCaptura(
            volver = alVolver,
            elegirEnfermedad = modelo::elegirEnfermedad,
            elegirMunicipio = modelo::elegirMunicipio,
            cambiarFechaReporte = modelo::cambiarFechaReporte,
            cambiarInicioSintomas = modelo::cambiarInicioSintomas,
            cambiarEdad = modelo::cambiarEdad,
            elegirSexo = modelo::elegirSexo,
            elegirResultado = modelo::elegirResultado,
            elegirSeveridad = modelo::elegirSeveridad,
            guardar = modelo::guardar,
            descargarCatalogos = modelo::descargarCatalogos,
            ubicar = {
                when {
                    tiene(contexto, PRECISA) -> modelo.ubicar(precisa = true)
                    tiene(contexto, APROXIMADA) -> modelo.ubicar(precisa = false)
                    else -> pedirPermiso.launch(arrayOf(PRECISA, APROXIMADA))
                }
            },
            quitarUbicacion = modelo::quitarUbicacion,
            abrirAjustes = {
                contexto.startActivity(
                    Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", contexto.packageName, null))
                )
            },
        ),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FormularioCaso(estado: EstadoCaptura, hoy: LocalDate, acciones: AccionesCaptura) {
    val avisos = remember { SnackbarHostState() }
    LaunchedEffect(estado.guardados) {
        if (estado.guardados > 0) avisos.showSnackbar("Caso guardado. Se envía en cuanto haya conexión.")
    }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Capturar caso") },
                navigationIcon = {
                    IconButton(onClick = acciones.volver) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(avisos) },
    ) { relleno ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(relleno)
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            if (estado.sinCatalogos) {
                SinCatalogos(estado, acciones.descargarCatalogos)
                return@Column
            }
            Selector(
                etiqueta = "Enfermedad",
                opciones = estado.enfermedades.map { it.id to it.nombre },
                elegido = estado.enfermedad,
                alElegir = acciones.elegirEnfermedad,
            )
            Selector(
                etiqueta = "Municipio",
                opciones = estado.municipios.map { it.id to it.nombre },
                elegido = estado.municipio,
                alElegir = acciones.elegirMunicipio,
            )
            CampoFecha("Fecha de reporte", estado.fechaReporte, hoy, acciones.cambiarFechaReporte)
            CampoFecha(
                "Inicio de síntomas (opcional)", estado.inicioSintomas, hoy, acciones.cambiarInicioSintomas,
                alQuitar = { acciones.cambiarInicioSintomas(null) },
            )
            val foco = LocalFocusManager.current
            OutlinedTextField(
                value = estado.edad,
                onValueChange = acciones.cambiarEdad,
                label = { Text("Edad (opcional)") },
                suffix = { Text("años") },
                singleLine = true,
                // La palomita del teclado lo cierra: el resto del formulario se elige tocando.
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { foco.clearFocus() }),
                modifier = Modifier.fillMaxWidth(),
            )
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Sexo (opcional)", style = MaterialTheme.typography.labelLarge)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    SEXOS.forEach { (valor, nombre) ->
                        FilterChip(
                            selected = estado.sexo == valor,
                            onClick = { acciones.elegirSexo(valor) },
                            label = { Text(nombre) },
                        )
                    }
                }
            }
            Selector(
                etiqueta = "Resultado de prueba (opcional)",
                opciones = RESULTADOS_DE_PRUEBA,
                elegido = estado.resultadoPrueba,
                alElegir = acciones.elegirResultado,
                alQuitar = { acciones.elegirResultado(null) },
            )
            Selector(
                etiqueta = "Severidad (opcional)",
                opciones = SEVERIDADES,
                elegido = estado.severidad,
                alElegir = acciones.elegirSeveridad,
                alQuitar = { acciones.elegirSeveridad(null) },
            )
            SeccionUbicacion(estado, acciones)
            if (estado.errores.isNotEmpty()) {
                Text(
                    estado.errores.joinToString("\n"),
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
                )
            }
            Button(onClick = acciones.guardar, enabled = !estado.guardando, modifier = Modifier.fillMaxWidth()) {
                if (estado.guardando) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                else Text("Guardar caso")
            }
            Text(
                "Se guarda en el teléfono y se envía en cuanto haya conexión, aunque cierres la app.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

// Sin red funciona con el GPS: puede tardar, sobre todo bajo techo.
@Composable
private fun SeccionUbicacion(estado: EstadoCaptura, acciones: AccionesCaptura) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("Ubicación (opcional)", style = MaterialTheme.typography.labelLarge)
        val ubicacion = estado.ubicacion
        if (ubicacion != null) {
            Text("%.6f, %.6f".format(Locale.ROOT, ubicacion.latitud, ubicacion.longitud), style = MaterialTheme.typography.bodyLarge)
            ubicacion.precisionMetros?.let {
                Text(
                    "Precisión: ± %d m".format(it.roundToInt()),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            TextButton(onClick = acciones.quitarUbicacion) { Text("Quitar ubicación") }
            return@Column
        }
        OutlinedButton(onClick = acciones.ubicar, enabled = !estado.ubicando, modifier = Modifier.fillMaxWidth()) {
            if (estado.ubicando) {
                CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
            } else {
                Icon(Icons.Filled.LocationOn, contentDescription = null, modifier = Modifier.size(18.dp))
            }
            Spacer(Modifier.width(8.dp))
            Text(if (estado.ubicando) "Buscando señal…" else "Agregar mi ubicación")
        }
        estado.errorUbicacion?.let {
            Text(
                it,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            )
        }
        if (estado.sinPermisoDeUbicacion) {
            TextButton(onClick = acciones.abrirAjustes) { Text("Abrir ajustes") }
        }
    }
}

@Composable
private fun SinCatalogos(estado: EstadoCaptura, alDescargar: () -> Unit) {
    Text(
        "Para capturar sin conexión, el teléfono necesita los catálogos de enfermedades y " +
            "municipios. Se descargan una vez con conexión.",
        style = MaterialTheme.typography.bodyLarge,
    )
    estado.errorCatalogos?.let {
        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
    }
    Button(onClick = alDescargar, enabled = !estado.descargando) {
        Text(if (estado.descargando) "Descargando…" else "Descargar catálogos")
    }
}

// Con alQuitar, la primera opción deja el campo sin valor.
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun <T> Selector(
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

// Solo fechas hasta hoy: casos rechaza las futuras.
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CampoFecha(
    etiqueta: String,
    dia: LocalDate?,
    hoy: LocalDate,
    alElegir: (LocalDate) -> Unit,
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
    val limite = hoy.enMilisegundos()
    val calendario = rememberDatePickerState(
        initialSelectedDateMillis = (dia ?: hoy).enMilisegundos(),
        selectableDates = object : SelectableDates {
            override fun isSelectableDate(utcTimeMillis: Long) = utcTimeMillis <= limite
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

@Preview(showBackground = true)
@Composable
private fun VistaCaptura() {
    TemaEpidemia {
        FormularioCaso(
            estado = EstadoCaptura(
                fechaReporte = LocalDate.of(2026, 11, 7),
                enfermedades = listOf(Enfermedad(4, "Dengue")),
                municipios = listOf(Municipio(3, "Monterrey")),
                enfermedad = 4,
                municipio = 3,
                sexo = "F",
            ),
            hoy = LocalDate.of(2026, 11, 7),
            acciones = AccionesCaptura(),
        )
    }
}
