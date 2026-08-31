package com.railnow.app.ui.screens

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import com.railnow.app.ui.nav.Routes

/**
 * 실시간 추적(허브) — 플로팅 바 확장형 카드(진행률 바 + Live Update on/off)는 후속 작업.
 * 시스템 Live Update 알림은 앱 화면 밖(OS)이라 여기선 다루지 않는다.
 */
@Composable
fun TrackingScreen(navController: NavHostController) {
    PlaceholderScaffold(
        title = "실시간 추적",
        nextLabel = "도착(추적 종료)",
        onNext = {
            navController.navigate(Routes.HOME) {
                popUpTo(Routes.HOME) { inclusive = false }
            }
        },
    )
}
