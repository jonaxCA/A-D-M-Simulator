package com.estudiante.simuladorepidemico.ui.casos

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import com.estudiante.simuladorepidemico.red.CambioDeCaso
import com.estudiante.simuladorepidemico.red.CasoRemoto
import com.estudiante.simuladorepidemico.ui.CampoFecha
import com.estudiante.simuladorepidemico.ui.RESULTADOS_DE_PRUEBA
import com.estudiante.simuladorepidemico.ui.SEVERIDADES
import com.estudiante.simuladorepidemico.ui.SEXOS
import com.estudiante.simuladorepidemico.ui.Selector
import com.estudiante.simuladorepidemico.ui.fecha
import com.estudiante.simuladorepidemico.ui.fechaYHora
import com.estudiante.simuladorepidemico.ui.nombreDeEstado
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import java.time.LocalDate
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PantallaSeguimiento(modelo: SeguimientoViewModel, alVolver: () -> Unit) {
    val estado = modelo.estado
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(estado.caso?.let { "Caso ${it.id}" } ?: "Seguimiento") },
                navigationIcon = {
                    IconButton(onClick = alVolver) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
            )
        },
    ) { relleno ->
        val caso = estado.caso
        if (caso == null) {
            Box(Modifier.fillMaxSize().padding(relleno).padding(24.dp), contentAlignment = Alignment.Center) {
                if (estado.cargando) CircularProgressIndicator()
                else Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(estado.error ?: "No se pudo cargar el caso.", color = MaterialTheme.colorScheme.error)
                    Button(onClick = { modelo.cargar() }) { Text("Reintentar") }
                }
            }
            return@Scaffold
        }
        Column(
            modifier = Modifier.fillMaxSize().padding(relleno).imePadding().verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(caso.nombreEnfermedad ?: "Enfermedad ${caso.enfermedad}", style = MaterialTheme.typography.titleLarge)
            Text(
                "${nombreDeEstado(caso.status)} · versión ${caso.version}",
                style = MaterialTheme.typography.labelLarge,
                color = if (caso.status in setOf("descartado", "duplicado")) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
            )
            caso.motivo?.let { Text("Motivo: $it", style = MaterialTheme.typography.bodyMedium) }
            estado.conflicto?.let {
                Text(
                    "$it Esto es lo que tiene el servidor ahora.",
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
                )
            }
            val correccion = estado.correccion
            if (correccion == null) {
                DatosDelCaso(caso)
                if (estado.puedeCorregir) {
                    OutlinedButton(onClick = modelo::corregir, modifier = Modifier.fillMaxWidth()) { Text("Corregir datos") }
                } else if (caso.status == "pendiente") {
                    Text(
                        "Solo quien lo capturó lo corrige mientras está pendiente.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                FormularioCorreccion(caso, correccion, estado.guardando, modelo)
            }
            estado.error?.takeIf { estado.caso != null }?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            HorizontalDivider()
            SeccionFotos(estado, modelo)
            HorizontalDivider()
            Text("Historial", style = MaterialTheme.typography.titleMedium)
            if (estado.historial.isEmpty()) {
                Text("Sin cambios desde que llegó.", style = MaterialTheme.typography.bodyMedium)
            }
            estado.historial.forEach { CambioEnHistorial(it) }
        }
    }
}

// Las fotos que el caso tiene en evidencias (D30). Se bajan una a la vez, al pedirlas: en el
// teléfono no se guardan, igual que las que ya se subieron.
@Composable
private fun SeccionFotos(estado: EstadoSeguimiento, modelo: SeguimientoViewModel) {
    Text("Fotos", style = MaterialTheme.typography.titleMedium)
    if (estado.fotosSinAcceso) {
        Text("Tu perfil no ve las fotos de los casos.", style = MaterialTheme.typography.bodyMedium)
    } else if (estado.fotos.isEmpty() && estado.errorFotos == null) {
        Text("El caso no tiene fotos en el servidor.", style = MaterialTheme.typography.bodyMedium)
    }
    estado.fotos.forEachIndexed { indice, foto ->
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(if (foto.tipo.startsWith("image/")) "Foto ${indice + 1}" else "Documento ${indice + 1}")
                Text(
                    listOfNotNull(tamanoLegible(foto.tamano), foto.subida?.let { fechaYHora(it) ?: it }).joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (foto.tipo.startsWith("image/")) {
                OutlinedButton(onClick = { modelo.verFoto(foto) }, enabled = estado.bajandoFoto == null) {
                    Text(if (estado.bajandoFoto == foto.id) "Bajando…" else "Ver")
                }
            } else {
                Text("Se abre en la web", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
    estado.errorFotos?.let {
        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
    }
    estado.fotoAbierta?.let { VisorDeFoto(it, alCerrar = modelo::cerrarFoto) }
}

fun tamanoLegible(bytes: Long): String? = when {
    bytes <= 0 -> null
    bytes < 1_048_576 -> "%d KB".format(Locale.ROOT, (bytes + 1023) / 1024)
    else -> "%.1f MB".format(Locale.ROOT, bytes / 1_048_576.0)
}

@Composable
private fun VisorDeFoto(foto: FotoAbierta, alCerrar: () -> Unit) {
    val imagen = remember(foto.id) { decodificar(foto.bytes) }
    Dialog(onDismissRequest = alCerrar) {
        Surface(shape = MaterialTheme.shapes.large) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (imagen != null) {
                    Image(imagen, contentDescription = "Foto del caso", modifier = Modifier.fillMaxWidth(), contentScale = ContentScale.Fit)
                } else {
                    Text("El archivo no es una imagen que el teléfono pueda mostrar.", color = MaterialTheme.colorScheme.error)
                }
                Button(onClick = alCerrar, modifier = Modifier.fillMaxWidth()) { Text("Cerrar") }
            }
        }
    }
}

// Reducida a no más de 2048 px por lado: una foto de cámara entera no cabe en la memoria de un
// teléfono modesto.
private fun decodificar(bytes: ByteArray): ImageBitmap? {
    val medidas = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, medidas)
    if (medidas.outWidth <= 0 || medidas.outHeight <= 0) return null
    var muestra = 1
    while (maxOf(medidas.outWidth, medidas.outHeight) / muestra > 2048) muestra *= 2
    val opciones = BitmapFactory.Options().apply { inSampleSize = muestra }
    return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opciones)?.asImageBitmap()
}

