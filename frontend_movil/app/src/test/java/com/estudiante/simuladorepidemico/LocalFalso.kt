package com.estudiante.simuladorepidemico

import com.estudiante.simuladorepidemico.local.CasoLocal
import com.estudiante.simuladorepidemico.local.CasosDao
import com.estudiante.simuladorepidemico.local.CatalogoDao
import com.estudiante.simuladorepidemico.local.Enfermedad
import com.estudiante.simuladorepidemico.local.EstadoCaso
import com.estudiante.simuladorepidemico.local.Municipio
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update

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

    override suspend fun descartar(localUuid: String) =
        filas.update { lista -> lista.filterNot { it.localUuid == localUuid && it.estado == EstadoCaso.RECHAZADO } }
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
