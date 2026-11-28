package com.estudiante.simuladorepidemico.ui.casos

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.estudiante.simuladorepidemico.local.CasoLocal
import com.estudiante.simuladorepidemico.local.ConteoFotos
import com.estudiante.simuladorepidemico.local.EstadoCaso
import com.estudiante.simuladorepidemico.red.CasoRemoto
import com.estudiante.simuladorepidemico.ui.fecha
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia

@Composable
fun PantallaMisCasos(modelo: MisCasosViewModel, alVolver: () -> Unit, alAbrir: (Long) -> Unit) {
    val filas by modelo.filas.collectAsStateWithLifecycle()
    val incompletos by modelo.incompletos.collectAsStateWithLifecycle()
    // Al llegar y al volver de un seguimiento, donde pudo completarse alguno.
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { modelo.cargarIncompletos() }
    ListaCasos(filas, alVolver, modelo::enviarAhora, modelo::descartar, incompletos, alAbrir)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ListaCasos(
    filas: List<FilaCaso>?,
    alVolver: () -> Unit,
    alEnviar: () -> Unit,
    alDescartar: (CasoLocal) -> Unit,
    incompletos: List<CasoRemoto>? = null,
    alAbrir: (Long) -> Unit = {},
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Mis casos") },
                navigationIcon = {
                    IconButton(onClick = alVolver) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
                actions = {
                    if (filas.orEmpty().any { it.caso.estado == EstadoCaso.PENDIENTE }) {
                        TextButton(onClick = alEnviar) { Text("Enviar ahora") }
                    }
                },
            )
        },
    ) { relleno ->
        when {
            filas == null -> Box(Modifier.fillMaxSize().padding(relleno), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            filas.isEmpty() -> Text(
                "Todavía no has capturado casos en este teléfono.",
                modifier = Modifier.padding(relleno).padding(24.dp),
            )
            else -> LazyColumn(contentPadding = PaddingValues(bottom = 16.dp), modifier = Modifier.padding(relleno)) {
                if (!incompletos.isNullOrEmpty()) {
                    item {
                        Text(
                            "Les faltan datos",
                            style = MaterialTheme.typography.titleSmall,
                            modifier = Modifier.padding(start = 24.dp, end = 24.dp, top = 16.dp),
                        )
                    }
                    items(incompletos, key = { "servidor-${it.id}" }) { caso ->
                        Column(
                            modifier = Modifier.fillMaxWidth().clickable { alAbrir(caso.id) }.padding(horizontal = 24.dp, vertical = 12.dp),
                        ) {
                            Text("Caso ${caso.id} · ${caso.nombreEnfermedad ?: ""}", style = MaterialTheme.typography.titleMedium)
                            Text(
                                "Falta: ${caso.faltantes.joinToString()}",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.tertiary,
                            )
                        }
                        HorizontalDivider()
                    }
                    item {
                        Text(
                            "En este teléfono",
                            style = MaterialTheme.typography.titleSmall,
                            modifier = Modifier.padding(start = 24.dp, end = 24.dp, top = 16.dp),
                        )
                    }
                }
                items(filas, key = { it.caso.localUuid }) { fila ->
                    FilaDeCaso(fila, alDescartar, alAbrir)
                    HorizontalDivider()
                }
            }
        }
    }
}

// Un caso que ya llegó al servidor abre su seguimiento: su estado ahí, su historial y la corrección.
@Composable
private fun FilaDeCaso(fila: FilaCaso, alDescartar: (CasoLocal) -> Unit, alAbrir: (Long) -> Unit) {
    val caso = fila.caso
    val enServidor = caso.caseId
    Column(
        modifier = Modifier.fillMaxWidth()
            .then(if (enServidor != null) Modifier.clickable { alAbrir(enServidor) } else Modifier)
            .padding(horizontal = 24.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(fila.enfermedad, style = MaterialTheme.typography.titleMedium)
        Text(
            "${fila.municipio} · ${fecha(caso.fechaReporte)}",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        val (estado, color) = when (caso.estado) {
            EstadoCaso.PENDIENTE ->
                (if (caso.lote == null) "Por enviar" else "Enviando") to MaterialTheme.colorScheme.tertiary
            EstadoCaso.ENVIADO ->
                (caso.caseId?.let { "Recibido · caso $it · ver seguimiento" } ?: "Recibido") to MaterialTheme.colorScheme.primary
            EstadoCaso.RECHAZADO -> "Rechazado" to MaterialTheme.colorScheme.error
        }
        Text(estado, style = MaterialTheme.typography.labelLarge, color = color)
        fila.fotos?.let {
            Text(textoDeFotos(it), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (caso.estado == EstadoCaso.RECHAZADO) {
            caso.error?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            TextButton(onClick = { alDescartar(caso) }) { Text("Descartar") }
        }
    }
}

// "2 fotos subidas", "1 de 2 fotos por subir", "1 foto rechazada"...
fun textoDeFotos(conteo: ConteoFotos): String {
    fun fotos(n: Int) = if (n == 1) "1 foto" else "$n fotos"
    val porSubir = conteo.total - conteo.subidas - conteo.rechazadas
    return listOfNotNull(
        fotos(conteo.subidas).takeIf { conteo.subidas > 0 }?.let { it + if (conteo.subidas == 1) " subida" else " subidas" },
        fotos(porSubir).takeIf { porSubir > 0 }?.let { "$it por subir" },
        fotos(conteo.rechazadas).takeIf { conteo.rechazadas > 0 }?.let { it + if (conteo.rechazadas == 1) " rechazada" else " rechazadas" },
    ).joinToString(" · ")
}

@Preview(showBackground = true)
@Composable
private fun VistaMisCasos() {
    fun caso(id: String, estado: EstadoCaso, caseId: Long? = null, error: String? = null) = CasoLocal(
        localUuid = id, cuenta = 12, enfermedad = 4, municipio = 3, fechaReporte = "2026-11-07",
        capturadoEn = 0, estado = estado, caseId = caseId, error = error,
    )
    TemaEpidemia {
        ListaCasos(
            filas = listOf(
                FilaCaso(caso("a", EstadoCaso.PENDIENTE), "Dengue", "Monterrey"),
                FilaCaso(caso("b", EstadoCaso.ENVIADO, caseId = 41), "Dengue", "Apodaca"),
                FilaCaso(caso("c", EstadoCaso.RECHAZADO, error = "Esa enfermedad no está activa en el catálogo."), "Influenza", "García"),
            ),
            alVolver = {},
            alEnviar = {},
            alDescartar = {},
        )
    }
}
