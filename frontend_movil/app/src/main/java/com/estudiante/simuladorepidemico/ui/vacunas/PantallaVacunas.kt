package com.estudiante.simuladorepidemico.ui.vacunas

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import com.estudiante.simuladorepidemico.red.LoteVacuna
import com.estudiante.simuladorepidemico.ui.CampoFecha
import com.estudiante.simuladorepidemico.ui.Selector
import com.estudiante.simuladorepidemico.ui.fecha
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia
import java.time.LocalDate

class AccionesVacunas(
    val volver: () -> Unit = {},
    val cambiarEscrito: (String) -> Unit = {},
    val buscarEscrito: () -> Unit = {},
    val cambiarDosis: (Int) -> Unit = {},
    val aplicar: () -> Unit = {},
    val otroCodigo: () -> Unit = {},
    val cambiarRegistro: (DatosLote.() -> DatosLote) -> Unit = {},
    val registrar: () -> Unit = {},
)

private fun tieneCamara(contexto: Context) =
    ContextCompat.checkSelfPermission(contexto, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

@Composable
fun PantallaVacunas(modelo: VacunasViewModel, alVolver: () -> Unit) {
    val contexto = LocalContext.current
    var conCamara by rememberSaveable { mutableStateOf(tieneCamara(contexto)) }
    var negada by rememberSaveable { mutableStateOf(false) }
    var preguntada by rememberSaveable { mutableStateOf(false) }
    val pedir = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { dado ->
        conCamara = dado
        negada = !dado
    }
    // La pantalla es para escanear: se pide al entrar, una vez. Sin permiso se puede escribir el
    // código a mano.
    LaunchedEffect(Unit) {
        if (!conCamara && !preguntada) {
            preguntada = true
            pedir.launch(Manifest.permission.CAMERA)
        }
    }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { conCamara = tieneCamara(contexto) }
    ContenidoVacunas(
        estado = modelo.estado,
        hoy = LocalDate.now(),
        acciones = AccionesVacunas(
            volver = alVolver,
            cambiarEscrito = modelo::cambiarEscrito,
            buscarEscrito = modelo::buscarEscrito,
            cambiarDosis = modelo::cambiarDosis,
            aplicar = modelo::aplicar,
            otroCodigo = modelo::otroCodigo,
            cambiarRegistro = modelo::cambiarRegistro,
            registrar = modelo::registrar,
        ),
        camara = {
            if (conCamara) {
                VistaDeCamara(alLeer = modelo::leido, modifier = Modifier.fillMaxSize())
            } else {
                SinCamara(
                    negada = negada,
                    alPedir = { pedir.launch(Manifest.permission.CAMERA) },
                    alAbrirAjustes = {
                        contexto.startActivity(
                            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", contexto.packageName, null))
                        )
                    },
                )
            }
        },
    )
}

// `camara` va aparte para que las pruebas muestren la pantalla sin abrir la cámara.
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ContenidoVacunas(
    estado: EstadoVacunas,
    hoy: LocalDate,
    acciones: AccionesVacunas,
    camara: @Composable () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Lotes de vacuna") },
                navigationIcon = {
                    IconButton(onClick = acciones.volver) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
            )
        },
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
            when (estado.paso) {
                Paso.ESCANEAR -> Escanear(estado, acciones, camara)
                Paso.BUSCANDO -> Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
                    Text("Buscando ${estado.codigo}…")
                }
                Paso.LOTE -> estado.lote?.let { FichaLote(it, estado, acciones) }
                Paso.REGISTRAR -> RegistroLote(estado, hoy, acciones)
            }
        }
    }
}

@Composable
private fun Escanear(estado: EstadoVacunas, acciones: AccionesVacunas, camara: @Composable () -> Unit) {
    Box(
        Modifier
            .fillMaxWidth()
            .aspectRatio(1f)
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .semantics { contentDescription = "Cámara para leer el código del lote" },
    ) { camara() }
    Text("Apunta la cámara al QR o al código de barras del lote.", style = MaterialTheme.typography.bodyLarge)
    OutlinedTextField(
        value = estado.escrito,
        onValueChange = acciones.cambiarEscrito,
        label = { Text("O escribe el código") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, keyboardType = KeyboardType.Ascii, imeAction = ImeAction.Search),
        keyboardActions = KeyboardActions(onSearch = { acciones.buscarEscrito() }),
        modifier = Modifier.fillMaxWidth(),
    )
    Button(onClick = acciones.buscarEscrito, enabled = estado.escrito.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
        Text("Buscar lote")
    }
    Mensajes(estado)
}

@Composable
private fun SinCamara(negada: Boolean, alPedir: () -> Unit, alAbrirAjustes: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            if (negada) "Sin permiso de cámara. Puedes escribir el código abajo, o darlo en Ajustes."
            else "Para leer el código, la app necesita la cámara.",
            style = MaterialTheme.typography.bodyMedium,
        )
        if (negada) {
            TextButton(onClick = alAbrirAjustes) { Text("Abrir ajustes") }
        } else {
            FilledTonalButton(onClick = alPedir) { Text("Permitir cámara") }
        }
    }
}

