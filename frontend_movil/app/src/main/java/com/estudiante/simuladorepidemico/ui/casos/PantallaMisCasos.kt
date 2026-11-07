package com.estudiante.simuladorepidemico.ui.casos

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
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.estudiante.simuladorepidemico.local.CasoLocal
import com.estudiante.simuladorepidemico.local.EstadoCaso
import com.estudiante.simuladorepidemico.ui.fecha
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia

@Composable
fun PantallaMisCasos(modelo: MisCasosViewModel, alVolver: () -> Unit) {
    val filas by modelo.filas.collectAsStateWithLifecycle()
    ListaCasos(filas, alVolver, modelo::enviarAhora, modelo::descartar)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ListaCasos(
    filas: List<FilaCaso>?,
    alVolver: () -> Unit,
    alEnviar: () -> Unit,
    alDescartar: (CasoLocal) -> Unit,
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
                items(filas, key = { it.caso.localUuid }) { fila ->
                    FilaDeCaso(fila, alDescartar)
                    HorizontalDivider()
                }
            }
        }
    }
}

@Composable
private fun FilaDeCaso(fila: FilaCaso, alDescartar: (CasoLocal) -> Unit) {
    val caso = fila.caso
    Column(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 12.dp),
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
                (caso.caseId?.let { "Enviado · caso $it" } ?: "Enviado") to MaterialTheme.colorScheme.primary
            EstadoCaso.RECHAZADO -> "Rechazado" to MaterialTheme.colorScheme.error
        }
        Text(estado, style = MaterialTheme.typography.labelLarge, color = color)
        if (caso.estado == EstadoCaso.RECHAZADO) {
            caso.error?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            TextButton(onClick = { alDescartar(caso) }) { Text("Descartar") }
        }
    }
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
