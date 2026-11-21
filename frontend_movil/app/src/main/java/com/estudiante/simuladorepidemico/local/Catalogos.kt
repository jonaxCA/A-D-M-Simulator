package com.estudiante.simuladorepidemico.local

import com.estudiante.simuladorepidemico.red.Apis

// Baja los catálogos cuando hay red, para capturar sin ella. Si falla, lanza el error y se queda
// lo que ya había.
class Catalogos(private val apis: Apis, private val dao: CatalogoDao) {
    suspend fun actualizar() {
        val enfermedades = mutableListOf<Enfermedad>()
        var pagina = 1
        do {
            val leida = apis.enfermedades().listar(estado = "activa", pagina = pagina, tamano = 100)
            enfermedades += leida.enfermedades.map { Enfermedad(it.id, it.nombre) }
            pagina++
        } while (pagina <= leida.paginas)
        val municipios = apis.regiones().listar().municipios.map { Municipio(it.id, it.nombre) }
        dao.reemplazar(enfermedades, municipios)
    }
}
