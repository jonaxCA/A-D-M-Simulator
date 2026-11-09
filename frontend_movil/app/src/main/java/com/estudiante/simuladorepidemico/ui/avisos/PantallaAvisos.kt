package com.estudiante.simuladorepidemico.ui.avisos

import android.Manifest
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import com.estudiante.simuladorepidemico.avisos.Notificador
import com.estudiante.simuladorepidemico.red.Aviso
import com.estudiante.simuladorepidemico.ui.fechaYHora
import com.estudiante.simuladorepidemico.ui.nombreDeAviso
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia

class AccionesAvisos(
    val volver: () -> Unit = {},
    val recargar: () -> Unit = {},
    val abrir: (Aviso) -> Unit = {},
    val marcarTodos: () -> Unit = {},
    val permitirNotificaciones: () -> Unit = {},
)

// Lo que se ofrece para que el teléfono avise solo: pedir el permiso (Android 13+), o ir a Ajustes
// si ya se negó o las apagaron ahí.
enum class Notificaciones { ACTIVAS, PEDIR, AJUSTES }

@Composable
fun PantallaAvisos(modelo: AvisosViewModel, alVolver: () -> Unit) {
    val contexto = LocalContext.current
    val notificador = Notificador(contexto)
    var activas by rememberSaveable { mutableStateOf(notificador.puede()) }
    var negadas by rememberSaveable { mutableStateOf(false) }
    val pedir = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { dado ->
        activas = dado
        negadas = !dado
    }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { activas = notificador.puede() }
    val notificaciones = when {
        activas -> Notificaciones.ACTIVAS
        Build.VERSION.SDK_INT >= 33 && !negadas -> Notificaciones.PEDIR
        else -> Notificaciones.AJUSTES
    }
    ListaDeAvisos(
        estado = modelo.estado,
        notificaciones = notificaciones,
        acciones = AccionesAvisos(
            volver = alVolver,
            recargar = modelo::cargar,
            abrir = modelo::abrir,
            marcarTodos = modelo::marcarTodos,
            permitirNotificaciones = {
                if (notificaciones == Notificaciones.PEDIR) {
                    pedir.launch(Manifest.permission.POST_NOTIFICATIONS)
                } else {
                    contexto.startActivity(
                        Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, contexto.packageName)
                    )
                }
            },
        ),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ListaDeAvisos(estado: EstadoAvisos, notificaciones: Notificaciones, acciones: AccionesAvisos) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Avisos") },
                navigationIcon = {
                    IconButton(onClick = acciones.volver) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
                actions = {
                    if (estado.avisos.any { !it.leido }) {
                        TextButton(onClick = acciones.marcarTodos, enabled = !estado.marcandoTodos) { Text("Marcar leídos") }
                    }
                    IconButton(onClick = acciones.recargar, enabled = !estado.cargando) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Actualizar")
                    }
                },
            )
        },
    ) { relleno ->
        LazyColumn(contentPadding = PaddingValues(bottom = 16.dp), modifier = Modifier.fillMaxSize().padding(relleno)) {
            if (notificaciones != Notificaciones.ACTIVAS) {
                item { AvisoDeNotificaciones(notificaciones, acciones.permitirNotificaciones) }
            }
            estado.error?.let { error ->
                item {
                    Column(Modifier.padding(horizontal = 24.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(error, color = MaterialTheme.colorScheme.error)
                        if (estado.avisos.isEmpty()) Button(onClick = acciones.recargar) { Text("Reintentar") }
                    }
                }
            }
            when {
                estado.cargando && estado.avisos.isEmpty() -> item {
                    Box(Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                }
                estado.avisos.isEmpty() && estado.error == null -> item {
                    Text("No tienes avisos.", modifier = Modifier.padding(24.dp))
                }
                else -> items(estado.avisos, key = { it.id }) { aviso ->
                    FilaDeAviso(aviso, acciones.abrir)
                    HorizontalDivider()
                }
            }
        }
    }
}

@Composable
private fun AvisoDeNotificaciones(notificaciones: Notificaciones, alPermitir: () -> Unit) {
    Card(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                if (notificaciones == Notificaciones.PEDIR) {
                    "Para que el teléfono te avise cuando llegue uno nuevo, permite las notificaciones."
                } else {
                    "Las notificaciones de EPIDEMIA están apagadas: los avisos solo se ven aquí."
                },
                style = MaterialTheme.typography.bodyMedium,
            )
            TextButton(onClick = alPermitir) {
                Text(if (notificaciones == Notificaciones.PEDIR) "Permitir notificaciones" else "Abrir ajustes")
            }
        }
    }
}

@Composable
private fun FilaDeAviso(aviso: Aviso, alAbrir: (Aviso) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(enabled = !aviso.leido, onClickLabel = "Marcar como leído") { alAbrir(aviso) }
            .semantics { stateDescription = if (aviso.leido) "Leído" else "Sin leer" }
            .padding(horizontal = 24.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // El punto marca los que no se han leído.
        Box(Modifier.padding(top = 6.dp).size(10.dp)) {
            if (!aviso.leido) Spacer(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.primary, CircleShape))
        }
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                aviso.titulo,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = if (aviso.leido) FontWeight.Normal else FontWeight.Bold,
            )
            aviso.cuerpo?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
            Text(
                "${nombreDeAviso(aviso.tipo)} · ${fechaYHora(aviso.creadoEn)}",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun VistaAvisos() {
    TemaEpidemia {
        ListaDeAvisos(
            estado = EstadoAvisos(
                cargando = false,
                noLeidos = 1,
                avisos = listOf(
                    Aviso(7, "RUN_FINISHED", "La corrida SIM-00042 terminó", "Brote de influenza en Monterrey, versión 2.", null, "2026-10-20T15:02:00+00:00"),
                    Aviso(6, "SCENARIO_APPROVED", "Versión 2 aprobada", null, "2026-10-20T14:30:00+00:00", "2026-10-20T14:10:00+00:00"),
                ),
            ),
            notificaciones = Notificaciones.PEDIR,
            acciones = AccionesAvisos(),
        )
    }
}
