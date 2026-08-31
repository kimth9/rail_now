package com.railnow.app.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * 색상 역할 4가지(project_app_design_direction 메모리 확정) — 절대 섞어 쓰지 않는다.
 * 1) 노선색: "어느 노선인지" 식별 전용(즐겨찾기 칩·헤더)
 * 2) 카운트다운: 실시간 강조 전용(다음 열차, 진행률 바)
 * 3) LiveUpdateOn: Live Update 켜짐 상태 전용
 * 4) Selected: "선택됨" 상태 전용(카운트다운과 별개)
 */
object RailColors {
    val CountdownDark = Color(0xFFFFB238)
    val CountdownLight = Color(0xFFB8860B)

    val LiveUpdateOnDark = Color(0xFF34C38F)
    val LiveUpdateOnLight = Color(0xFF1F8B6B)

    val Selected = Color(0xFF123C6B)
    val DangerDelete = Color(0xFFC1443A)
}

/** 노선명 -> 실제 코레일/서울교통공사 노선색. 필요해지는 노선을 그때그때 추가한다. */
val LineColors: Map<String, Color> = mapOf(
    "1호선" to Color(0xFF0052A4),
    "경의중앙선" to Color(0xFF77C4A3),
    "수인분당선" to Color(0xFFF5A200),
)
