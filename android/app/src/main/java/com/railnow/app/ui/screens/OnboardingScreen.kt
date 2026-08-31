package com.railnow.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.railnow.app.RailNowApp
import com.railnow.app.ui.nav.Routes

/**
 * 최초 실행 시 DB(184MB, GitHub Releases에서 다운로드, DbDownloader 참조)를 내려받는 단계.
 * 이미 받아져 있으면(RailNowApp.database가 캐시 확인) 진행률 없이 바로 홈으로 넘어간다.
 */
@Composable
fun OnboardingScreen(navController: NavHostController) {
    val app = LocalContext.current.applicationContext as RailNowApp
    var progress by remember { mutableFloatStateOf(0f) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        try {
            app.database(onDownloadProgress = { progress = it })
            navController.navigate(Routes.HOME) {
                popUpTo(Routes.ONBOARDING) { inclusive = true }
            }
        } catch (e: Exception) {
            error = e.message ?: "DB 준비 실패"
        }
    }

    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text(text = "온보딩", style = MaterialTheme.typography.titleLarge)
            if (error != null) {
                Text(text = "오류: $error")
            } else {
                CircularProgressIndicator(progress = { progress })
                Text(text = "시각표 데이터 준비 중… ${(progress * 100).toInt()}%")
            }
        }
    }
}
