package com.estudiante.simuladorepidemico.red.api

import com.estudiante.simuladorepidemico.red.Dispositivo
import com.estudiante.simuladorepidemico.red.PedidoDispositivo
import retrofit2.http.Body
import retrofit2.http.POST

interface DispositivosApi {
    // 201 la primera vez; 200 si ya era de la cuenta. 409 si es de otra cuenta o está revocado.
    @POST("api/v1/devices")
    suspend fun registrar(@Body pedido: PedidoDispositivo): Dispositivo
}
