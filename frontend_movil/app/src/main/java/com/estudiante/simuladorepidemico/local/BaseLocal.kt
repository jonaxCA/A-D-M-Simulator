package com.estudiante.simuladorepidemico.local

import androidx.room.Database
import androidx.room.RoomDatabase

// epidemia.db: fuera de los respaldos (res/xml), porque los casos llevan datos de salud.
@Database(entities = [CasoLocal::class, Enfermedad::class, Municipio::class], version = 1)
abstract class BaseLocal : RoomDatabase() {
    abstract fun casos(): CasosDao
    abstract fun catalogo(): CatalogoDao

    companion object {
        const val ARCHIVO = "epidemia.db"
    }
}
