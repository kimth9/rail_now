package com.railnow.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

// 라이트/다크는 같은 컴포넌트 형태를 공유하고 색 토큰만 바뀐다(디자인 확정 사항).
private val DarkColors = darkColorScheme(
    primary = RailColors.CountdownDark,
    secondary = RailColors.LiveUpdateOnDark,
    tertiary = RailColors.Selected,
)

private val LightColors = lightColorScheme(
    primary = RailColors.CountdownLight,
    secondary = RailColors.LiveUpdateOnLight,
    tertiary = RailColors.Selected,
)

@Composable
fun RailNowTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) DarkColors else LightColors
    MaterialTheme(
        colorScheme = colors,
        typography = RailNowTypography,
        content = content,
    )
}
