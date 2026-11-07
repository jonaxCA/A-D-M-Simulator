package com.estudiante.simuladorepidemico.ui.perfil

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.estudiante.simuladorepidemico.red.Perfil
import com.estudiante.simuladorepidemico.ui.fechaYHora
import com.estudiante.simuladorepidemico.ui.momento
import com.estudiante.simuladorepidemico.ui.nombreDeRol
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia

@Composable
fun PantallaPerfil(modelo: PerfilViewModel, alVolver: () -> Unit) {
    FichaPerfil(
        estado = modelo.estado,
        alVolver = alVolver,
        alReintentar = modelo::cargar,
        alRegistrarTelefono = modelo::registrarTelefono,
        alCerrarSesion = modelo::cerrarSesion,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FichaPerfil(
    estado: EstadoPerfil,
    alVolver: () -> Unit,
    alReintentar: () -> Unit,
    alRegistrarTelefono: () -> Unit,
    alCerrarSesion: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Mi perfil") },
                navigationIcon = {
                    IconButton(onClick = alVolver) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
            )
        },
    ) { relleno ->
        val perfil = estado.perfil
        when {
            estado.cargando -> Box(Modifier.fillMaxSize().padding(relleno), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            perfil == null -> Column(
                modifier = Modifier.fillMaxSize().padding(relleno).padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text(estado.error ?: "No se pudo cargar el perfil.", color = MaterialTheme.colorScheme.error)
                Button(onClick = alReintentar) { Text("Reintentar") }
            }
            else -> Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(relleno)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 24.dp, vertical = 16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Column {
                    Text(perfil.nombre, style = MaterialTheme.typography.headlineSmall)
                    Text(
                        perfil.username,
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                HorizontalDivider()
                Dato("Correo", perfil.email ?: "Sin correo")
                Dato(if (perfil.roles.size > 1) "Roles" else "Rol", perfil.roles.joinToString { nombreDeRol(it) })
                Dato("Último inicio de sesión", fechaYHora(perfil.ultimoAcceso) ?: "Sin registro")
                estado.vence?.let {
                    Dato("La sesión vence", momento(it), "Después hay que volver a iniciar sesión.")
                }
                FilaTelefono(estado, alRegistrarTelefono)
                HorizontalDivider()
                var confirmar by remember { mutableStateOf(false) }
                OutlinedButton(
                    onClick = { if (estado.porEnviar > 0) confirmar = true else alCerrarSesion() },
                    enabled = !estado.cerrando,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Cerrar sesión")
                }
                if (confirmar) {
                    AvisoPendientes(estado.porEnviar, alCerrar = { confirmar = false; alCerrarSesion() }, alCancelar = { confirmar = false })
                }
            }
        }
    }
}

// Los casos no se borran al salir: se quedan en el teléfono y se envían cuando esta cuenta vuelva a
// entrar. Quien entre con otra cuenta no los ve.
@Composable
private fun AvisoPendientes(porEnviar: Int, alCerrar: () -> Unit, alCancelar: () -> Unit) {
    AlertDialog(
        onDismissRequest = alCancelar,
        title = { Text(if (porEnviar == 1) "1 caso sin enviar" else "$porEnviar casos sin enviar") },
        text = {
            Text(
                "Se quedan guardados en este teléfono y se envían cuando vuelvas a entrar con tu cuenta. " +
                    "Si desinstalas la app antes, se pierden."
            )
        },
        confirmButton = { TextButton(onClick = alCerrar) { Text("Cerrar sesión") } },
        dismissButton = { TextButton(onClick = alCancelar) { Text("Cancelar") } },
    )
}

// El número es el id en dispositivos: con él, ADMINISTRADOR sabe cuál revocar si se pierde.
@Composable
private fun FilaTelefono(estado: EstadoPerfil, alRegistrar: () -> Unit) {
    val id = estado.dispositivo
    if (id != null) {
        Dato("Este teléfono", "Registrado como dispositivo $id")
        return
    }
    Column {
        Dato("Este teléfono", "Sin registrar", "Hasta registrarlo, los casos no quedan ligados a este teléfono.")
        estado.errorTelefono?.let {
            Text(
                it,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 4.dp).semantics { liveRegion = LiveRegionMode.Polite },
            )
        }
        TextButton(onClick = alRegistrar, enabled = !estado.registrando) {
            Text(if (estado.registrando) "Registrando…" else "Registrar este teléfono")
        }
    }
}

@Composable
private fun Dato(etiqueta: String, valor: String, nota: String? = null) {
    Column {
        Text(etiqueta, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(valor, style = MaterialTheme.typography.bodyLarge)
        nota?.let {
            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun VistaPerfil() {
    TemaEpidemia {
        FichaPerfil(
            estado = EstadoPerfil(
                cargando = false,
                perfil = Perfil(12, "capturista1", "Carla Captura", "capturista1@ejemplo.mx",
                    "2026-11-06T09:30:00-06:00", listOf("CAPTURISTA")),
                vence = 1_794_000_000,
                dispositivo = 3,
            ),
            alVolver = {},
            alReintentar = {},
            alRegistrarTelefono = {},
            alCerrarSesion = {},
        )
    }
}
