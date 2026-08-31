package com.railnow.app.data.network

import kotlinx.serialization.Serializable
import retrofit2.http.GET
import retrofit2.http.Path

/**
 * 서울 열린데이터광장 실시간 지하철 API 2종(2026-08-31 URL·인증 검증 완료,
 * feedback_verify_api_endpoint_urls 메모리 참조 — swopenapi.seoul.go.kr, :8088 아님).
 * baseUrl: http://swopenapi.seoul.go.kr/api/subway/
 * 응답 코드: INFO-000=성공, INFO-200=데이터 없음(정상), INFO-100=인증키 오류.
 */
interface SeoulSubwayApiService {
    @GET("{key}/json/realtimeStationArrival/0/5/{stationName}")
    suspend fun getStationArrival(
        @Path("key") key: String,
        @Path("stationName") stationName: String,
    ): SeoulSubwayResponse

    @GET("{key}/json/realtimePosition/0/100/{lineName}")
    suspend fun getLinePosition(
        @Path("key") key: String,
        @Path("lineName") lineName: String,
    ): SeoulSubwayResponse
}

@Serializable
data class SeoulSubwayResponse(
    val errorMessage: SeoulSubwayStatus? = null,
)

@Serializable
data class SeoulSubwayStatus(
    val status: Int? = null,
    val code: String? = null,
    val message: String? = null,
)
