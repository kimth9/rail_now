package com.railnow.app.ui.screens

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import com.railnow.app.ui.nav.Routes

/** 시각표 상세 — ★즐겨찾기 추가, "열차 승차" 버튼(탑승 확인)은 후속 작업에서 채운다. */
@Composable
fun TimetableDetailScreen(navController: NavHostController) {
    PlaceholderScaffold(
        title = "시각표 상세",
        nextLabel = "실시간 추적 시작",
        onNext = { navController.navigate(Routes.TRACKING) },
    )
}
