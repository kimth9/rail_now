package com.railnow.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.railnow.app.ui.nav.Routes

/**
 * 홈(허브) — 하단 플로팅 바(알약형, 다음 열차 카운트다운)는 후속 작업에서 채운다.
 * 지금은 도시·광역철도 / 일반·고속철도 두 진입점과 즐겨찾기 편집 진입만 연결.
 */
@Composable
fun HomeScreen(navController: NavHostController) {
    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(text = "홈", style = MaterialTheme.typography.titleLarge)
            Button(onClick = { navController.navigate(Routes.SEARCH_RESULTS) }) {
                Text("도시·광역철도 검색")
            }
            Button(onClick = { navController.navigate(Routes.RAIL_SEARCH) }) {
                Text("일반·고속철도 검색")
            }
            Button(onClick = { navController.navigate(Routes.FAVORITES_SETTINGS) }) {
                Text("즐겨찾기·설정")
            }
        }
    }
}
