package com.railnow.app.ui.nav

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.railnow.app.ui.screens.FavoritesSettingsScreen
import com.railnow.app.ui.screens.HomeScreen
import com.railnow.app.ui.screens.OnboardingScreen
import com.railnow.app.ui.screens.RailResultsScreen
import com.railnow.app.ui.screens.RailSearchScreen
import com.railnow.app.ui.screens.RouteDirectionSelectScreen
import com.railnow.app.ui.screens.SearchResultsScreen
import com.railnow.app.ui.screens.TimetableDetailScreen
import com.railnow.app.ui.screens.TrackingScreen

/** user-flow.html(2026-08-27 확정) 9화면 전환을 그대로 옮긴 네비게이션 뼈대. */
@Composable
fun RailNowNavGraph() {
    val navController = rememberNavController()
    NavHost(navController = navController, startDestination = Routes.ONBOARDING) {
        composable(Routes.ONBOARDING) { OnboardingScreen(navController) }
        composable(Routes.HOME) { HomeScreen(navController) }
        composable(Routes.SEARCH_RESULTS) { SearchResultsScreen(navController) }
        composable(Routes.ROUTE_DIRECTION_SELECT) { RouteDirectionSelectScreen(navController) }
        composable(Routes.TIMETABLE_DETAIL) { TimetableDetailScreen(navController) }
        composable(Routes.TRACKING) { TrackingScreen(navController) }
        composable(Routes.RAIL_SEARCH) { RailSearchScreen(navController) }
        composable(Routes.RAIL_RESULTS) { RailResultsScreen(navController) }
        composable(Routes.FAVORITES_SETTINGS) { FavoritesSettingsScreen(navController) }
    }
}
