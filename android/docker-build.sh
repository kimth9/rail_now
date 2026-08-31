#!/usr/bin/env bash
# 안드로이드 빌드 컨테이너 실행 — 기본값: assembleDebug + 유닛테스트 + lint.
# 사용법: ./docker-build.sh [gradle 태스크...]
set -euo pipefail
cd "$(dirname "$0")"
export MSYS_NO_PATHCONV=1

IMAGE=rail_now-android-build
TASKS=("${@:-assembleDebug testDebugUnitTest lint}")
HOSTDIR="$(pwd -W 2>/dev/null || pwd)"

docker build -t "$IMAGE" .
docker run --rm \
    -v "${HOSTDIR}:/workspace" \
    -v rail_now_gradle_cache:/root/.gradle \
    "$IMAGE" \
    gradle ${TASKS[@]} --no-daemon
