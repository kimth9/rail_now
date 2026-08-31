package com.railnow.app.data.db.entities

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * 기존 `output/kr_rail_timetable.sqlite` 스키마를 그대로 매핑한다(Room이 만든 DB가 아니라
 * 파이썬 파이프라인이 만든 사전 구축 DB). PRAGMA table_info로 확인한 결과 PK 포함 전부
 * NOT NULL 제약이 없지만, Room은 기본키를 nullable로 선언하는 것 자체를 막는다(KSP 컴파일
 * 오류) — 그래서 PK 필드만 non-null로 선언하고 나머지는 실제 컬럼과 맞춰 nullable로 둔다.
 */

@Entity(tableName = "stops")
data class Stop(
    @PrimaryKey val stop_id: String,
    val display_name: String?,
    val name_ko: String?,
    val line: String?,
    val name_hanja: String?,
    val group_id: String?,
)

@Entity(tableName = "station_groups")
data class StationGroup(
    @PrimaryKey val group_id: String,
    val name_ko: String?,
)

@Entity(tableName = "trips")
data class Trip(
    @PrimaryKey val trip_id: String,
    val train_no: String?,
    val line_name: String?,
    val formation: String?,
    val direction: String?,
    val service_id: String?,
    val origin: String?,
    val destination: String?,
    val source: String?,
)

@Entity(tableName = "stop_times", primaryKeys = ["trip_id", "stop_seq"])
data class StopTime(
    val trip_id: String,
    val stop_seq: Int,
    val stop_id: String?,
    val arr_sec: Int?,
    val dep_sec: Int?,
    val stop_type: String?,
)

@Entity(tableName = "door_directions")
data class DoorDirection(
    @PrimaryKey val id: Int,
    val line_sheet: String?,
    val group_id: String?,
    val station_name: String?,
    val direction: String?,
    val normal_side: String?,
    val evac_side: String?,
    val type: String?,
)

@Entity(tableName = "stop_door_side", primaryKeys = ["trip_id", "stop_seq"])
data class StopDoorSide(
    val trip_id: String,
    val stop_seq: Int,
    val door_side: String?,
    val is_evac: Int?,
    val overtaken_by_trip_id: String?,
)
