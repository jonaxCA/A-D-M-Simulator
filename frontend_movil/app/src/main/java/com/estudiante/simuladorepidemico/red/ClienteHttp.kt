package com.estudiante.simuladorepidemico.red

import com.estudiante.simuladorepidemico.sesion.AlmacenSesion
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Response
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.io.IOException

// explicitNulls = false: un campo opcional en null no se manda, en lugar de mandarlo como null.
val json = Json {
    ignoreUnknownKeys = true
    explicitNulls = false
}

// Los servicios responden XML si no se les pide JSON.
fun clienteBase(): OkHttpClient = OkHttpClient.Builder()
    .addInterceptor { cadena ->
        cadena.proceed(cadena.request().newBuilder().header("Accept", "application/json").build())
    }
    .build()

fun clienteConToken(base: OkHttpClient, almacen: AlmacenSesion, renovador: Renovador): OkHttpClient =
    base.newBuilder()
        .addInterceptor { cadena ->
            val pedido = cadena.request()
            val access = runBlocking { almacen.tokens() }?.access
            cadena.proceed(
                if (access == null) pedido
                else pedido.newBuilder().header("Authorization", "Bearer $access").build()
            )
        }
        .authenticator(renovador)
        .build()

fun retrofit(url: String, cliente: OkHttpClient): Retrofit = Retrofit.Builder()
    .baseUrl(url)
    .client(cliente)
    .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
    .build()

fun problema(respuesta: Response): Problema? =
    runCatching { json.decodeFromString<Problema>(respuesta.peekBody(16_384).string()) }.getOrNull()

fun problema(error: HttpException): Problema =
    error.response()?.errorBody()?.string()
        ?.let { runCatching { json.decodeFromString<Problema>(it) }.getOrNull() }
        ?: Problema(error.code(), error.message(), "")

// Lo que se le muestra a la persona. Los detail del servidor ya vienen en español.
fun mensajeDeError(error: Throwable): String = when (error) {
    is HttpException -> problema(error).detail.ifBlank { "El servidor respondió ${error.code()}." }
    is IOException -> "No se pudo conectar con los servicios. Revisa tu conexión."
    else -> "El servidor respondió algo inesperado."
}
