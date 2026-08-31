package com.railnow.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.railnow.app.data.db.DbDownloader
import com.railnow.app.data.db.RailNowDatabase
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * DB가 정상적으로 내려받아져 Room으로 열리는지 확인하는 최소 스모크 테스트. 실기기·에뮬레이터
 * 전용(androidTest) — 이유는 DbDownloader.kt 상단 주석 및 RailNowDatabaseSmokeTest 구버전
 * 히스토리(history.md 2026-08-31) 참조: Robolectric이 아직 API 36을 지원하지 않음.
 *
 * `DB_DOWNLOAD_URL`이 아직 비어 있으면(GitHub 저장소 생성 전) 실제 네트워크 없이는 검증할 수
 * 없으므로 스킵한다 — URL이 채워지면 이 테스트가 자동으로 활성화된다.
 */
@RunWith(AndroidJUnit4::class)
class RailNowDatabaseSmokeTest {

    @Test
    fun 서울역이_조회된다() = runBlocking {
        assumeTrue("DB_DOWNLOAD_URL 미설정 — secrets.properties 채운 뒤 재실행할 것", BuildConfig.DB_DOWNLOAD_URL.isNotBlank())

        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val file = DbDownloader.ensureDatabaseFile(context)
        val db = RailNowDatabase.build(context, file)
        val result = db.stopDao().findByNameKo("서울")
        assertTrue("stops 테이블에서 '서울' 역을 하나도 못 찾음", result.isNotEmpty())
        db.close()
    }
}
