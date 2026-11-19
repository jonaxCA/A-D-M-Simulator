package com.estudiante.simuladorepidemico.local

import android.database.sqlite.SQLiteDatabase
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

// Un teléfono con la app anterior tiene casos sin enviar en epidemia.db versión 1. Al actualizar,
// Room migra a la 2 sin perderlos. La versión 1 se arma con el esquema que Room exportó
// (app/schemas, que el build pone en los assets de estas pruebas).
@RunWith(AndroidJUnit4::class)
class MigracionTest {
    private val instrumentacion = InstrumentationRegistry.getInstrumentation()
    private val contexto = instrumentacion.targetContext
    private val nombre = "migracion-prueba.db"

    @After
    fun borrar() {
        contexto.deleteDatabase(nombre)
    }

    private fun esquema(version: Int): JSONObject = instrumentacion.context.assets
        .open("${BaseLocal::class.java.name}/$version.json").bufferedReader().use { JSONObject(it.readText()) }
        .getJSONObject("database")

    @Test
    fun de_la_1_a_la_2_los_casos_se_quedan_y_aparece_fotos() = runBlocking {
        val v1 = esquema(1)
        SQLiteDatabase.openOrCreateDatabase(contexto.getDatabasePath(nombre).apply { parentFile!!.mkdirs() }, null).use { base ->
            val entidades = v1.getJSONArray("entities")
            for (i in 0 until entidades.length()) {
                val entidad = entidades.getJSONObject(i)
                val tabla = entidad.getString("tableName")
                base.execSQL(entidad.getString("createSql").replace("\${TABLE_NAME}", tabla))
                entidad.optJSONArray("indices")?.let { indices ->
                    for (j in 0 until indices.length()) {
                        base.execSQL(indices.getJSONObject(j).getString("createSql").replace("\${TABLE_NAME}", tabla))
                    }
                }
            }
            val preparacion = v1.getJSONArray("setupQueries")
            for (i in 0 until preparacion.length()) base.execSQL(preparacion.getString(i))
            base.execSQL(
                "INSERT INTO casos (localUuid, cuenta, enfermedad, municipio, fechaReporte, edad, capturadoEn, estado) " +
                    "VALUES ('sin-enviar', 12, 1, 10, '2026-11-05', 34, 1, 'PENDIENTE')"
            )
            base.version = 1
        }

        val nueva = Room.databaseBuilder(contexto, BaseLocal::class.java, nombre).build()
        try {
            val dao = nueva.casos()
            val caso = dao.deLaCuenta(12).first().single()
            assertEquals("sin-enviar" to 34, caso.localUuid to caso.edad)
            dao.insertarFotos(listOf(FotoLocal("f1", "sin-enviar", tomadaEn = 0)))
            assertEquals(listOf("f1"), dao.fotosDelCaso("sin-enviar"))
            assertEquals(2, nueva.openHelper.readableDatabase.version)
        } finally {
            nueva.close()
        }
    }
}
