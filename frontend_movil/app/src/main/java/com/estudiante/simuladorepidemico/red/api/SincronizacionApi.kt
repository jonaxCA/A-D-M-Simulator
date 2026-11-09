package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.PedidoLote
import com.estudiante.simuladorepidemico.red.RespuestaLote
import retrofit2.http.Body
import retrofit2.http.POST

interface SincronizacionApi {
    // 200 aunque haya rechazos: cada caso trae su resultado. 503 o 409: reenviar el mismo lote.
    @POST("api/v1/sync/cases")
    suspend fun enviar(@Body pedido: PedidoLote): RespuestaLote
}
