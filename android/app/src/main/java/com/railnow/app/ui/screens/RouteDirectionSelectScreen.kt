package com.railnow.app.ui.screens

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import com.railnow.app.ui.nav.Routes

@Composable
fun RouteDirectionSelectScreen(navController: NavHostController) {
    PlaceholderScaffold(
        title = "노선·방향 선택",
        nextLabel = "시각표 상세",
        onNext = { navController.navigate(Routes.TIMETABLE_DETAIL) },
    )
}