@Composable
private fun DatosDelCaso(caso: CasoRemoto) {
    fun nombre(lista: List<Pair<String, String>>, valor: String?) = lista.firstOrNull { it.first == valor }?.second ?: "Sin dato"
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("${caso.nombreMunicipio ?: "Municipio ${caso.municipio}"} · reportado el ${fecha(caso.fechaReporte)}")
        Text("Inicio de síntomas: ${caso.inicioSintomas?.let { fecha(it) } ?: "Sin dato"}")
        Text("Edad: ${caso.age?.let { "$it años" } ?: "Sin dato"} · Sexo: ${nombre(SEXOS, caso.sex)}")
        Text("Resultado: ${nombre(RESULTADOS_DE_PRUEBA, caso.resultadoPrueba)} · Gravedad: ${nombre(SEVERIDADES, caso.severity)}")
        Text(
            "Ubicación: " + if (caso.latitude != null && caso.longitude != null) "%.6f, %.6f".format(Locale.ROOT, caso.latitude, caso.longitude) else "Sin dato",
        )
    }
}

@Composable
private fun FormularioCorreccion(caso: CasoRemoto, correccion: Correccion, guardando: Boolean, modelo: SeguimientoViewModel) {
    OutlinedTextField(
        value = correccion.edad,
        onValueChange = { texto -> modelo.cambiar { copy(edad = texto.filter(Char::isDigit).take(3)) } },
        label = { Text("Edad") },
        suffix = { Text("años") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        modifier = Modifier.fillMaxWidth(),
    )
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        SEXOS.forEach { (valor, nombre) ->
            FilterChip(
                selected = correccion.sexo == valor,
                onClick = { modelo.cambiar { copy(sexo = valor.takeIf { it != sexo }) } },
                label = { Text(nombre) },
            )
        }
    }
    val hasta = LocalDate.parse(caso.fechaReporte)
    CampoFecha(
        "Inicio de síntomas", correccion.inicioSintomas, { dia -> modelo.cambiar { copy(inicioSintomas = dia) } },
        inicial = hasta, hasta = hasta, alQuitar = { modelo.cambiar { copy(inicioSintomas = null) } },
    )
    Selector(
        "Resultado de prueba", RESULTADOS_DE_PRUEBA, correccion.resultadoPrueba,
        alElegir = { valor -> modelo.cambiar { copy(resultadoPrueba = valor) } },
        alQuitar = { modelo.cambiar { copy(resultadoPrueba = null) } },
    )
    Selector(
        "Gravedad", SEVERIDADES, correccion.severidad,
        alElegir = { valor -> modelo.cambiar { copy(severidad = valor) } },
        alQuitar = { modelo.cambiar { copy(severidad = null) } },
    )
    OutlinedTextField(
        value = correccion.motivo,
        onValueChange = { texto -> modelo.cambiar { copy(motivo = texto.take(500)) } },
        label = { Text("Motivo (opcional)") },
        modifier = Modifier.fillMaxWidth(),
    )
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(onClick = modelo::cancelar, modifier = Modifier.weight(1f)) { Text("Cancelar") }
        Button(onClick = modelo::guardar, enabled = !guardando, modifier = Modifier.weight(1f)) {
            Text(if (guardando) "Guardando…" else "Guardar")
        }
    }
    Text("Necesita conexión: el servidor revisa que nadie más lo haya cambiado.", style = MaterialTheme.typography.bodySmall)
}

private val NOMBRES_DE_CAMPO = mapOf(
    "age" to "edad", "sex" to "sexo", "onset_date" to "inicio de síntomas", "report_date" to "fecha de reporte",
    "test_result" to "resultado", "severity" to "gravedad", "status" to "estado", "region_id" to "municipio",
    "disease_id" to "enfermedad", "latitude" to "latitud", "longitude" to "longitud", "form_answers" to "formulario",
)

// "edad: 33 → 34".
fun textoDeCambios(cambios: JsonObject): String = cambios.entries.joinToString("; ") { (campo, valor) ->
    fun texto(clave: String) = when (val v = runCatching { valor.jsonObject[clave] }.getOrNull()) {
        null, JsonNull -> "sin dato"
        is JsonPrimitive -> if (campo == "status") nombreDeEstado(v.content) else v.content
        else -> v.toString()
    }
    "${NOMBRES_DE_CAMPO[campo] ?: campo}: ${texto("antes")} → ${texto("despues")}"
}

@Composable
private fun CambioEnHistorial(cambio: CambioDeCaso) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(
            "Versión ${cambio.version} · ${fechaYHora(cambio.cuando) ?: cambio.cuando}",
            style = MaterialTheme.typography.labelLarge,
        )
        Text(textoDeCambios(cambio.cambios), style = MaterialTheme.typography.bodyMedium)
        cambio.reason?.let {
            Text("Motivo: $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
