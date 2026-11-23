package com.estudiante.simuladorepidemico.ui.consulta

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
import com.estudiante.simuladorepidemico.local.CatalogoDao
import com.estudiante.simuladorepidemico.local.Enfermedad
import com.estudiante.simuladorepidemico.red.Apis
import com.estudiante.simuladorepidemico.red.Zona
import com.estudiante.simuladorepidemico.red.mensajeDeError
import com.estudiante.simuladorepidemico.ui.Selector
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import java.util.Locale

// Los periodos que acepta zonas (PERIODOS_TABLA).
val PERIODOS = listOf(7, 30, 90)

data class EstadoConsulta(
    val enfermedades: List<Enfermedad> = emptyList(),
    val enfermedad: Long? = null,
    val dias: Int = 30,
    val zonas: List<Zona>? = null,
    val cargando: Boolean = false,
    val error: String? = null,
)

// Casos e incidencia por municipio, con el alcance que el servidor le da a la cuenta. Necesita red.
class ConsultaViewModel(private val apis: Apis, catalogo: CatalogoDao) : ViewModel() {
    var estado by mutableStateOf(EstadoConsulta())
        private set
    private var consulta: Job? = null

    init {
        viewModelScope.launch { catalogo.enfermedades().collect { estado = estado.copy(enfermedades = it) } }
        consultar()
    }

    fun elegirEnfermedad(id: Long?) {
        estado = estado.copy(enfermedad = id)
        consultar()
    }

    fun elegirPeriodo(dias: Int) {
        estado = estado.copy(dias = dias)
        consultar()
    }

    fun consultar() {
        consulta?.cancel()
        estado = estado.copy(cargando = true, error = null)
        consulta = viewModelScope.launch {
            estado = try {
                estado.copy(cargando = false, zonas = apis.zonas().zonas(estado.enfermedad, estado.dias).zonas)
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
fun PantallaConsulta(modelo: ConsultaViewModel, alVolver: () -> Unit) {
    val estado = modelo.estado
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Consulta por zona") },
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
                    Selector(
                        "Enfermedad", estado.enfermedades.map { it.id to it.nombre }, estado.enfermedad,
                        alElegir = { modelo.elegirEnfermedad(it) }, alQuitar = { modelo.elegirEnfermedad(null) },
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        PERIODOS.forEach { dias ->
                            FilterChip(
                                selected = estado.dias == dias,
                                onClick = { modelo.elegirPeriodo(dias) },
                                label = { Text("$dias días") },
                            )
                        }
                    }
                    Text(
                        "Casos e incidencia por 100 mil habitantes en el periodo. Sin enfermedad, todas.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    when {
                        estado.cargando -> CircularProgressIndicator(Modifier.align(Alignment.CenterHorizontally))
                        estado.error != null -> Text(estado.error, color = MaterialTheme.colorScheme.error)
                        estado.zonas?.isEmpty() == true -> Text("No hay casos en ese periodo.")
                    }
                }
                HorizontalDivider()
            }
            items(estado.zonas.orEmpty(), key = { it.id }) { zona ->
                FilaZona(zona)
                HorizontalDivider()
            }
        }
    }
}

private val NIVELES = mapOf("critico" to "Crítico", "alerta" to "Alerta", "estable" to "Estable")

@Composable
private fun FilaZona(zona: Zona) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(zona.zona, style = MaterialTheme.typography.titleMedium)
            Text(
                "${zona.casos} casos · %.1f por 100 mil · ${zona.graves} graves".format(Locale.ROOT, zona.incidencia),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            NIVELES[zona.estado] ?: zona.estado,
            style = MaterialTheme.typography.labelLarge,
            color = when (zona.estado) {
                "critico" -> MaterialTheme.colorScheme.error
                "alerta" -> MaterialTheme.colorScheme.tertiary
                else -> MaterialTheme.colorScheme.secondary
            },
        )
    }
}
