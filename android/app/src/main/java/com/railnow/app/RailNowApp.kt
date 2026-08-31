package com.railnow.app

import android.app.Application
import com.railnow.app.data.db.DbDownloader
import com.railnow.app.data.db.RailNowDatabase
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** 수동 DI 컨테이너 — 규모상 Hilt 미사용(확정 사항). 필요해지면 나중에 도입. */
class RailNowApp : Application() {
    private val dbMutex = Mutex()
    private var db: RailNowDatabase? = null

    /** DB가 아직 안 받아져 있으면 먼저 내려받는다(OnboardingScreen에서 진행률과 함께 호출). */
    suspend fun database(onDownloadProgress: (Float) -> Unit = {}): RailNowDatabase {
        db?.let { return it }
        return dbMutex.withLock {
            db ?: run {
                val file = DbDownloader.ensureDatabaseFile(this, onDownloadProgress)
                RailNowDatabase.build(this, file).also { db = it }
            }
        }
    }
}
