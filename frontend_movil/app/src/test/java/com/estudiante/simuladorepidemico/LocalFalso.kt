package com.estudiante.simuladorepidemico

import com.estudiante.simuladorepidemico.local.CasoLocal
import com.estudiante.simuladorepidemico.local.CasosDao
import com.estudiante.simuladorepidemico.local.CatalogoDao
import com.estudiante.simuladorepidemico.local.ConteoFotos
import com.estudiante.simuladorepidemico.local.Enfermedad
import com.estudiante.simuladorepidemico.local.EstadoCaso
import com.estudiante.simuladorepidemico.local.EstadoFoto
import com.estudiante.simuladorepidemico.local.FotoLocal
import com.estudiante.simuladorepidemico.local.FotoPorSubir
import com.estudiante.simuladorepidemico.local.Fotos
import com.estudiante.simuladorepidemico.local.Municipio
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import java.nio.file.Files

// Room necesita Android; aquí las consultas se imitan en memoria. siguienteLote y aplicar son los
// de CasosDao. Las consultas de verdad se prueban en el emulador (CasosDaoTest).
class CasosDaoFalso : CasosDao() {
    val filas = MutableStateFlow<List<CasoLocal>>(emptyList())
    private val enOrden = compareBy<CasoLocal>({ it.capturadoEn }, { it.localUuid })

    fun caso(localUuid: String) = filas.value.single { it.localUuid == localUuid }

    private fun cambiar(localUuid: String, cambio: (CasoLocal) -> CasoLocal) =
        filas.update { lista -> lista.map { if (it.localUuid == localUuid) cambio(it) else it } }

    override suspend fun insertar(caso: CasoLocal) {
        check(filas.value.none { it.localUuid == caso.localUuid }) { "localUuid repetido" }
        filas.update { it + caso }
    }

    override fun deLaCuenta(cuenta: Long): Flow<List<CasoLocal>> =
        filas.map { lista -> lista.filter { it.cuenta == cuenta }.sortedWith(enOrden.reversed()) }

    override fun porEnviar(cuenta: Long): Flow<Int> =
        filas.map { lista -> lista.count { it.cuenta == cuenta && it.estado == EstadoCaso.PENDIENTE } }

    override suspend fun loteAbierto(cuenta: Long): String? =
        filas.value.firstOrNull { it.cuenta == cuenta && it.lote != null }?.lote

    override suspend fun asignarLote(cuenta: Long, lote: String, maximo: Int): Int {
        val elegidos = filas.value
            .filter { it.cuenta == cuenta && it.estado == EstadoCaso.PENDIENTE && it.lote == null }
            .sortedWith(enOrden).take(maximo).map { it.localUuid }.toSet()
        filas.update { lista -> lista.map { if (it.localUuid in elegidos) it.copy(lote = lote) else it } }
        return elegidos.size
    }

    override suspend fun delLote(lote: String): List<CasoLocal> =
        filas.value.filter { it.lote == lote }.sortedWith(enOrden)

    override suspend fun marcarEnviado(localUuid: String, caseId: Long?) = cambiar(localUuid) {
        it.copy(
            estado = EstadoCaso.ENVIADO, caseId = caseId, lote = null, error = null, inicioSintomas = null,
            edad = null, sexo = null, resultadoPrueba = null, severidad = null, latitud = null, longitud = null,
        )
    }

    override suspend fun marcarRechazado(localUuid: String, error: String) =
        cambiar(localUuid) { it.copy(estado = EstadoCaso.RECHAZADO, error = error, lote = null) }

    override suspend fun soltar(lote: String) =
        filas.update { lista -> lista.map { if (it.lote == lote) it.copy(lote = null) else it } }

    // Con la llave foránea: sus fotos se van con él.
    override suspend fun descartar(localUuid: String): Int {
        val borrar = filas.value.any { it.localUuid == localUuid && it.estado == EstadoCaso.RECHAZADO }
        if (!borrar) return 0
        filas.update { lista -> lista.filterNot { it.localUuid == localUuid } }
        fotos.update { lista -> lista.filterNot { it.caso == localUuid } }
        return 1
    }

