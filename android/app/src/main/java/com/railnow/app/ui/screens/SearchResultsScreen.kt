package com.railnow.app.ui.screens

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import com.railnow.app.ui.nav.Routes

@Composable
fun SearchResultsScreen(navController: NavHostController) {
    PlaceholderScaffold(
        title = "검색 결과",
        nextLabel = "노선·방향 선택",
        onNext = { navController.navigate(Routes.ROUTE_DIRECTION_SELECT) },
    )
}
