package com.estudiante.simuladorepidemico.ui.navegacion

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect

// Android 17 (API 37) bloquea las direcciones de la red local sin este permiso, y ahí corren los
// servicios: la PC con el compose, o 10.0.2.2 desde el emulador.
private const val RED_LOCAL = "android.permission.ACCESS_LOCAL_NETWORK"

private fun tienePermiso(contexto: Context) = Build.VERSION.SDK_INT < 37 ||
    ContextCompat.checkSelfPermission(contexto, RED_LOCAL) == PackageManager.PERMISSION_GRANTED

@Composable
fun ConPermisoRedLocal(contenido: @Composable () -> Unit) {
    val contexto = LocalContext.current
    var concedido by remember { mutableStateOf(tienePermiso(contexto)) }
    var negado by remember { mutableStateOf(false) }
    val pedir = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        concedido = it
        negado = !it
    }
    // Al volver de Ajustes.
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { concedido = tienePermiso(contexto) }

    if (concedido) {
        contenido()
        return
    }
    Scaffold { relleno ->
        Column(
            modifier = Modifier.fillMaxSize().padding(relleno).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
        ) {
            Text("EPIDEMIA", style = MaterialTheme.typography.headlineMedium)
            Text(
                "Los servicios corren en una computadora de tu red local. Para conectarse a ellos, " +
                    "la app necesita el permiso de dispositivos de la red local.",
                style = MaterialTheme.typography.bodyLarge,
            )
            if (negado) {
                Text(
                    "Si ya no aparece la pregunta, actívalo en Ajustes, en los permisos de la app.",
                    color = MaterialTheme.colorScheme.error,
                )
            }
            Button(onClick = { pedir.launch(RED_LOCAL) }, modifier = Modifier.fillMaxWidth()) {
                Text("Permitir")
            }
            if (negado) {
                OutlinedButton(
                    onClick = {
                        contexto.startActivity(
                            Intent(
                                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                Uri.fromParts("package", contexto.packageName, null),
                            )
                        )
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Abrir ajustes")
                }
            }
        }
    }
}
