package com.railnow.app.ui.screens

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import com.railnow.app.ui.nav.Routes

/** 차종별 아이콘(trainfrontview.net 소재, 프로덕션 반영 전 이용문의 필요)은 후속 작업. */
@Composable
fun RailResultsScreen(navController: NavHostController) {
    PlaceholderScaffold(
        title = "일반·고속철도 검색 결과",
        nextLabel = "시각표 상세",
        onNext = { navController.navigate(Routes.TIMETABLE_DETAIL) },
    )
}
