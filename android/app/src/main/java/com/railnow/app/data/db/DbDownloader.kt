package com.railnow.app.data.db

import android.content.Context
import com.railnow.app.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.IOException

private const val DB_FILE_NAME = "kr_rail_timetable.sqlite"

class DbDownloadException(message: String) : IOException(message)

/**
 * DB(184MB)를 앱에 번들하지 않고 최초 실행 시 내려받는 방식(사용자 확정, 2026-08-31) —
 * APK 크기·git 리포 크기를 줄이고, DB 개정 시 앱 재배포 없이 새 릴리스만 올리면 됨.
 * 아직 GitHub 저장소가 없어 `DB_DOWNLOAD_URL`은 비어 있다 — 저장소·릴리스 생성 후
 * `secrets.properties`에 채울 것(형식은 secrets.properties.example 주석 참조).
 */
object DbDownloader {
    private val client = OkHttpClient()

    fun targetFile(context: Context): File = context.getDatabasePath(DB_FILE_NAME)

    /** 이미 받아둔 파일이 있으면 그대로 반환, 없으면 다운로드한다. onProgress: 0.0~1.0. */
    suspend fun ensureDatabaseFile(
        context: Context,
        onProgress: (Float) -> Unit = {},
    ): File = withContext(Dispatchers.IO) {
        val target = targetFile(context)
        if (target.exists() && target.length() > 0L) return@withContext target

        val url = BuildConfig.DB_DOWNLOAD_URL
        if (url.isBlank()) {
            throw DbDownloadException(
                "DB_DOWNLOAD_URL 미설정 — secrets.properties에 GitHub Releases 다운로드 URL을 채울 것",
            )
        }

        target.parentFile?.mkdirs()
        val tempFile = File(target.parentFile, "$DB_FILE_NAME.download")

        val request = Request.Builder().url(url).build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw DbDownloadException("DB 다운로드 실패: HTTP ${response.code}")
            }
            val body = response.body ?: throw DbDownloadException("DB 다운로드 응답 본문 없음")
            val total = body.contentLength()
            body.byteStream().use { input ->
                tempFile.outputStream().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    var readBytes = 0L
                    while (true) {
                        val n = input.read(buffer)
                        if (n == -1) break
                        output.write(buffer, 0, n)
                        readBytes += n
                        if (total > 0) onProgress(readBytes.toFloat() / total)
                    }
                }
            }
        }
        if (!tempFile.renameTo(target)) {
            throw DbDownloadException("다운로드한 DB 파일 이동 실패: $tempFile -> $target")
        }
        target
    }
}
