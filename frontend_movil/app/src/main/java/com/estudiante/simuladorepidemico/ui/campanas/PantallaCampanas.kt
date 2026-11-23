package com.estudiante.simuladorepidemico.ui.campanas

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.estudiante.simuladorepidemico.red.Apis
import com.estudiante.simuladorepidemico.red.Campana
import com.estudiante.simuladorepidemico.red.mensajeDeError
import com.estudiante.simuladorepidemico.ui.fecha
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.util.Locale

// Los filtros: las que importan en campo primero.
val FILTROS_DE_CAMPANAS = listOf("activa" to "Activas", "programada" to "Programadas", null to "Todas")

val ESTADOS_DE_CAMPANA = mapOf(
    "activa" to "Activa", "programada" to "Programada", "terminada" to "Terminada", "cancelada" to "Cancelada",
)

data class EstadoCampanas(
    val filtro: String? = "activa",
    val campanas: List<Campana>? = null,
    val cargando: Boolean = false,
    val error: String? = null,
)

// D49 y D54: las campañas de salud que dio de alta el EPIDEMIOLOGO, para consultarlas en campo.
// Crearlas, editarlas y cancelarlas es de la web. Necesita red.
class CampanasViewModel(private val apis: Apis) : ViewModel() {
    var estado by mutableStateOf(EstadoCampanas())
        private set
    private var consulta: Job? = null

    init {
        consultar()
    }

    fun filtrar(filtro: String?) {
        estado = estado.copy(filtro = filtro)
        consultar()
    }

    fun consultar() {
        consulta?.cancel()
        estado = estado.copy(cargando = true, error = null)
        consulta = viewModelScope.launch {
            estado = try {
                estado.copy(cargando = false, campanas = apis.vacunas().campanas(estado.filtro).campanas)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                estado.copy(cargando = false, error = mensajeDeError(e))
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PantallaCampanas(modelo: CampanasViewModel, alVolver: () -> Unit) {
    val estado = modelo.estado
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Campañas") },
                navigationIcon = {
                    IconButton(onClick = alVolver) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
            )
        },
    ) { relleno ->
        LazyColumn(modifier = Modifier.fillMaxSize().padding(relleno)) {
            item {
                Column(Modifier.padding(horizontal = 24.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FILTROS_DE_CAMPANAS.forEach { (valor, nombre) ->
                            FilterChip(selected = estado.filtro == valor, onClick = { modelo.filtrar(valor) }, label = { Text(nombre) })
                        }
                    }
                    when {
                        estado.cargando -> CircularProgressIndicator(Modifier.align(Alignment.CenterHorizontally))
                        estado.error != null -> {
                            Text(estado.error, color = MaterialTheme.colorScheme.error)
                            Button(onClick = modelo::consultar) { Text("Reintentar") }
                        }
                        estado.campanas?.isEmpty() == true -> Text("No hay campañas con ese estado.")
                    }
                }
                HorizontalDivider()
            }
            items(estado.campanas.orEmpty(), key = { it.id }) { campana ->
                FichaCampana(campana)
                HorizontalDivider()
            }
        }
    }
}

@Composable
private fun FichaCampana(campana: Campana) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(campana.nombre, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            Text(
                ESTADOS_DE_CAMPANA[campana.status] ?: campana.status,
                style = MaterialTheme.typography.labelLarge,
                color = if (campana.status == "cancelada") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
            )
        }
        Text(
            listOfNotNull(campana.enfermedad, campana.municipio).joinToString(" · "),
            style = MaterialTheme.typography.bodyMedium,
        )
        Text(
            "Del ${fecha(campana.inicio)} al ${fecha(campana.fin)}" +
                (campana.poblacionObjetivo?.let { " · ${poblacion(it)} personas objetivo" } ?: ""),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        campana.descripcion?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        campana.motivoCancelacion?.let {
            Text("Cancelada: $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
    }
}

fun poblacion(n: Long): String = NumberFormat.getIntegerInstance(Locale.forLanguageTag("es-MX")).format(n)
