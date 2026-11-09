package com.estudiante.simuladorepidemico.ui.casos

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
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
import androidx.core.content.FileProvider
import com.estudiante.simuladorepidemico.local.Enfermedad
import com.estudiante.simuladorepidemico.local.Municipio
import com.estudiante.simuladorepidemico.ui.CampoFecha
import com.estudiante.simuladorepidemico.ui.RESULTADOS_DE_PRUEBA
import com.estudiante.simuladorepidemico.ui.SEVERIDADES
import com.estudiante.simuladorepidemico.ui.SEXOS
import com.estudiante.simuladorepidemico.ui.Selector
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import java.time.LocalDate
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
    val tomarFoto: () -> Unit = {},
    val elegirFoto: () -> Unit = {},
    val quitarFoto: (String) -> Unit = {},
    // El archivo de una foto, para su miniatura; null en las pruebas, que no tienen archivos.
    val archivoDeFoto: (String) -> File? = { null },
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
    // La app de cámara escribe en un archivo nuestro (FileProvider). La ruta sobrevive si Android
    // cierra esta pantalla mientras la cámara está abierta.
    var enCamara by rememberSaveable { mutableStateOf<String?>(null) }
    val tomarFoto = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { tomada ->
        val archivo = enCamara?.let(::File) ?: return@rememberLauncherForActivityResult
        enCamara = null
        if (tomada && archivo.length() > 0) modelo.agregarDeCamara(archivo) else archivo.delete()
    }
    fun abrirCamara() {
        val archivo = modelo.archivoParaLaCamara()
        enCamara = archivo.path
        try {
            tomarFoto.launch(FileProvider.getUriForFile(contexto, "${contexto.packageName}.fotos", archivo))
        } catch (e: ActivityNotFoundException) {
            enCamara = null
            archivo.delete()
            modelo.errorDeFoto("Este teléfono no tiene app de cámara. Elige la foto de la galería.")
        }
    }
    // El manifiesto declara CAMERA (para leer los QR de los lotes), y entonces Android no deja abrir
    // la app de cámara sin ese permiso: se pide antes de la primera foto.
    val pedirCamara = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { dado ->
        if (dado) abrirCamara()
        else modelo.errorDeFoto("Sin permiso de cámara. Elige la foto de la galería, o da el permiso en Ajustes.")
    }
    val elegirFoto = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) {
            modelo.agregarFoto({ contexto.contentResolver.openInputStream(uri) ?: throw IOException("No se pudo abrir la foto.") })
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
            tomarFoto = {
                if (tiene(contexto, Manifest.permission.CAMERA)) abrirCamara() else pedirCamara.launch(Manifest.permission.CAMERA)
            },
            elegirFoto = { elegirFoto.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
            quitarFoto = modelo::quitarFoto,
            archivoDeFoto = modelo::archivoDeFoto,
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
            CampoFecha("Fecha de reporte", estado.fechaReporte, acciones.cambiarFechaReporte, inicial = hoy, hasta = hoy)
            CampoFecha(
                "Inicio de síntomas (opcional)", estado.inicioSintomas, acciones.cambiarInicioSintomas,
                inicial = hoy, hasta = hoy, alQuitar = { acciones.cambiarInicioSintomas(null) },
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
            SeccionFotos(estado, acciones)
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
private fun SeccionFotos(estado: EstadoCaptura, acciones: AccionesCaptura) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Fotos (opcional)", style = MaterialTheme.typography.labelLarge)
        if (estado.fotos.isNotEmpty()) {
            Row(
                modifier = Modifier.horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                estado.fotos.forEachIndexed { i, id ->
                    Miniatura(acciones.archivoDeFoto(id), "Foto ${i + 1}") { acciones.quitarFoto(id) }
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = acciones.tomarFoto, enabled = estado.caben, modifier = Modifier.weight(1f)) {
                Text("Tomar foto")
            }
            OutlinedButton(onClick = acciones.elegirFoto, enabled = estado.caben, modifier = Modifier.weight(1f)) {
                Text("De la galería")
            }
        }
        Text(
            if (estado.agregandoFoto) "Preparando la foto…"
            else "${estado.fotos.size} de $MAXIMO_DE_FOTOS. Se suben cuando el caso ya está en el servidor, " +
                "reducidas y sin la ubicación que guarda la cámara en el archivo.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        estado.errorFoto?.let {
            Text(
                it,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            )
        }
    }
}

@Composable
private fun Miniatura(archivo: File?, descripcion: String, alQuitar: () -> Unit) {
    val imagen by produceState<ImageBitmap?>(null, archivo) {
        value = archivo?.let { withContext(Dispatchers.IO) { miniatura(it, 256)?.asImageBitmap() } }
    }
    Box(Modifier.size(88.dp).clip(RoundedCornerShape(8.dp)).background(MaterialTheme.colorScheme.surfaceVariant)) {
        imagen?.let {
            Image(it, contentDescription = descripcion, contentScale = ContentScale.Crop, modifier = Modifier.matchParentSize())
        }
        IconButton(
            onClick = alQuitar,
            modifier = Modifier.align(Alignment.TopEnd).padding(2.dp).size(32.dp)
                .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.8f), CircleShape),
        ) {
            Icon(Icons.Filled.Close, contentDescription = "Quitar ${descripcion.lowercase()}", modifier = Modifier.size(18.dp))
        }
    }
}

// Para la miniatura basta una versión chica: no se decodifica la foto entera.
private fun miniatura(archivo: File, lado: Int): Bitmap? {
    val limites = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeFile(archivo.path, limites)
    if (limites.outWidth <= 0) return null
    var muestra = 1
    while (maxOf(limites.outWidth, limites.outHeight) / (muestra * 2) >= lado) muestra *= 2
    return BitmapFactory.decodeFile(archivo.path, BitmapFactory.Options().apply { inSampleSize = muestra })
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
