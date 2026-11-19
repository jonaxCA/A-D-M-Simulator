package com.estudiante.simuladorepidemico.ui.navegacion

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.distinctUntilChanged

// Si el teléfono tiene una red con internet. No pide VALIDATED: un celular en un Wi-Fi sin salida
// a internet sí llega a la PC con los servicios.
fun conexion(contexto: Context): Flow<Boolean> = callbackFlow {
    val gestor = contexto.getSystemService(ConnectivityManager::class.java)
    val llamada = object : ConnectivityManager.NetworkCallback() {
        override fun onCapabilitiesChanged(red: Network, capacidades: NetworkCapabilities) {
            trySend(capacidades.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET))
        }

        override fun onLost(red: Network) {
            trySend(false)
        }
    }
    trySend(gestor.getNetworkCapabilities(gestor.activeNetwork)?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true)
    gestor.registerDefaultNetworkCallback(llamada)
    awaitClose { gestor.unregisterNetworkCallback(llamada) }
}.distinctUntilChanged()

// RF-I20: una franja fija arriba de todas las pantallas dice si hay red. Ocupa el lugar de la barra
// de estado, así que las pantallas de abajo ya no la dejan libre.
@Composable
fun ConIndicadorDeConexion(contenido: @Composable () -> Unit) {
    val contexto = LocalContext.current
    val enLinea by remember { conexion(contexto.applicationContext) }.collectAsStateWithLifecycle(initialValue = true)
    Column(Modifier.fillMaxSize()) {
        IndicadorConexion(enLinea)
        Box(Modifier.weight(1f).consumeWindowInsets(WindowInsets.statusBars)) { contenido() }
    }
}

@Composable
fun IndicadorConexion(enLinea: Boolean) {
    val colores = MaterialTheme.colorScheme
    Surface(
        color = if (enLinea) colores.secondaryContainer else colores.errorContainer,
        contentColor = if (enLinea) colores.onSecondaryContainer else colores.onErrorContainer,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            if (enLinea) "Con conexión" else "Sin conexión",
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier
                .windowInsetsPadding(WindowInsets.statusBars)
                .padding(horizontal = 16.dp, vertical = 4.dp)
                .semantics { liveRegion = LiveRegionMode.Polite },
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun VistaIndicador() {
    TemaEpidemia { Column { IndicadorConexion(true); IndicadorConexion(false) } }
}
