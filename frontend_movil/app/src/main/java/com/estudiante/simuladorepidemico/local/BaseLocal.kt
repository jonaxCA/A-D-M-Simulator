package com.estudiante.simuladorepidemico.local

import androidx.room.AutoMigration
import androidx.room.Database
import androidx.room.RoomDatabase

// epidemia.db: fuera de los respaldos (res/xml), porque los casos llevan datos de salud. Cada
// versión deja su esquema en app/schemas/; un teléfono con casos sin enviar se migra, no se borra.
// 1 → 2: la tabla fotos.
@Database(
    entities = [CasoLocal::class, FotoLocal::class, Enfermedad::class, Municipio::class],
    version = 2,
    autoMigrations = [AutoMigration(from = 1, to = 2)],
)
abstract class BaseLocal : RoomDatabase() {
    abstract fun casos(): CasosDao
    abstract fun catalogo(): CatalogoDao

    companion object {
        const val ARCHIVO = "epidemia.db"
    }
}
