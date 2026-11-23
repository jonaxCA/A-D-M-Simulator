package com.estudiante.simuladorepidemico.ui.casos

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.material3.OutlinedButton
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
import com.estudiante.simuladorepidemico.red.CasoRemoto
import com.estudiante.simuladorepidemico.red.mensajeDeError
import com.estudiante.simuladorepidemico.ui.fecha
import com.estudiante.simuladorepidemico.ui.nombreDeEstado
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

// Los filtros de la lista: el estado de casos, o todos.
val FILTROS_DE_CASOS = listOf("pendiente" to "Por validar", "validado" to "Validados", "descartado" to "Descartados", null to "Todos")

const val CASOS_POR_PAGINA = 20

data class EstadoCasosServidor(
    val filtro: String? = "pendiente",
    val casos: List<CasoRemoto> = emptyList(),
    val total: Int = 0,
    val pagina: Int = 0,
    val paginas: Int = 0,
    val cargando: Boolean = false,
    val error: String? = null,
) {
    val hayMas: Boolean get() = pagina < paginas
}

// D54: los casos que el servidor deja ver a la cuenta (los de su región si tiene alcance, D43), del
// más reciente al más viejo. Para quien revisa en campo: el seguimiento se abre solo para leer;
// validar y descartar es de la web. Necesita red.
class CasosServidorViewModel(private val apis: Apis) : ViewModel() {
    var estado by mutableStateOf(EstadoCasosServidor())
        private set
    private var consulta: Job? = null

    init {
        cargar()
    }

    fun filtrar(filtro: String?) {
        if (filtro == estado.filtro && estado.error == null) return
        estado = EstadoCasosServidor(filtro = filtro)
        cargar()
    }

    // Sin `mas`, la primera página; con él, la siguiente.
    fun cargar(mas: Boolean = false) {
        if (mas && (!estado.hayMas || estado.cargando)) return
        consulta?.cancel()
        val pagina = if (mas) estado.pagina + 1 else 1
        estado = estado.copy(cargando = true, error = null)
        consulta = viewModelScope.launch {
            estado = try {
                val respuesta = apis.casos().lista(estado.filtro, pagina, CASOS_POR_PAGINA)
                estado.copy(
                    cargando = false, total = respuesta.total, pagina = respuesta.pagina, paginas = respuesta.paginas,
                    casos = if (mas) estado.casos + respuesta.casos else respuesta.casos,
                )
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
fun PantallaCasosServidor(modelo: CasosServidorViewModel, alVolver: () -> Unit, alAbrir: (Long) -> Unit) {
    val estado = modelo.estado
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Casos") },
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
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FILTROS_DE_CASOS.forEach { (valor, nombre) ->
                            FilterChip(selected = estado.filtro == valor, onClick = { modelo.filtrar(valor) }, label = { Text(nombre) })
                        }
                    }
                    Text(
                        if (estado.pagina > 0) "${estado.total} casos en tu alcance. Validar y descartar se hace en la web."
                        else "Los casos que tu cuenta puede ver. Necesita conexión.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    estado.error?.let {
                        Text(it, color = MaterialTheme.colorScheme.error)
                        Button(onClick = { modelo.cargar() }) { Text("Reintentar") }
                    }
                    if (estado.pagina > 0 && estado.casos.isEmpty() && !estado.cargando) Text("No hay casos con ese estado.")
                }
                HorizontalDivider()
            }
            items(estado.casos, key = { it.id }) { caso ->
                FilaCaso(caso) { alAbrir(caso.id) }
                HorizontalDivider()
            }
            item {
                Column(Modifier.fillMaxWidth().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    when {
                        estado.cargando -> CircularProgressIndicator()
                        estado.hayMas -> OutlinedButton(onClick = { modelo.cargar(mas = true) }) { Text("Cargar más") }
                    }
                }
            }
        }
    }
}

@Composable
private fun FilaCaso(caso: CasoRemoto, alTocar: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = alTocar).padding(horizontal = 24.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text("Caso ${caso.id} · ${caso.nombreEnfermedad ?: "Enfermedad ${caso.enfermedad}"}", style = MaterialTheme.typography.titleMedium)
            Text(
                "${caso.nombreMunicipio ?: "Municipio ${caso.municipio}"} · ${fecha(caso.fechaReporte)}",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            nombreDeEstado(caso.status),
            style = MaterialTheme.typography.labelLarge,
            color = if (caso.status in setOf("descartado", "duplicado")) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
        )
    }
}
