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
    val verCasosServidor: () -> Unit = {},
    val verCampanas: () -> Unit = {},
)

// Los números del panel; null es "se consultan con red".
data class Panel(
    val porEnviar: Int = 0,
    val noLeidos: Int? = null,
    val incompletos: Int? = null,
    val formularios: Int = 0,
    val porValidar: Int? = null,
    val campanasActivas: Int? = null,
)

@Composable
fun PantallaInicio(
    modelo: InicioViewModel,
    alCapturar: () -> Unit,
    alVerCasos: () -> Unit,
    alVerLotes: (registra: Boolean) -> Unit,
    alVerAvisos: () -> Unit,
    alAbrirPerfil: () -> Unit,
    alConsultar: () -> Unit,
    alVerCasosServidor: () -> Unit,
    alVerCampanas: () -> Unit,
) {
    val porEnviar by modelo.porEnviar.collectAsStateWithLifecycle()
    val noLeidos by modelo.noLeidos.collectAsStateWithLifecycle()
    val menu by modelo.menu.collectAsStateWithLifecycle()
    val incompletos by modelo.incompletos.collectAsStateWithLifecycle()
    val formularios by modelo.formularios.collectAsStateWithLifecycle()
    val porValidar by modelo.porValidar.collectAsStateWithLifecycle()
    val campanasActivas by modelo.campanasActivas.collectAsStateWithLifecycle()
    // Al llegar y al volver (de los avisos, por ejemplo).
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { modelo.contarAvisos() }
    MenuInicio(
        menu, Panel(porEnviar, noLeidos, incompletos, formularios, porValidar, campanasActivas),
        AccionesInicio(
            alCapturar, alVerCasos, { alVerLotes(menu.lotesRegistra) }, alVerAvisos, alAbrirPerfil, alConsultar,
            alVerCasosServidor, alVerCampanas,
        ),
    )
}

// Con la forma del tablero de la web: la marca, los indicadores en tarjetas y el menú de su perfil
// (D56). Para el CAPTURISTA es su panel: lo pendiente de enviar, lo que le falta completar, los
// formularios que ya tiene el teléfono y los avisos. Para quien revisa: los casos por validar de su
// alcance, las campañas activas y los avisos.
@Composable
fun MenuInicio(menu: Menu, panel: Panel, acciones: AccionesInicio) {
    Scaffold { relleno ->
        Column(
            modifier = Modifier.fillMaxSize().padding(relleno).verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Marca()
            if (menu.captura) {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Indicador(
                        "CASOS POR ENVIAR", "${panel.porEnviar}",
                        if (panel.porEnviar == 0) "Todo enviado" else "Se envían solos con red",
                        Modifier.weight(1f),
                    )
                    Indicador(
                        "DATOS FALTANTES", panel.incompletos?.toString() ?: "—",
                        if (panel.incompletos == null) "Se consultan con red" else "Casos por completar",
                        Modifier.weight(1f), acciones.verCasos,
                    )
                }
            }
            if (menu.revisa) {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Indicador(
                        "POR VALIDAR", panel.porValidar?.toString() ?: "—",
                        if (panel.porValidar == null) "Se consultan con red" else "Casos de tu alcance",
                        Modifier.weight(1f), acciones.verCasosServidor,
                    )
                    Indicador(
                        "CAMPAÑAS ACTIVAS", panel.campanasActivas?.toString() ?: "—",
                        if (panel.campanasActivas == null) "Se consultan con red" else "En curso hoy",
                        Modifier.weight(1f), acciones.verCampanas,
                    )
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Indicador(
                    "AVISOS SIN LEER", panel.noLeidos?.toString() ?: "—",
                    if (panel.noLeidos == null) "Se consultan con red" else "De tu cuenta",
                    Modifier.weight(1f), acciones.verAvisos,
                )
                if (menu.captura) {
                    Indicador(
                        "FORMULARIOS", "${panel.formularios}",
                        if (panel.formularios == 1) "Enfermedad con campos propios" else "Enfermedades con campos propios",
                        Modifier.weight(1f),
                    )
                }
            }
            if (menu.captura) {
                Button(onClick = acciones.capturar, modifier = Modifier.fillMaxWidth()) { Text("+  Capturar caso") }
            }
            if (Opcion.MIS_CASOS in menu.opciones) {
                Entrada("📋", "Mis casos", "Pendientes, enviados y rechazados", acciones.verCasos)
            }
            if (Opcion.CASOS_SERVIDOR in menu.opciones) {
                Entrada("🗂", "Casos", "Por validar, validados y descartados, con su seguimiento", acciones.verCasosServidor)
            }
            if (Opcion.CAMPANAS in menu.opciones) {
                Entrada("📣", "Campañas", "Activas y programadas, por enfermedad y municipio", acciones.verCampanas)
            }
            if (Opcion.LOTES in menu.opciones) {
                Entrada(
                    "💉", "Lotes de vacuna",
                    if (menu.lotesRegistra) "Leer el código y aplicar dosis" else "Consultar un lote por su código",
                    acciones.verLotes,
                )
            }
            if (Opcion.CONSULTA in menu.opciones) {
                Entrada("🗺", "Consulta por zona", "Casos por municipio, enfermedad y periodo", acciones.consultar)
            }
            Entrada("🔔", "Avisos", "Casos nuevos, revisiones y corridas", acciones.verAvisos)
            Entrada("👤", "Mi perfil", "Cuenta, teléfono y cerrar sesión", acciones.abrirPerfil)
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
private fun Entrada(icono: String, titulo: String, descripcion: String, alTocar: () -> Unit) {
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
    TemaEpidemia { MenuInicio(menuDe(setOf("CAPTURISTA")), Panel(porEnviar = 3, noLeidos = 2), AccionesInicio()) }
}
