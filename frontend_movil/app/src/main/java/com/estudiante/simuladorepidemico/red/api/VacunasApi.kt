package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.ListaLotesVacuna
import com.estudiante.simuladorepidemico.red.LoteVacuna
import com.estudiante.simuladorepidemico.red.PedidoDosis
import com.estudiante.simuladorepidemico.red.PedidoLoteVacuna
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface VacunasApi {
    @GET("api/v1/vaccine-lots")
    suspend fun buscar(@Query("lot_code") codigo: String): ListaLotesVacuna

    @GET("api/v1/vaccine-lots/{id}")
    suspend fun consultar(@Path("id") id: Long): LoteVacuna

    // 201; 200 si ya estaba con los mismos datos; 409 si alguien lo registró distinto.
    @POST("api/v1/vaccine-lots")
    suspend fun registrar(@Body pedido: PedidoLoteVacuna): LoteVacuna

    // 409 si no alcanzan las dosis o el lote caducó: no descuenta nada.
    @POST("api/v1/vaccine-lots/{id}/doses")
    suspend fun aplicar(@Path("id") id: Long, @Body pedido: PedidoDosis): LoteVacuna
}
