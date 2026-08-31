package com.railnow.app.data.db.dao

import androidx.room.Dao
import androidx.room.Query
import com.railnow.app.data.db.entities.DoorDirection
import com.railnow.app.data.db.entities.Stop
import com.railnow.app.data.db.entities.StopDoorSide
import com.railnow.app.data.db.entities.StopTime
import com.railnow.app.data.db.entities.StationGroup
import com.railnow.app.data.db.entities.Trip

// DB는 파이썬 파이프라인이 미리 만든 완성본이라 전부 읽기 전용(@Insert/@Update 없음).

@Dao
interface StopDao {
    @Query("SELECT * FROM stops WHERE name_ko = :nameKo")
    suspend fun findByNameKo(nameKo: String): List<Stop>

    @Query("SELECT * FROM stops WHERE group_id = :groupId")
    suspend fun findByGroupId(groupId: String): List<Stop>
}

@Dao
interface StationGroupDao {
    @Query("SELECT * FROM station_groups WHERE name_ko = :name")
    suspend fun findByName(name: String): List<StationGroup>
}

@Dao
interface TripDao {
    @Query("SELECT * FROM trips WHERE trip_id = :tripId")
    suspend fun findById(tripId: String): Trip?
}

@Dao
interface StopTimeDao {
    @Query("SELECT * FROM stop_times WHERE trip_id = :tripId ORDER BY stop_seq")
    suspend fun findByTripId(tripId: String): List<StopTime>
}

@Dao
interface DoorDirectionDao {
    @Query("SELECT * FROM door_directions WHERE group_id = :groupId")
    suspend fun findByGroupId(groupId: String): List<DoorDirection>
}

@Dao
interface StopDoorSideDao {
    @Query("SELECT * FROM stop_door_side WHERE trip_id = :tripId ORDER BY stop_seq")
    suspend fun findByTripId(tripId: String): List<StopDoorSide>
}
