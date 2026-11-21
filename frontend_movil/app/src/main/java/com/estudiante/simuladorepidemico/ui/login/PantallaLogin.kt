package com.estudiante.simuladorepidemico.ui.login

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.estudiante.simuladorepidemico.ui.tema.TemaEpidemia

@Composable
fun PantallaLogin(modelo: LoginViewModel, alQuedarDentro: () -> Unit) {
    val dentro = modelo.estado.dentro
    LaunchedEffect(dentro) {
        if (dentro) alQuedarDentro()
    }
    FormularioLogin(
        estado = modelo.estado,
        alCambiarUsuario = modelo::cambiarUsuario,
        alCambiarPassword = modelo::cambiarPassword,
        alCambiarRespuesta = modelo::cambiarRespuesta,
        alPedirOtroCaptcha = { modelo.otroCaptcha() },
        alEntrar = modelo::entrar,
    )
}

@Composable
fun FormularioLogin(
    estado: EstadoLogin,
    alCambiarUsuario: (String) -> Unit,
    alCambiarPassword: (String) -> Unit,
    alCambiarRespuesta: (String) -> Unit,
    alPedirOtroCaptcha: () -> Unit,
    alEntrar: () -> Unit,
) {
    Scaffold { relleno ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(relleno)
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
        ) {
            Text("EPIDEMIA", style = MaterialTheme.typography.headlineMedium)
            Text(
                "Inicia sesión con tu cuenta.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(
                value = estado.usuario,
                onValueChange = alCambiarUsuario,
                label = { Text("Usuario") },
                singleLine = true,
                enabled = !estado.entrando,
                keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, imeAction = ImeAction.Next),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = estado.password,
                onValueChange = alCambiarPassword,
                label = { Text("Contraseña") },
                singleLine = true,
                enabled = !estado.entrando,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Next),
                modifier = Modifier.fillMaxWidth(),
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = when {
                        estado.cargandoCaptcha -> "Cargando la pregunta…"
                        estado.pregunta != null -> "¿Cuánto es ${estado.pregunta}?"
                        else -> "No se pudo cargar la pregunta."
                    },
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                TextButton(onClick = alPedirOtroCaptcha, enabled = !estado.cargandoCaptcha && !estado.entrando) {
                    Text(if (estado.pregunta == null) "Reintentar" else "Otra pregunta")
                }
            }
            OutlinedTextField(
                value = estado.respuesta,
                onValueChange = alCambiarRespuesta,
                label = { Text("Respuesta") },
                singleLine = true,
                enabled = estado.pregunta != null && !estado.entrando,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { alEntrar() }),
                modifier = Modifier.fillMaxWidth(),
            )
            estado.error?.let {
                Text(
                    text = it,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
                )
            }
            Button(onClick = alEntrar, enabled = estado.listo, modifier = Modifier.fillMaxWidth()) {
                if (estado.entrando) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                } else {
                    Text("Entrar")
                }
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun VistaLogin() {
    TemaEpidemia {
        FormularioLogin(
            estado = EstadoLogin(
                usuario = "capturista1",
                pregunta = "3 + 5",
                error = "El captcha es incorrecto o venció. Pide uno nuevo.",
            ),
            alCambiarUsuario = {},
            alCambiarPassword = {},
            alCambiarRespuesta = {},
            alPedirOtroCaptcha = {},
            alEntrar = {},
        )
    }
}
