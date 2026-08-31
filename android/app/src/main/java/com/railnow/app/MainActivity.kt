package com.railnow.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.railnow.app.ui.nav.RailNowNavGraph
import com.railnow.app.ui.theme.RailNowTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            RailNowTheme {
                RailNowNavGraph()
            }
        }
    }
}