@Composable
private fun FichaLote(lote: LoteVacuna, estado: EstadoVacunas, acciones: AccionesVacunas) {
    Text(lote.codigo, style = MaterialTheme.typography.headlineSmall)
    Dato("Enfermedad", lote.nombreEnfermedad ?: "Enfermedad ${lote.enfermedad}")
    lote.fabricante?.let { Dato("Fabricante", it) }
    lote.nombreMunicipio?.let { Dato("Municipio", it) }
    Dato("Dosis", "Quedan ${lote.dosisRestantes} de ${lote.dosisTotales}")
    lote.caducidad?.let { Dato("Caducidad", fecha(it) + if (lote.vencido) " · caducado" else "") }
    when {
        lote.vencido -> Text("Caducado: ya no se le pueden aplicar dosis.", color = MaterialTheme.colorScheme.error)
        lote.dosisRestantes == 0 -> Text("Ya no le quedan dosis.", color = MaterialTheme.colorScheme.error)
        else -> {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                FilledTonalButton(
                    onClick = { acciones.cambiarDosis(estado.dosis - 1) },
                    enabled = estado.dosis > 1 && !estado.aplicando,
                    modifier = Modifier.semantics { contentDescription = "Una dosis menos" },
                ) { Text("−") }
                Text("${estado.dosis}", style = MaterialTheme.typography.headlineSmall)
                FilledTonalButton(
                    onClick = { acciones.cambiarDosis(estado.dosis + 1) },
                    enabled = estado.dosis < estado.maximoDeDosis && !estado.aplicando,
                    modifier = Modifier.semantics { contentDescription = "Una dosis más" },
                ) { Text("+") }
            }
            Button(onClick = acciones.aplicar, enabled = !estado.aplicando, modifier = Modifier.fillMaxWidth()) {
                if (estado.aplicando) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                else Text(if (estado.dosis == 1) "Aplicar 1 dosis" else "Aplicar ${estado.dosis} dosis")
            }
        }
    }
    // Junto al botón que los produjo, antes de "Escanear otro lote".
    Mensajes(estado)
    OutlinedButton(onClick = acciones.otroCodigo, modifier = Modifier.fillMaxWidth()) { Text("Escanear otro lote") }
}

@Composable
private fun RegistroLote(estado: EstadoVacunas, hoy: LocalDate, acciones: AccionesVacunas) {
    val datos = estado.registro
    Text(
        "El lote ${estado.codigo} no está registrado. Regístralo con los datos de la caja.",
        style = MaterialTheme.typography.bodyLarge,
    )
    if (estado.enfermedades.isEmpty()) {
        Text(
            "Falta el catálogo de enfermedades: se descarga al abrir el inicio con conexión.",
            color = MaterialTheme.colorScheme.error,
        )
    }
    Selector(
        etiqueta = "Enfermedad",
        opciones = estado.enfermedades.map { it.id to it.nombre },
        elegido = datos.enfermedad,
        alElegir = { id -> acciones.cambiarRegistro { copy(enfermedad = id) } },
    )
    OutlinedTextField(
        value = datos.dosisTotales,
        onValueChange = { texto -> acciones.cambiarRegistro { copy(dosisTotales = texto.filter(Char::isDigit).take(7)) } },
        label = { Text("Dosis del lote") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Next),
        modifier = Modifier.fillMaxWidth(),
    )
    OutlinedTextField(
        value = datos.fabricante,
        onValueChange = { texto -> acciones.cambiarRegistro { copy(fabricante = texto.take(120)) } },
        label = { Text("Fabricante (opcional)") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    Selector(
        etiqueta = "Municipio (opcional)",
        opciones = estado.municipios.map { it.id to it.nombre },
        elegido = datos.municipio,
        alElegir = { id -> acciones.cambiarRegistro { copy(municipio = id) } },
        alQuitar = { acciones.cambiarRegistro { copy(municipio = null) } },
    )
    CampoFecha(
        "Caducidad (opcional)", datos.caducidad, { dia -> acciones.cambiarRegistro { copy(caducidad = dia) } },
        inicial = hoy, alQuitar = { acciones.cambiarRegistro { copy(caducidad = null) } },
    )
    Mensajes(estado)
    Button(onClick = acciones.registrar, enabled = !estado.registrando, modifier = Modifier.fillMaxWidth()) {
        if (estado.registrando) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
        else Text("Registrar lote")
    }
    OutlinedButton(onClick = acciones.otroCodigo, modifier = Modifier.fillMaxWidth()) { Text("Escanear otro lote") }
}

@Composable
private fun Mensajes(estado: EstadoVacunas) {
    estado.aviso?.let {
        Text(it, color = MaterialTheme.colorScheme.primary, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
    }
    estado.error?.let {
        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
    }
}

@Composable
private fun Dato(etiqueta: String, valor: String) {
    Column {
        Text(etiqueta, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(valor, style = MaterialTheme.typography.bodyLarge)
    }
}

@Preview(showBackground = true)
@Composable
private fun VistaLote() {
    TemaEpidemia {
        ContenidoVacunas(
            estado = EstadoVacunas(
                paso = Paso.LOTE,
                lote = LoteVacuna(
                    id = 5, codigo = "FL3239-2026", fabricante = "Sanofi Pasteur", enfermedad = 1,
                    nombreEnfermedad = "Influenza A", nombreMunicipio = "Monterrey", dosisTotales = 500,
                    dosisUsadas = 12, dosisRestantes = 488, caducidad = "2027-03-31",
                ),
                dosis = 2,
            ),
            hoy = LocalDate.of(2026, 11, 7),
            acciones = AccionesVacunas(),
            camara = {},
        )
    }
}
