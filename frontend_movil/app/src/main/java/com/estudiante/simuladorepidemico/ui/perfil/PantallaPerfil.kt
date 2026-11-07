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
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
        alCerrarSesion = modelo::cerrarSesion,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FichaPerfil(
    estado: EstadoPerfil,
    alVolver: () -> Unit,
    alReintentar: () -> Unit,
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
                HorizontalDivider()
                OutlinedButton(
                    onClick = alCerrarSesion,
                    enabled = !estado.cerrando,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Cerrar sesión")
                }
            }
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
            ),
            alVolver = {},
            alReintentar = {},
            alCerrarSesion = {},
        )
    }
}
