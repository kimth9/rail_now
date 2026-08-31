package com.railnow.app.data.network

import kotlinx.serialization.Serializable
import retrofit2.http.GET
import retrofit2.http.Query

/**
 * KRIC(국가철도공단 철도포털) `subwayTimetable` — 정적 도시철도 운행시각표.
 * 2026-08-31 기준 서비스키 발급 대기 중(todo.md 참조) — 응답 실제 구조는 키 발급 후
 * 검증 필요. baseUrl: https://openapi.kric.go.kr/openapi/trainUseInfo/
 */
interface KricApiService {
    @GET("subwayTimetable")
    suspend fun getTimetable(
        @Query("serviceKey") serviceKey: String,
        @Query("format") format: String = "json",
        @Query("dayCd") dayCd: String,
        @Query("railOprIsttCd") railOprIsttCd: String,
        @Query("lnCd") lnCd: String,
        @Query("stinCd") stinCd: String,
    ): KricTimetableResponse
}

@Serializable
data class KricTimetableResponse(
    val trnNo: String? = null,
    val arvTm: String? = null,
    val dptTm: String? = null,
)