    val fotos = MutableStateFlow<List<FotoLocal>>(emptyList())

    fun foto(id: String) = fotos.value.single { it.id == id }

    override suspend fun insertarFotos(fotos: List<FotoLocal>) {
        check(fotos.all { f -> filas.value.any { it.localUuid == f.caso } }) { "foto sin caso" }
        this.fotos.update { it + fotos }
    }

    override suspend fun fotosDelCaso(caso: String): List<String> = fotos.value.filter { it.caso == caso }.map { it.id }

    override suspend fun fotosPorSubir(cuenta: Long): List<FotoPorSubir> {
        val enviados = filas.value.filter { it.cuenta == cuenta && it.estado == EstadoCaso.ENVIADO && it.caseId != null }
            .associate { it.localUuid to it.caseId!! }
        return fotos.value.filter { it.estado == EstadoFoto.PENDIENTE && it.caso in enviados }
            .sortedWith(compareBy({ it.tomadaEn }, { it.id }))
            .map { FotoPorSubir(it.id, enviados.getValue(it.caso)) }
    }

    private fun cambiarFoto(id: String, cambio: (FotoLocal) -> FotoLocal) =
        fotos.update { lista -> lista.map { if (it.id == id) cambio(it) else it } }

    override suspend fun marcarFotoSubida(id: String, evidencia: Long) =
        cambiarFoto(id) { it.copy(estado = EstadoFoto.SUBIDA, evidencia = evidencia, error = null) }

    override suspend fun marcarFotoRechazada(id: String, error: String) =
        cambiarFoto(id) { it.copy(estado = EstadoFoto.RECHAZADA, error = error) }

    override fun conteoDeFotos(cuenta: Long): Flow<List<ConteoFotos>> = combine(filas, fotos) { casos, lista ->
        val deLaCuenta = casos.filter { it.cuenta == cuenta }.map { it.localUuid }.toSet()
        lista.filter { it.caso in deLaCuenta }.groupBy { it.caso }.map { (caso, del) ->
            ConteoFotos(caso, del.size, del.count { it.estado == EstadoFoto.SUBIDA }, del.count { it.estado == EstadoFoto.RECHAZADA })
        }
    }
}

// Sin Bitmap en la PC: "reducir" copia el archivo tal cual.
fun fotosDePrueba() = Fotos(Files.createTempDirectory("fotos").toFile()) { abrir, destino ->
    abrir().use { entrada -> destino.outputStream().use { entrada.copyTo(it) } }
}

class CatalogoDaoFalso(
    enfermedades: List<Enfermedad> = emptyList(),
    municipios: List<Municipio> = emptyList(),
) : CatalogoDao() {
    val listaEnfermedades = MutableStateFlow(enfermedades)
    val listaMunicipios = MutableStateFlow(municipios)

    override fun enfermedades(): Flow<List<Enfermedad>> = listaEnfermedades.map { l -> l.sortedBy { it.nombre } }
    override fun municipios(): Flow<List<Municipio>> = listaMunicipios.map { l -> l.sortedBy { it.nombre } }
    override suspend fun borrarEnfermedades() { listaEnfermedades.value = emptyList() }
    override suspend fun borrarMunicipios() { listaMunicipios.value = emptyList() }
    override suspend fun insertarEnfermedades(lista: List<Enfermedad>) { listaEnfermedades.update { it + lista } }
    override suspend fun insertarMunicipios(lista: List<Municipio>) { listaMunicipios.update { it + lista } }
}

fun casoDePrueba(
    localUuid: String,
    cuenta: Long = 12,
    capturadoEn: Long = 1,
    municipio: Long = 10,
) = CasoLocal(
    localUuid = localUuid, cuenta = cuenta, enfermedad = 1, municipio = municipio,
    fechaReporte = "2026-11-05", capturadoEn = capturadoEn,
)
