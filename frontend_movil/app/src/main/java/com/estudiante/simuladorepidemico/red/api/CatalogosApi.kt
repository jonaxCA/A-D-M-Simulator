package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.ListaMunicipios
import com.estudiante.simuladorepidemico.red.PaginaEnfermedades
import retrofit2.http.GET
import retrofit2.http.Query

// Los dos catálogos son públicos: no llevan token.
interface EnfermedadesApi {
    @GET("api/v1/diseases")
    suspend fun listar(
        @Query("status") estado: String,
        @Query("page") pagina: Int,
        @Query("size") tamano: Int,
    ): PaginaEnfermedades
}

interface RegionesApi {
    @GET("api/v1/regions")
    suspend fun listar(): ListaMunicipios
}
