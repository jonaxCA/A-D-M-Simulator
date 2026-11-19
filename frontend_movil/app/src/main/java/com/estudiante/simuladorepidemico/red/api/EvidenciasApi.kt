package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.Evidencia
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.Path

interface EvidenciasApi {
    // El archivo va tal cual en el cuerpo, no como formulario. 201, o 200 si esa foto ya estaba en
    // el caso: reintentar no la duplica.
    @POST("api/v1/cases/{case_id}/attachments")
    suspend fun subir(@Path("case_id") caso: Long, @Body archivo: RequestBody): Evidencia
}
