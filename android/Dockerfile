# 안드로이드 빌드/테스트/lint 전용 컨테이너. 에뮬레이터는 포함하지 않는다
# (WSL2/Hyper-V 중첩 가상화 한계로 Docker 안 GPU 가속 사실상 불가 — 과설계 방지).
# 인터랙티브 UI 확인(에뮬레이터·실기기)은 Android Studio를 네이티브 설치해 사용할 것.
FROM gradle:8.10-jdk21

ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV ANDROID_HOME=$ANDROID_SDK_ROOT
ENV PATH=$PATH:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools

RUN mkdir -p $ANDROID_SDK_ROOT/cmdline-tools \
    && curl -sSL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o /tmp/cmdline-tools.zip \
    && unzip -q /tmp/cmdline-tools.zip -d $ANDROID_SDK_ROOT/cmdline-tools \
    && mv $ANDROID_SDK_ROOT/cmdline-tools/cmdline-tools $ANDROID_SDK_ROOT/cmdline-tools/latest \
    && rm /tmp/cmdline-tools.zip

RUN yes | sdkmanager --licenses > /dev/null \
    && sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0"

WORKDIR /workspace
