package com.railnow.app.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import com.railnow.app.data.db.dao.DoorDirectionDao
import com.railnow.app.data.db.dao.StationGroupDao
import com.railnow.app.data.db.dao.StopDao
import com.railnow.app.data.db.dao.StopDoorSideDao
import com.railnow.app.data.db.dao.StopTimeDao
import com.railnow.app.data.db.dao.TripDao
import com.railnow.app.data.db.entities.DoorDirection
import com.railnow.app.data.db.entities.Stop
import com.railnow.app.data.db.entities.StopDoorSide
import com.railnow.app.data.db.entities.StopTime
import com.railnow.app.data.db.entities.StationGroup
import com.railnow.app.data.db.entities.Trip
import java.io.File

@Database(
    entities = [Stop::class, StationGroup::class, Trip::class, StopTime::class, DoorDirection::class, StopDoorSide::class],
    version = 1,
    exportSchema = false,
)
abstract class RailNowDatabase : RoomDatabase() {
    abstract fun stopDao(): StopDao
    abstract fun stationGroupDao(): StationGroupDao
    abstract fun tripDao(): TripDao
    abstract fun stopTimeDao(): StopTimeDao
    abstract fun doorDirectionDao(): DoorDirectionDao
    abstract fun stopDoorSideDao(): StopDoorSideDao

    companion object {
        /** [dbFile]은 [DbDownloader.ensureDatabaseFile]로 미리 내려받아 둔 파일이어야 한다. */
        fun build(context: Context, dbFile: File): RailNowDatabase =
            Room.databaseBuilder(context.applicationContext, RailNowDatabase::class.java, dbFile.absolutePath)
                .build()
    }
}
