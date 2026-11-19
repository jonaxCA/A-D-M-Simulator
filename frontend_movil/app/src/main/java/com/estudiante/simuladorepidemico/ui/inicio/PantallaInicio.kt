package com.estudiante.simuladorepidemico.ui.inicio

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia

class AccionesInicio(
    val capturar: () -> Unit = {},
    val verCasos: () -> Unit = {},
    val verLotes: () -> Unit = {},
    val verAvisos: () -> Unit = {},
    val abrirPerfil: () -> Unit = {},
)

@Composable
fun PantallaInicio(
    modelo: InicioViewModel,
    alCapturar: () -> Unit,
    alVerCasos: () -> Unit,
    alVerLotes: () -> Unit,
    alVerAvisos: () -> Unit,
    alAbrirPerfil: () -> Unit,
) {
    val porEnviar by modelo.porEnviar.collectAsStateWithLifecycle()
    val noLeidos by modelo.noLeidos.collectAsStateWithLifecycle()
    // Al llegar y al volver (de los avisos, por ejemplo).
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { modelo.contarAvisos() }
    MenuInicio(porEnviar, noLeidos, AccionesInicio(alCapturar, alVerCasos, alVerLotes, alVerAvisos, alAbrirPerfil))
}

@Composable
fun MenuInicio(porEnviar: Int, noLeidos: Int?, acciones: AccionesInicio) {
    Scaffold { relleno ->
        Column(
            modifier = Modifier.fillMaxSize().padding(relleno).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("EPIDEMIA", style = MaterialTheme.typography.headlineMedium)
            Text("Sesión iniciada.", style = MaterialTheme.typography.bodyLarge)
            Text(
                when (porEnviar) {
                    0 -> "No hay casos por enviar."
                    1 -> "1 caso por enviar."
                    else -> "$porEnviar casos por enviar."
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(onClick = acciones.capturar, modifier = Modifier.fillMaxWidth()) { Text("Capturar caso") }
            OutlinedButton(onClick = acciones.verCasos, modifier = Modifier.fillMaxWidth()) { Text("Mis casos") }
            OutlinedButton(onClick = acciones.verLotes, modifier = Modifier.fillMaxWidth()) { Text("Lotes de vacuna") }
            OutlinedButton(onClick = acciones.verAvisos, modifier = Modifier.fillMaxWidth()) {
                Text(
                    when (noLeidos) {
                        null, 0 -> "Avisos"
                        1 -> "Avisos · 1 sin leer"
                        else -> "Avisos · $noLeidos sin leer"
                    }
                )
            }
            OutlinedButton(onClick = acciones.abrirPerfil, modifier = Modifier.fillMaxWidth()) { Text("Mi perfil") }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun VistaInicio() {
    TemaEpidemia { MenuInicio(porEnviar = 3, noLeidos = 2, acciones = AccionesInicio()) }
}
