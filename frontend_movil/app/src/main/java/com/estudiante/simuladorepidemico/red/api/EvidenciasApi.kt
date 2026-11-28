package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.Evidencia
import com.estudiante.simuladorepidemico.red.EvidenciasDeCaso
import com.estudiante.simuladorepidemico.red.UrlFirmada
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface EvidenciasApi {
    // El archivo va tal cual en el cuerpo, no como formulario. 201, o 200 si esa foto ya estaba en
    // el caso: reintentar no la duplica.
    @POST("api/v1/cases/{case_id}/attachments")
    suspend fun subir(@Path("case_id") caso: Long, @Body archivo: RequestBody): Evidencia

    // Las fotos de un caso, con su tipo y su huella.
    @GET("api/v1/cases/{case_id}/attachments")
    suspend fun deCaso(@Path("case_id") caso: Long): EvidenciasDeCaso

    // La URL firmada de una (D30): se pide justo antes de bajarla y no se guarda.
    @GET("api/v1/attachments/{id}/url")
    suspend fun url(@Path("id") id: Long): UrlFirmada
}
