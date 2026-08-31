package com.railnow.app.ui.screens

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import com.railnow.app.ui.nav.Routes

/** 일반·고속철도 출발역·도착역 입력(예매 방식과 동일하게 두 역 지정). */
@Composable
fun RailSearchScreen(navController: NavHostController) {
    PlaceholderScaffold(
        title = "일반·고속철도 검색",
        nextLabel = "조회하기",
        onNext = { navController.navigate(Routes.RAIL_RESULTS) },
    )
}
