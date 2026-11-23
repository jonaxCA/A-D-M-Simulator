package com.estudiante.simuladorepidemico.ui.inicio

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
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
    val consultar: () -> Unit = {},
)

@Composable
fun PantallaInicio(
    modelo: InicioViewModel,
    alCapturar: () -> Unit,
    alVerCasos: () -> Unit,
    alVerLotes: () -> Unit,
    alVerAvisos: () -> Unit,
    alAbrirPerfil: () -> Unit,
    alConsultar: () -> Unit,
) {
    val porEnviar by modelo.porEnviar.collectAsStateWithLifecycle()
    val noLeidos by modelo.noLeidos.collectAsStateWithLifecycle()
    val capturista by modelo.capturista.collectAsStateWithLifecycle()
    val incompletos by modelo.incompletos.collectAsStateWithLifecycle()
    val formularios by modelo.formularios.collectAsStateWithLifecycle()
    // Al llegar y al volver (de los avisos, por ejemplo).
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { modelo.contarAvisos() }
    MenuInicio(
        porEnviar, noLeidos, capturista,
        AccionesInicio(alCapturar, alVerCasos, alVerLotes, alVerAvisos, alAbrirPerfil, alConsultar),
        incompletos, formularios,
    )
}

// Con la forma del tablero de la web: la marca, los indicadores en tarjetas y el menú. Para el
// CAPTURISTA es su panel: lo pendiente de enviar, lo que le falta completar, los formularios que ya
// tiene el teléfono y los avisos.
@Composable
fun MenuInicio(
    porEnviar: Int,
    noLeidos: Int?,
    capturista: Boolean,
    acciones: AccionesInicio,
    incompletos: Int? = null,
    formularios: Int = 0,
) {
    Scaffold { relleno ->
        Column(
            modifier = Modifier.fillMaxSize().padding(relleno).verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Marca()
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (capturista) {
                    Indicador(
                        "CASOS POR ENVIAR", "$porEnviar",
                        if (porEnviar == 0) "Todo enviado" else "Se envían solos con red",
                        Modifier.weight(1f),
                    )
                }
                if (capturista) {
                    Indicador(
                        "DATOS FALTANTES", incompletos?.toString() ?: "—",
                        if (incompletos == null) "Se consultan con red" else "Casos por completar",
                        Modifier.weight(1f), acciones.verCasos,
                    )
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Indicador(
                    "AVISOS SIN LEER", noLeidos?.toString() ?: "—",
                    if (noLeidos == null) "Se consultan con red" else "De tu cuenta",
                    Modifier.weight(1f), acciones.verAvisos,
                )
                if (capturista) {
                    Indicador(
                        "FORMULARIOS", "$formularios",
                        if (formularios == 1) "Enfermedad con campos propios" else "Enfermedades con campos propios",
                        Modifier.weight(1f),
                    )
                }
            }
            if (capturista) {
                Button(onClick = acciones.capturar, modifier = Modifier.fillMaxWidth()) { Text("+  Capturar caso") }
                Opcion("📋", "Mis casos", "Pendientes, enviados y rechazados", acciones.verCasos)
            }
            Opcion("💉", "Lotes de vacuna", "Leer el código y aplicar dosis", acciones.verLotes)
            Opcion("🗺", "Consulta por zona", "Casos por municipio, enfermedad y periodo", acciones.consultar)
            Opcion("🔔", "Avisos", "Casos nuevos, revisiones y corridas", acciones.verAvisos)
            Opcion("👤", "Mi perfil", "Cuenta, teléfono y cerrar sesión", acciones.abrirPerfil)
        }
    }
}

@Composable
private fun Marca() {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Box(
            Modifier.size(36.dp).background(MaterialTheme.colorScheme.primary, RoundedCornerShape(9.dp)),
            contentAlignment = Alignment.Center,
        ) {
            Text("✚", color = Color.White, style = MaterialTheme.typography.titleMedium)
        }
        Column {
            Text("EPIDEMIA", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(
                "Simulador de respuesta a epidemias",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun Tarjeta(modifier: Modifier = Modifier, alTocar: (() -> Unit)? = null, contenido: @Composable () -> Unit) {
    val colores = CardDefaults.outlinedCardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest)
    val borde = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
    if (alTocar == null) {
        OutlinedCard(modifier, colors = colores, border = borde) { contenido() }
    } else {
        OutlinedCard(alTocar, modifier, colors = colores, border = borde) { contenido() }
    }
}

@Composable
private fun Indicador(etiqueta: String, valor: String, nota: String, modifier: Modifier, alTocar: (() -> Unit)? = null) {
    Tarjeta(modifier, alTocar) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                etiqueta,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontWeight = FontWeight.SemiBold,
            )
            Text(valor, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text(nota, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun Opcion(icono: String, titulo: String, descripcion: String, alTocar: () -> Unit) {
    Tarjeta(Modifier.fillMaxWidth(), alTocar) {
        Row(
            Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text(icono, style = MaterialTheme.typography.titleLarge)
            Column(Modifier.weight(1f)) {
                Text(titulo, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(descripcion, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text("›", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun VistaInicio() {
    TemaEpidemia { MenuInicio(porEnviar = 3, noLeidos = 2, capturista = true, acciones = AccionesInicio()) }
}
