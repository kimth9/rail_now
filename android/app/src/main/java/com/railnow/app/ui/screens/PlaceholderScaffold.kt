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

/**
 * 화면 뼈대 공용 틀 — 실제 레이아웃(목업 .dc.html 기반)은 후속 작업에서 채운다.
 * 지금은 화면 전환(NavGraph)이 목업 순서대로 동작하는지 확인하는 용도.
 */
@Composable
fun PlaceholderScaffold(
    title: String,
    nextLabel: String? = null,
    onNext: (() -> Unit)? = null,
) {
    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text(text = title, style = MaterialTheme.typography.titleLarge)
            if (nextLabel != null && onNext != null) {
                Button(onClick = onNext, modifier = Modifier.padding(top = 16.dp)) {
                    Text(nextLabel)
                }
            }
        }
    }
}
