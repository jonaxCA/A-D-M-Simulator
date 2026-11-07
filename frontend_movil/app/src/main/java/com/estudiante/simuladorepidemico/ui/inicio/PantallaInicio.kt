package com.estudiante.simuladorepidemico.ui.inicio

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

// Provisional: las pantallas de captura van a colgar de aquí.
@Composable
fun PantallaInicio(alAbrirPerfil: () -> Unit) {
    Scaffold { relleno ->
        Column(
            modifier = Modifier.fillMaxSize().padding(relleno).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("EPIDEMIA", style = MaterialTheme.typography.headlineMedium)
            Text("Sesión iniciada.", style = MaterialTheme.typography.bodyLarge)
            Button(onClick = alAbrirPerfil) {
                Text("Mi perfil")
            }
        }
    }
}
