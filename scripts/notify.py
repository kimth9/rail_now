"""장시간 로컬 스크립트의 완료/실패를 Windows Toast로 알린다 (팀 표준, 프로젝트_표준_가이드.md §13).

Claude Code 세션이 닫혀 있어도 동작한다 — 알림 발신에 세션이 관여하지 않고, PC가 켜져
로그인된 상태에서 OS가 직접 띄운다. 추가 pip 의존성 없음(PowerShell 내장 WinRT API 사용).

사용 예 (run_all.py 등 장시간 파이프라인 끝):
    from scripts.notify import notify

    ok, fail = 0, 0
    for item in items:
        try:
            process(item)
            ok += 1
        except Exception:
            fail += 1
    notify(
        "run_all 완료" if fail == 0 else "run_all 완료 (실패 있음)",
        f"성공 {ok} / 실패 {fail}",
    )

주의: 개별 실패를 내부에서 잡아먹고 마지막에 "완료"로만 알리는 기존 버그를 반복하지
않으려면, try/except로 감싸는 것만으로는 부족하다 — 항목별 성공/실패를 직접 카운트해서
그 요약을 notify()에 실어 보낼 것.
"""

import subprocess

_PS_TEMPLATE = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null

$template = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>{title}</text>
      <text>{message}</text>
    </binding>
  </visual>
</toast>
"@

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{app_id}").Show($toast)
"""


def notify(title: str, message: str, app_id: str = "VibeCoding") -> None:
    """Windows Toast 알림을 띄운다. 실패해도(예: 비 Windows 환경) 예외를 올리지 않는다."""
    script = _PS_TEMPLATE.format(
        title=title.replace('"', "'"),
        message=message.replace('"', "'"),
        app_id=app_id,
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        pass
